from sqlalchemy import text

from src.core.config import settings
from src.core.job import job_init, job_log, run_background_or_immediately
from src.core.tool import CRUDToolBase, get_statistics_sql, convert_geom_measurement_field
from src.schemas.job import JobStatusType
from src.schemas.layer import (
    FeatureGeometryType,
    IFeatureLayerToolCreate,
    OgrPostgresType,
)
from src.schemas.tool import IAggregationPoint, IAggregationPolygon, IOriginDestination
from src.schemas.toolbox_base import ColumnStatisticsOperation, DefaultResultLayerName
from src.schemas.error import ColumnTypeError
from src.utils import (
    get_result_column,
    search_value,
)


class CRUDAggregateBase(CRUDToolBase):
    def __init__(self, job_id, background_tasks, async_session, user_id, project_id):
        super().__init__(job_id, background_tasks, async_session, user_id, project_id)
        self.table_name_total_stats = (
            f"temporal.total_stats_{str(self.job_id).replace('-', '')}"
        )
        self.table_name_grouped_stats = (
            f"temporal.grouped_stats_{str(self.job_id).replace('-', '')}"
        )

    async def prepare_aggregation(
        self, params: IAggregationPoint | IAggregationPolygon
    ):
        # Get layers
        layers_project = await self.get_layers_project(
            params=params,
        )
        source_layer_project = layers_project["source_layer_project_id"]
        aggregation_layer_project = layers_project.get("aggregation_layer_project_id")

        # Check if mapped statistics field is float, integer or biginteger
        result_check_statistics_field = await self.check_column_statistics(
            layer_project=source_layer_project,
            column_statistics_field=params.column_statistics.field,
        )
        mapped_statistics_field = result_check_statistics_field[
            "mapped_statistics_field"
        ]

        # Create distributed point table or polygon table depend on the geometry type
        if (
            source_layer_project.feature_layer_geometry_type
            == FeatureGeometryType.point
        ):
            temp_source = await self.create_distributed_point_table(
                layer_project=source_layer_project,
            )
        elif (
            source_layer_project.feature_layer_geometry_type
            == FeatureGeometryType.polygon
        ):
            temp_source = await self.create_distributed_polygon_table(
                layer_project=source_layer_project,
            )

        # Check if aggregation_layer_project_id exists
        if aggregation_layer_project:
            # Create distributed polygon table
            temp_aggregation = await self.create_distributed_polygon_table(
                layer_project=aggregation_layer_project,
            )
            attribute_mapping_aggregation = (
                aggregation_layer_project.attribute_mapping.copy()
            )
            # Build select columns
            select_columns_arr = ["geom"] + list(attribute_mapping_aggregation.keys())
            select_columns = ", ".join(
                f"{aggregation_layer_project.table_name}.{column}"
                for column in select_columns_arr
            )
        else:
            attribute_mapping_aggregation = {"text_attr1": f"h3_{params.h3_resolution}"}

        result_column = get_result_column(
            attribute_mapping=attribute_mapping_aggregation,
            base_column_name=params.column_statistics.operation.value,
            datatype=result_check_statistics_field["mapped_statistics_field_type"],
        )

        # Build group by columns
        if params.source_group_by_field:
            # Extend result column with jsonb
            result_column.update(
                get_result_column(
                    attribute_mapping=attribute_mapping_aggregation,
                    base_column_name=f"{params.column_statistics.operation.value}_grouped",
                    datatype="jsonb",
                )
            )
            # Build group by columns
            group_by_columns = ", ".join(
                f"{temp_source}.{search_value(source_layer_project.attribute_mapping, column)}"
                for column in params.source_group_by_field
            )
            group_by_select_columns = ", ".join(
                f"{temp_source}.{search_value(source_layer_project.attribute_mapping, column)}::text"
                for column in params.source_group_by_field
            )
            group_column_name = f"ARRAY_TO_STRING(ARRAY[{group_by_select_columns}], '_') AS group_column_name"

        # Get statistics column query
        statistics_column_query = get_statistics_sql(
            f"{temp_source}." + mapped_statistics_field,
            operation=params.column_statistics.operation,
        )

        # Create insert statement
        insert_columns_arr = (
            ["geom"]
            + list(attribute_mapping_aggregation.keys())
            + list(result_column.keys())
        )
        insert_columns = ", ".join(insert_columns_arr)

        # Create new layer
        layer_in = IFeatureLayerToolCreate(
            name=DefaultResultLayerName[params.tool_type].value,
            feature_layer_geometry_type=FeatureGeometryType.polygon,
            attribute_mapping={**attribute_mapping_aggregation, **result_column},
            tool_type=params.tool_type,
            job_id=self.job_id,
        )

        return {
            "aggregation_layer_project": locals().get(
                "aggregation_layer_project", None
            ),
            "layer_in": layer_in,
            "temp_source": temp_source,
            "temp_aggregation": locals().get("temp_aggregation", None),
            "group_by_columns": locals().get("group_by_columns", None),
            "group_column_name": locals().get("group_column_name", None),
            "statistics_column_query": statistics_column_query,
            "insert_columns": insert_columns,
            "select_columns": locals().get("select_columns", None),
            "result_check_statistics_field": result_check_statistics_field,
            "mapped_statistics_field": mapped_statistics_field,
        }


class CRUDAggregatePoint(CRUDAggregateBase):
    """Tool aggregation points."""

    def __init__(self, job_id, background_tasks, async_session, user_id, project_id):
        super().__init__(job_id, background_tasks, async_session, user_id, project_id)
        self.result_table = (
            f"{settings.USER_DATA_SCHEMA}.polygon_{str(self.user_id).replace('-', '')}"
        )

    @job_log(job_step_name="aggregation")
    async def aggregate_point(self, params: IAggregationPoint):
        # Prepare aggregation
        aggregation = await self.prepare_aggregation(params=params)
        aggregation_layer_project = aggregation["aggregation_layer_project"]
        layer_in = aggregation["layer_in"]
        temp_source = aggregation["temp_source"]
        temp_aggregation = aggregation["temp_aggregation"]
        group_by_columns = aggregation["group_by_columns"]
        group_column_name = aggregation["group_column_name"]
        statistics_column_query = aggregation["statistics_column_query"]
        insert_columns = aggregation["insert_columns"]
        select_columns = aggregation["select_columns"]

        # Create query
        if aggregation_layer_project:
            # Define subquery for grouped by id only
            sql_query_total_stats = f"""
                CREATE TABLE {self.table_name_total_stats} AS
                SELECT {temp_aggregation}.id, {statistics_column_query} AS stats
                FROM {temp_aggregation}, {temp_source}
                WHERE ST_Intersects({temp_aggregation}.geom, {temp_source}.geom)
                AND {temp_aggregation}.h3_3 = {temp_source}.h3_3
                GROUP BY {temp_aggregation}.id
            """
            await self.async_session.execute(sql_query_total_stats)
            await self.async_session.execute(
                f"CREATE INDEX ON {self.table_name_total_stats} (id);"
            )

            if params.source_group_by_field:
                # Define subquery for grouped by id and group_by_field
                sql_query_group_stats = f"""
                    CREATE TABLE {self.table_name_grouped_stats} AS
                    SELECT id, JSONB_OBJECT_AGG(group_column_name, stats) AS stats
                    FROM
                    (
                        SELECT {temp_aggregation}.id, {group_column_name}, {statistics_column_query} AS stats
                        FROM {temp_aggregation}, {temp_source}
                        WHERE ST_Intersects({temp_aggregation}.geom, {temp_source}.geom)
                        AND {temp_aggregation}.h3_3 = {temp_source}.h3_3
                        GROUP BY {temp_aggregation}.id, {group_by_columns}
                    ) AS to_group
                    GROUP BY id
                """
                await self.async_session.execute(text(sql_query_group_stats))
                await self.async_session.execute(
                    f"CREATE INDEX ON {self.table_name_grouped_stats} (id);"
                )

                # Build combined query with two left joins
                sql_query = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    WITH first_join AS
                    (
                        SELECT t.id, t.stats AS total_stats, g.stats AS grouped_stats
                        FROM {self.table_name_grouped_stats} g, {self.table_name_total_stats} t
                        WHERE g.id = t.id
                    )
                    SELECT '{layer_in.id}', {select_columns}, f.total_stats, f.grouped_stats
                    FROM {aggregation_layer_project.table_name}
                    LEFT JOIN first_join f
                    ON {aggregation_layer_project.table_name}.id = f.id
                    WHERE {aggregation_layer_project.table_name}.layer_id = '{aggregation_layer_project.layer_id}'
                """
            else:
                # Build combined query with one left join
                sql_query = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    SELECT '{layer_in.id}', {select_columns}, t.stats AS total_stats
                    FROM {aggregation_layer_project.table_name}
                    LEFT JOIN {self.table_name_total_stats} t
                    ON {aggregation_layer_project.table_name}.id = t.id
                    WHERE {aggregation_layer_project.table_name}.layer_id = '{aggregation_layer_project.layer_id}'
                """
        else:
            # If aggregation_layer_project_id does not exist the h3 grid will be taken for the intersection
            sql_query_total_stats = f"""
                CREATE TABLE {self.table_name_total_stats} AS
                SELECT h3_lat_lng_to_cell(geom::point, {params.h3_resolution}) h3_index, {statistics_column_query} AS stats
                FROM {temp_source}
                GROUP BY h3_lat_lng_to_cell(geom::point, {params.h3_resolution})
            """
            await self.async_session.execute(sql_query_total_stats)
            await self.async_session.execute(
                f"CREATE INDEX ON {self.table_name_total_stats} (h3_index);"
            )

            if params.source_group_by_field:
                # Define subquery for grouped by id and group_by_field
                sql_query_group_stats = f"""
                    CREATE TABLE {self.table_name_grouped_stats} AS
                    SELECT h3_index, JSONB_OBJECT_AGG(group_column_name, stats) AS stats
                    FROM
                    (
                        SELECT h3_lat_lng_to_cell(geom::point, {params.h3_resolution}) h3_index, {group_column_name}, {statistics_column_query} AS stats
                        FROM {temp_source}
                        GROUP BY h3_lat_lng_to_cell(geom::point, {params.h3_resolution}), {group_by_columns}
                    ) AS to_group
                    GROUP BY h3_index
                """
                await self.async_session.execute(sql_query_group_stats)
                await self.async_session.execute(
                    f"CREATE INDEX ON {self.table_name_grouped_stats} (h3_index);"
                )

                sql_query = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    SELECT '{layer_in.id}', ST_SETSRID(h3_cell_to_boundary(t.h3_index)::geometry, 4326),
                    t.h3_index, t.stats AS total_stats, g.stats AS grouped_stats
                    FROM {self.table_name_total_stats} t, {self.table_name_grouped_stats} g
                    WHERE t.h3_index = g.h3_index
                """
            else:
                sql_query = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    SELECT '{layer_in.id}', ST_SETSRID(h3_cell_to_boundary(h3_index)::geometry, 4326),
                    h3_index, t.stats AS total_stats
                    FROM {self.table_name_total_stats} t
                """
        # Execute query
        await self.async_session.execute(sql_query)

        # Create new layer
        await self.create_feature_layer_tool(
            layer_in=layer_in,
            params=params,
        )

        # Delete temporary tables
        await self.delete_temp_tables()

        return {
            "status": JobStatusType.finished.value,
            "msg": "Points where successfully aggregated.",
        }

    @run_background_or_immediately(settings)
    @job_init()
    async def aggregate_point_run(self, params: IAggregationPoint):
        return await self.aggregate_point(params=params)


class CRUDAggregatePolygon(CRUDAggregateBase):
    def __init__(self, job_id, background_tasks, async_session, user_id, project_id):
        super().__init__(job_id, background_tasks, async_session, user_id, project_id)
        self.result_table = (
            f"{settings.USER_DATA_SCHEMA}.polygon_{str(self.user_id).replace('-', '')}"
        )
        self.table_name_pre_grouped = (
            f"temporal.h3_pregrouped_{str(self.job_id).replace('-', '')}"
        )

    @job_log(job_step_name="aggregation")
    async def aggregate_polygon(self, params: IAggregationPolygon):
        # Prepare aggregation
        aggregation = await self.prepare_aggregation(params=params)
        aggregation_layer_project = aggregation["aggregation_layer_project"]
        layer_in = aggregation["layer_in"]
        temp_source = aggregation["temp_source"]
        temp_aggregation = aggregation["temp_aggregation"]
        group_by_columns = aggregation["group_by_columns"]
        group_column_name = aggregation["group_column_name"]
        statistics_column_query = aggregation["statistics_column_query"]
        insert_columns = aggregation["insert_columns"]
        select_columns = aggregation["select_columns"]
        mapped_statistics_field = aggregation["result_check_statistics_field"][
            "mapped_statistics_field"
        ]
        if aggregation_layer_project:
            if params.weigthed_by_intersecting_area:
                statistics_column_query = f"{statistics_column_query} * SUM(ST_AREA(ST_INTERSECTION({temp_aggregation}.geom, {temp_source}.geom)) / ST_AREA({temp_source}.geom))"

            # Define subquery for grouped by id only
            sql_query_total_stats = f"""
                CREATE TABLE {self.table_name_total_stats} AS
                SELECT {temp_aggregation}.id, round(({statistics_column_query})::numeric, 6) AS stats
                FROM {temp_aggregation}, {temp_source}
                WHERE ST_Intersects({temp_aggregation}.geom, {temp_source}.geom)
                AND {temp_aggregation}.h3_3 = {temp_source}.h3_3
                GROUP BY {temp_aggregation}.id
            """
            await self.async_session.execute(sql_query_total_stats)
            await self.async_session.execute(
                f"CREATE INDEX ON {self.table_name_total_stats} (id);"
            )

            if params.source_group_by_field:
                # Define subquery for grouped by id and group_by_field

                sql_query_group_stats = f"""
                    CREATE TABLE {self.table_name_grouped_stats} AS
                    SELECT id, JSONB_OBJECT_AGG(group_column_name, stats) AS stats
                    FROM
                    (
                        SELECT {temp_aggregation}.id, {group_column_name}, round(({statistics_column_query})::numeric, 6) AS stats
                        FROM {temp_aggregation}, {temp_source}
                        WHERE ST_Intersects({temp_aggregation}.geom, {temp_source}.geom)
                        AND {temp_aggregation}.h3_3 = {temp_source}.h3_3
                        GROUP BY {temp_aggregation}.id, {group_by_columns}
                    ) AS to_group
                    GROUP BY id
                """
                await self.async_session.execute(text(sql_query_group_stats))
                await self.async_session.execute(
                    f"CREATE INDEX ON {self.table_name_grouped_stats} (id);"
                )

                # Build combined query with two left joins
                sql_query_combine = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    WITH first_join AS
                    (
                        SELECT t.id, t.stats AS total_stats, g.stats AS grouped_stats
                        FROM {self.table_name_grouped_stats} g, {self.table_name_total_stats} t
                        WHERE g.id = t.id
                    )
                    SELECT '{layer_in.id}', {select_columns}, f.total_stats, f.grouped_stats
                    FROM {aggregation_layer_project.table_name}
                    LEFT JOIN first_join f
                    ON {aggregation_layer_project.table_name}.id = f.id
                    WHERE {aggregation_layer_project.table_name}.layer_id = '{aggregation_layer_project.layer_id}'
                """
            else:
                # Build combined query with one left join
                sql_query_combine = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    SELECT '{layer_in.id}', {select_columns}, t.stats AS total_stats
                    FROM {aggregation_layer_project.table_name}
                    LEFT JOIN {self.table_name_total_stats} t
                    ON {aggregation_layer_project.table_name}.id = t.id
                    WHERE {aggregation_layer_project.table_name}.layer_id = '{aggregation_layer_project.layer_id}'
                """
        else:
            # Get average edge length of h3 grid
            avg_edge_length = await self.async_session.execute(
                f"SELECT h3_get_hexagon_edge_length_avg({params.h3_resolution}, 'm')"
            )
            avg_edge_length = avg_edge_length.scalars().first()

            # Build group by fields
            group_by_columns_subquery = ""
            if params.source_group_by_field:
                group_by_columns.replace(f"{temp_source}.", "")
                group_by_columns_subquery = group_by_columns.replace(
                    f"{temp_source}.", "p."
                )
                group_column_name = group_column_name.replace(f"{temp_source}.", "p.")

            # Build statistics column query
            if params.weigthed_by_intersecting_area:
                first_statistic_column_query = """* SUM(
                    (CASE WHEN ST_WITHIN(j.geom, p.geom) THEN 1
                    WHEN ST_Intersects(j.geom, p.geom) THEN ST_AREA(ST_Intersection(j.geom, p.geom)) / ST_AREA(j.geom)
                    ELSE 0
                    END))
                """
                if (
                    params.column_statistics.operation.value
                    == ColumnStatisticsOperation.count.value
                ):
                    statistics_val = "1"
                    statistics_sql = "SUM(val)"
                else:
                    if mapped_statistics_field == "$intersected_area":
                        statistics_val = convert_geom_measurement_field(
                            "j." + mapped_statistics_field
                        )
                    else:
                        statistics_val = "p." + mapped_statistics_field

                    statistics_sql = get_statistics_sql(
                        "val", params.column_statistics.operation
                    )

            # Pregroup the data
            group_column_name_with_comma = (
                f"{group_column_name}, " if group_column_name else ""
            )
            group_by_columns_subquery_with_comma = (
                f"{group_by_columns_subquery}, " if group_by_columns_subquery else ""
            )

            sql_query_pre_grouped = f"""
                CREATE TABLE {self.table_name_pre_grouped} AS
                SELECT h3_target, {group_column_name_with_comma}
                (ARRAY_AGG({statistics_val}))[1] {first_statistic_column_query} AS val
                FROM (
                    SELECT *,
                    (ST_DUMP(ST_BUFFER(geom::geography, {avg_edge_length})::geometry)).geom AS buffer_geom
                    FROM {temp_source}
                ) p
                LEFT JOIN LATERAL (
                    SELECT h3_target, ST_SETSRID(h3_cell_to_boundary(h3_target)::geometry, 4326) AS geom
                    FROM
                    (
                        SELECT CASE WHEN h3_polygon_to_cells IS NULL
                        THEN h3_lat_lng_to_cell(ST_CENTROID(p.buffer_geom)::point, {params.h3_resolution})
                        ELSE h3_polygon_to_cells
                        END AS h3_target
                        FROM
                        (
                            SELECT h3_polygon_to_cells
                            FROM h3_polygon_to_cells(p.buffer_geom::polygon, ARRAY[]::polygon[], {params.h3_resolution})
                        ) x
                    ) y
                ) j ON TRUE
                WHERE ST_Intersects(j.geom, p.geom)
                GROUP BY h3_target, {group_by_columns_subquery_with_comma} p.id;
            """
            await self.async_session.execute(sql_query_pre_grouped)
            await self.async_session.execute(
                f"CREATE INDEX ON {self.table_name_pre_grouped} (h3_target);"
            )

            # Compute total stats
            sql_query_total_stats = f"""
                CREATE TABLE {self.table_name_total_stats} AS
                SELECT h3_target::text, ROUND({statistics_sql}::numeric, 6) AS stats
                FROM {self.table_name_pre_grouped}
                GROUP BY h3_target;
            """
            await self.async_session.execute(sql_query_total_stats)
            await self.async_session.execute(
                f"CREATE INDEX ON {self.table_name_total_stats} (h3_target);"
            )

            if params.source_group_by_field:
                # Compute grouped stats
                sql_query_group_stats = f"""
                    CREATE TABLE {self.table_name_grouped_stats} AS
                    SELECT h3_target, JSONB_OBJECT_AGG(group_column_name, stats) AS stats
                    FROM
                    (
                        SELECT h3_target::text, group_column_name, ROUND({statistics_sql}::numeric, 6) AS stats
                        FROM {self.table_name_pre_grouped}
                        GROUP BY h3_target, group_column_name
                    ) AS to_group
                    GROUP BY h3_target;
                """
                await self.async_session.execute(text(sql_query_group_stats))
                await self.async_session.execute(
                    f"CREATE INDEX ON {self.table_name_grouped_stats} (h3_target);"
                )

                sql_query_combine = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    SELECT '{layer_in.id}', ST_SETSRID(h3_cell_to_boundary(t.h3_target::h3index)::geometry, 4326),
                    t.h3_target, t.stats as total_stats, g.stats AS grouped_stats
                    FROM {self.table_name_grouped_stats} g, {self.table_name_total_stats} t
                    WHERE g.h3_target = t.h3_target;
                """
            else:
                sql_query_combine = f"""
                    INSERT INTO {self.result_table} (layer_id, {insert_columns})
                    SELECT '{layer_in.id}', ST_SETSRID(h3_cell_to_boundary(h3_target::h3index)::geometry, 4326),
                    h3_target, stats AS total_stats
                    FROM {self.table_name_total_stats}
                """

        # Execute combined query
        await self.async_session.execute(sql_query_combine)

        # Create new layer
        await self.create_feature_layer_tool(
            layer_in=layer_in,
            params=params,
        )
        # Delete temporary tables
        await self.delete_temp_tables()

        return {
            "status": JobStatusType.finished.value,
            "msg": "Polygons where successfully aggregated.",
        }

    @run_background_or_immediately(settings)
    @job_init()
    async def aggregate_polygon_run(self, params: IAggregationPolygon):
        return await self.aggregate_polygon(params=params)


class CRUDOriginDestination(CRUDToolBase):
    def __init__(self, job_id, background_tasks, async_session, user_id, project_id):
        super().__init__(job_id, background_tasks, async_session, user_id, project_id)
        self.result_table_relation = (
            f"{settings.USER_DATA_SCHEMA}.line_{str(self.user_id).replace('-', '')}"
        )
        self.result_table_point = (
            f"{settings.USER_DATA_SCHEMA}.point_{str(self.user_id).replace('-', '')}"
        )

    @job_log(job_step_name="origin_destination")
    async def origin_destination(self, params: IOriginDestination):
        # Get layers
        layers_project = await self.get_layers_project(
            params=params,
        )
        geometry_layer_project = layers_project["geometry_layer_project_id"]
        origin_destination_matrix_layer_project = layers_project[
            "origin_destination_matrix_layer_project_id"
        ]
        # Check that origin_column and destination_column are the same type
        mapped_unique_id_column = search_value(
            geometry_layer_project.attribute_mapping,
            params.unique_id_column,
        )
        mapped_origin_column = search_value(
            origin_destination_matrix_layer_project.attribute_mapping,
            params.origin_column,
        )
        mapped_destination_column = search_value(
            origin_destination_matrix_layer_project.attribute_mapping,
            params.destination_column,
        )
        if (
            len(
                {
                    mapped_unique_id_column.split("_")[0],
                    mapped_origin_column.split("_")[0],
                    mapped_destination_column.split("_")[0],
                }
            )
            > 1
        ):
            raise ColumnTypeError(
                "The unique_id, origin and destination column must be of the same type"
            )

        # Check if weight column is of type number
        mapped_weight_column = search_value(
            origin_destination_matrix_layer_project.attribute_mapping,
            params.weight_column,
        )
        if mapped_weight_column.split("_")[0] not in [
            OgrPostgresType.Integer,
            OgrPostgresType.Real,
            OgrPostgresType.Integer64,
        ]:
            raise ColumnTypeError(
                f"Mapped weight field is not {OgrPostgresType.Integer}, {OgrPostgresType.Real}, {OgrPostgresType.Integer64}."
            )

        # Create new layers for relations and points
        result_layer_point = IFeatureLayerToolCreate(
            name=DefaultResultLayerName[params.tool_type + "_point"].value,
            feature_layer_geometry_type=FeatureGeometryType.point,
            attribute_mapping={
                mapped_weight_column.split("_")[0] + "_attr1": "weight",
            },
            tool_type=params.tool_type,
            job_id=self.job_id,
        )

        # Build attribute mapping for relation table
        attribute_mapping_relation = {
            mapped_unique_id_column.split("_")[0] + "_attr1": "origin",
            mapped_unique_id_column.split("_")[0] + "_attr2": "destination",
        }
        if mapped_weight_column.split("_")[0] + "_attr1" not in attribute_mapping_relation:
            attribute_mapping_relation[
                mapped_weight_column.split("_")[0] + "_attr1"
            ] = "weight"
        else:
            # Get attr of same name with max count
            count_attr = 1
            while (
                mapped_weight_column.split("_")[0] + f"_attr{count_attr}"
            ) in attribute_mapping_relation:
                count_attr += 1
            attribute_mapping_relation[
                mapped_weight_column.split("_")[0] + f"_attr{count_attr}"
            ] = "weight"

        result_layer_relation = IFeatureLayerToolCreate(
            name=DefaultResultLayerName[params.tool_type + "_relation"].value,
            feature_layer_geometry_type=FeatureGeometryType.line,
            attribute_mapping=attribute_mapping_relation,
            tool_type=params.tool_type,
            job_id=self.job_id,
        )

        # Create temp table for geometry layer
        temp_geometry_layer = await self.create_temp_table_layer(
            layer_project=geometry_layer_project,
        )
        await self.async_session.execute(
            f"CREATE INDEX ON {temp_geometry_layer} ({mapped_unique_id_column});"
        )
        await self.async_session.commit()

        # Create temp table for origin destination matrix
        temp_origin_destination_matrix_layer = await self.create_temp_table_layer(
            layer_project=origin_destination_matrix_layer_project,
        )
        await self.async_session.execute(
            f"CREATE INDEX ON {temp_origin_destination_matrix_layer} ({mapped_origin_column}, {mapped_destination_column});"
        )
        await self.async_session.commit()

        # Compute relations
        select_columns = ['matrix.' + attr for attr in list(result_layer_relation.attribute_mapping.keys())]
        select_columns = ', '.join(select_columns)
        sql_query_relations = f"""
            INSERT INTO {self.result_table_relation} (layer_id, geom, {', '.join(list(result_layer_relation.attribute_mapping.keys()))})
            SELECT '{result_layer_relation.id}',
            ST_MakeLine(ST_CENTROID((ARRAY_AGG(origin.geom))[1]), ST_CENTROID((ARRAY_AGG(destination.geom))[1])),
            (ARRAY_AGG(matrix.{mapped_origin_column}))[1] AS origin, (ARRAY_AGG(matrix.{mapped_destination_column}))[1] AS destination,
            SUM(matrix.{mapped_weight_column}) AS weight
            FROM {temp_geometry_layer} origin, {temp_geometry_layer} destination, {temp_origin_destination_matrix_layer} matrix
            WHERE origin.{mapped_unique_id_column} = matrix.{mapped_origin_column}
            AND destination.{mapped_unique_id_column} = matrix.{mapped_destination_column}
            GROUP BY matrix.{mapped_origin_column}, matrix.{mapped_destination_column}
        """
        await self.async_session.execute(sql_query_relations)

        # Compute points
        sql_query_points = f"""
            INSERT INTO {self.result_table_point} (layer_id, geom, {', '.join(list(result_layer_point.attribute_mapping.keys()))})
            WITH grouped AS
            (
                SELECT '{result_layer_point.id}', g.{mapped_unique_id_column}, SUM(m.{mapped_weight_column}) AS weight
                FROM {temp_geometry_layer} g, {temp_origin_destination_matrix_layer} m
                WHERE g.{mapped_unique_id_column} = m.{mapped_destination_column}
                GROUP BY g.{mapped_unique_id_column}
            )
            SELECT '{result_layer_point.id}', ST_CENTROID(g.geom), gg.weight
            FROM {temp_geometry_layer} g, grouped gg
            WHERE g.{mapped_unique_id_column} = gg.{mapped_unique_id_column}
        """
        await self.async_session.execute(sql_query_points)

        # Create new layer
        await self.create_feature_layer_tool(
            layer_in=result_layer_relation,
            params=params,
        )
        await self.create_feature_layer_tool(
            layer_in=result_layer_point,
            params=params,
        )

        return {
            "status": JobStatusType.finished.value,
            "msg": "Origin destination pairs where successfully created.",
        }

    @run_background_or_immediately(settings)
    @job_init()
    async def origin_destination_run(self, params: IAggregationPolygon):
        return await self.origin_destination(params=params)
