# Standard library imports
import asyncio
import json
import os
from uuid import UUID, uuid4

# Third party imports
from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from fastapi_pagination import Params as PaginationParams
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

# Local application imports
from src.core.config import settings
from src.core.job import job_init, run_background_or_immediately
from src.core.layer import FileUpload, OGRFileHandling
from src.crud.base import CRUDBase
from src.crud.crud_job import job as crud_job
from src.db.models.layer import Layer
from src.schemas.job import JobStatusType
from src.schemas.layer import (
    ColumnStatisticsOperation,
    FeatureType,
    IFeatureStandardCreateAdditionalAttributes,
    IFileUploadMetadata,
    IInternalLayerCreate,
    ITableCreateAdditionalAttributes,
    LayerType,
    SupportedOgrGeomType,
    UserDataGeomType,
)
from src.schemas.style import base_properties
from src.schemas.toolbox_base import MaxFeatureCnt
from src.utils import build_where, build_where_clause


class CRUDLayer(CRUDBase):
    """CRUD class for Layer."""
    async def create_internal(
        self,
        async_session: AsyncSession,
        user_id: UUID,
        layer_in: IInternalLayerCreate,
        file_metadata: dict,
        attribute_mapping: dict,
    ):
        additional_attributes = {}
        # Get layer_id and size from import job
        additional_attributes["user_id"] = user_id
        # Create attribute mapping
        additional_attributes["attribute_mapping"] = attribute_mapping

        # Get default style if feature layer
        if file_metadata["data_types"].get("geometry"):
            geom_type = SupportedOgrGeomType[
                file_metadata["data_types"]["geometry"]["type"]
            ].value
            additional_attributes["properties"] = base_properties["feature"][
                "standard"
            ][geom_type]
            additional_attributes["type"] = LayerType.feature
            additional_attributes["feature_layer_type"] = FeatureType.standard
            additional_attributes["feature_layer_geometry_type"] = geom_type
            additional_attributes["extent"] = file_metadata["data_types"]["geometry"][
                "extent"
            ]
            additional_attributes = IFeatureStandardCreateAdditionalAttributes(
                **additional_attributes
            ).dict()
        else:
            additional_attributes["type"] = LayerType.table
            additional_attributes = ITableCreateAdditionalAttributes(
                **additional_attributes
            ).dict()

        # TODO: Add dynamically created thumbnail to layer.
        # Populate layer_in with additional attributes
        layer_in = Layer(
            **layer_in.dict(exclude_none=True),
            **additional_attributes,
        )
        # Update size
        layer_in.size = await self.get_feature_layer_size(async_session=async_session, layer=layer_in)
        layer = await self.create(
            db=async_session,
            obj_in=layer_in,
        )
        return layer


    async def get_internal(self, async_session: AsyncSession, id: UUID):
        """Gets a layer and make sure it is a internal layer."""

        layer = await self.get(async_session, id=id)
        if layer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found"
            )
        if layer.type not in [LayerType.feature, LayerType.table]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Layer is not a feature layer or table layer. The requested operation cannot be performed on this layer.",
            )
        return layer

    async def upload_file(
        self,
        async_session: AsyncSession,
        user_id: UUID,
        layer_type: LayerType,
        file: UploadFile,
    ):
        """Validate file using ogr2ogr."""

        dataset_id = uuid4()
        # Initialize OGRFileUpload
        file_upload = FileUpload(
            async_session=async_session,
            user_id=user_id,
            dataset_id=dataset_id,
            file=file,
        )

        # Save file
        timeout = 120
        try:
            file_path = await asyncio.wait_for(
                file_upload.save_file(file=file),
                timeout,
            )
        except asyncio.TimeoutError:
            # Handle the timeout here. For example, you can raise a custom exception or log it.
            await file_upload.save_file_fail()
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"File upload timed out after {timeout} seconds.",
            )
        except Exception as e:
            # Run failure function if exists
            await file_upload.save_file_fail()
            # Update job status simple to failed
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

        # Initialize OGRFileHandling
        ogr_file_handling = OGRFileHandling(
            async_session=async_session,
            user_id=user_id,
            file_path=file_path,
        )

        # Validate file before uploading
        try:
            validation_result = await asyncio.wait_for(
                ogr_file_handling.validate(),
                timeout,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"File validation timed out after {timeout} seconds.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

        if validation_result.get("status") == "failed":
            # Run failure function if exists
            await file_upload.save_file_fail()
            # Update job status simple to failed
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=validation_result["msg"],
            )

        # Get file size in bytes
        original_position = file.file.tell()
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(original_position)

        # Define metadata object
        metadata = IFileUploadMetadata(
            **validation_result,
            dataset_id=dataset_id,
            file_ending=os.path.splitext(file.filename)[-1][1:],
            file_size=file_size,
            layer_type=layer_type,
        )

        # Save metadata into user folder as json
        metadata_path = os.path.join(
            os.path.dirname(metadata.file_path), "metadata.json"
        )
        with open(metadata_path, "w") as f:
            # Convert dict to json
            json.dump(metadata.json(), f)

        # Add layer_type and file_size to validation_result
        return metadata

    @run_background_or_immediately(settings)
    @job_init()
    async def import_file(
        self,
        background_tasks: BackgroundTasks,
        async_session: AsyncSession,
        job_id: UUID,
        file_metadata: dict,
        user_id: UUID,
        layer_in: IInternalLayerCreate,
    ):
        """Import file using ogr2ogr."""

        # Initialize OGRFileHandling
        ogr_file_upload = OGRFileHandling(
            async_session=async_session,
            user_id=user_id,
            file_path=file_metadata["file_path"],
        )

        # Create attribute mapping out of valid attributes
        attribute_mapping = {}
        for field_type, field_names in file_metadata["data_types"]["valid"].items():
            cnt = 1
            for field_name in field_names:
                if field_name == "id":
                    continue
                attribute_mapping[field_name] = field_type + "_attr" + str(cnt)
                cnt += 1

        temp_table_name = (
            f'{settings.USER_DATA_SCHEMA}."{str(job_id).replace("-", "")}"'
        )

        result = await ogr_file_upload.upload_ogr2ogr(
            temp_table_name=temp_table_name,
            job_id=job_id,
        )
        if result["status"] in [
            JobStatusType.failed.value,
            JobStatusType.timeout.value,
            JobStatusType.killed.value,
        ]:
            return result

        # Migrate temporary table to target table
        result = await ogr_file_upload.migrate_target_table(
            validation_result=file_metadata,
            attribute_mapping=attribute_mapping,
            temp_table_name=temp_table_name,
            layer_id=layer_in.id,
            job_id=job_id,
        )
        if result["status"] in [
            JobStatusType.failed.value,
            JobStatusType.timeout.value,
            JobStatusType.killed.value,
        ]:
            await async_session.rollback()
            return result

        # Add Layer ID to job
        job = await crud_job.get(db=async_session, id=job_id)
        await crud_job.update(
            db=async_session,
            db_obj=job,
            obj_in={
                "layer_ids": [str(layer_in.id)],
            },
        )

        # Create layer
        attribute_mapping = {value: key for key, value in attribute_mapping.items()}
        await self.create_internal(
            async_session=async_session,
            user_id=user_id,
            layer_in=layer_in,
            file_metadata=file_metadata,
            attribute_mapping=attribute_mapping,
        )
        return result

    async def delete_layer_data(self, async_session: AsyncSession, layer):
        """Delete layer data which is in the user data tables."""

        # Delete layer data
        await async_session.execute(
            text(f"DELETE FROM {layer.table_name} WHERE layer_id = '{layer.id}'")
        )
        await async_session.commit()

    async def get_feature_layer_size(self, async_session: AsyncSession, layer: BaseModel | SQLModel):
        """Get size of feature layer."""

        # Get size
        sql_query = f"""
            SELECT SUM(pg_column_size(p.*))
            FROM {layer.table_name} AS p
            WHERE layer_id = '{str(layer.id)}'
        """
        result = await async_session.execute(text(sql_query))
        result = result.fetchall()
        return result[0][0]

    async def get_feature_layer_extent(self, async_session: AsyncSession, layer: BaseModel | SQLModel):
        """Get extent of feature layer."""

        # Get extent
        sql_query = f"""
            SELECT ST_ASTEXT(ST_MULTI(ST_ENVELOPE(ST_Extent(geom))))
            FROM {layer.table_name}
            WHERE layer_id = '{str(layer.id)}'
        """
        result = await async_session.execute(text(sql_query))
        result = result.fetchall()
        return result[0][0]

    async def get_feature_cnt(
        self,
        async_session: AsyncSession,
        layer_project: SQLModel | BaseModel,
        where_query: str = None,
    ):
        """Get feature count for a layer or a layer project."""

        # Get feature count total
        feature_cnt = {}
        table_name = layer_project.table_name
        sql_query = f"SELECT COUNT(*) FROM {table_name} WHERE layer_id = '{str(layer_project.layer_id)}'"
        result = await async_session.execute(text(sql_query))
        feature_cnt["total_count"] = result.scalar_one()

        # Get feature count filtered
        if not where_query:
            where_query = build_where_clause([layer_project.where_query])
        else:
            where_query = build_where_clause([where_query])
        if where_query:
            sql_query = f"SELECT COUNT(*) FROM {table_name} {where_query}"
            result = await async_session.execute(text(sql_query))
            feature_cnt["filtered_count"] = result.scalar_one()
        return feature_cnt

    async def check_exceed_feature_cnt(
        self,
        async_session: AsyncSession,
        max_feature_cnt: int,
        layer,
        where_query: str,
    ):
        """Check if feature count is exceeding the defined limit."""
        feature_cnt = await self.get_feature_cnt(
            async_session=async_session, layer_project=layer, where_query=where_query
        )

        if feature_cnt.get("filtered_count") is not None:
            cnt_to_check = feature_cnt["filtered_count"]
        else:
            cnt_to_check = feature_cnt["total_count"]

        if cnt_to_check > max_feature_cnt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Operation not supported. The layer contains more than {max_feature_cnt} features. Please apply a filter to reduce the number of features.",
            )
        return feature_cnt

    async def check_if_column_suitable_for_stats(
        self, async_session: AsyncSession, id: UUID, column_name: str, query: str
    ):
        # Check if layer is internal layer
        layer = await self.get_internal(async_session, id=id)
        column_mapped = next(
            (
                key
                for key, value in layer.attribute_mapping.items()
                if value == column_name
            ),
            None,
        )

        if column_mapped is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Column not found"
            )

        return {
            "layer": layer,
            "column_mapped": column_mapped,
            "where_query": build_where(id=layer.id, table_name=layer.table_name, query=query, attribute_mapping=layer.attribute_mapping)
        }

    async def get_unique_values(
        self,
        async_session: AsyncSession,
        id: UUID,
        column_name: str,
        order: str,
        query: str,
        page_params: PaginationParams,
    ):
        # Check if layer is suitable for stats
        res_check = await self.check_if_column_suitable_for_stats(
            async_session=async_session, id=id, column_name=column_name, query=query
        )
        layer = res_check["layer"]
        column_mapped = res_check["column_mapped"]
        where_query = res_check["where_query"]
        # Map order
        order_mapped = {"descendent": "DESC", "ascendent": "ASC"}[order]
        # Build query
        sql_query = f"""
        WITH cnt AS (
            SELECT {column_mapped} AS {column_name}, COUNT(*) AS count
            FROM {layer.table_name}
            WHERE {where_query}
            AND {column_mapped} IS NOT NULL
            GROUP BY {column_mapped}
            ORDER BY COUNT(*)
            {order_mapped}
            LIMIT {page_params.size}
            OFFSET {(page_params.page - 1) * page_params.size}
        )
        SELECT JSONB_OBJECT_AGG({column_name}, count) FROM cnt
        """

        # Execute query
        result = await async_session.execute(text(sql_query))
        result = result.fetchall()
        return result[0][0]

    async def get_area_statistics(
        self,
        async_session: AsyncSession,
        id: UUID,
        operation: ColumnStatisticsOperation,
        query: str,
    ):
        # Check if layer is internal layer
        layer = await self.get_internal(async_session, id=id)

        # Where query
        where_query = build_where(id=layer.id, table_name=layer.table_name, query=query, attribute_mapping=layer.attribute_mapping)

        # Check if layer has polygon geoms
        if layer.feature_layer_geometry_type != UserDataGeomType.polygon.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Operation not supported. The layer does not contain polygon geometries. Pick a layer with polygon geometries.",
            )

        # Check if feature count is exceeding the defined limit
        await self.check_exceed_feature_cnt(
            async_session=async_session,
            max_feature_cnt=MaxFeatureCnt.area_statistics.value,
            layer=layer,
            where_query=where_query,
        )
        where_query = "WHERE " + where_query
        # Call SQL function
        sql_query = f"""
            SELECT * FROM basic.area_statistics('{operation.value}', '{layer.table_name}', '{where_query.replace("'", "''")}')
        """
        res = await async_session.execute(
            sql_query,
        )
        res = res.fetchall()
        return res[0][0] if res else None

    async def get_class_breaks(
        self,
        async_session: AsyncSession,
        id: UUID,
        operation: ColumnStatisticsOperation,
        query: str,
        column_name: str,
        stripe_zeros: bool = None,
        breaks: int = None,
    ):
        # Check if layer is suitable for stats
        res = await self.check_if_column_suitable_for_stats(
            async_session=async_session, id=id, column_name=column_name, query=query
        )

        args = res
        where_clause = res["where_query"]
        args["table_name"] = args["layer"].table_name
        # del layer from args
        del args["layer"]

        # Extend where clause
        column_mapped = res["column_mapped"]
        if stripe_zeros:
            where_extension = (
                f" AND {column_mapped} != 0"
                if where_clause
                else f"{column_mapped} != 0"
            )
            args["where"] = where_clause + where_extension

        # Define additional arguments
        if breaks:
            args["breaks"] = breaks

        # Choose the SQL query based on operation
        if operation == ColumnStatisticsOperation.quantile:
            sql_query = "SELECT * FROM basic.quantile_breaks(:table_name, :column_mapped, :where, :breaks)"
        elif operation == ColumnStatisticsOperation.equal_interval:
            sql_query = "SELECT * FROM basic.equal_interval_breaks(:table_name, :column_mapped, :where, :breaks)"
        elif operation == ColumnStatisticsOperation.standard_deviation:
            sql_query = "SELECT * FROM basic.standard_deviation_breaks(:table_name, :column_mapped, :where)"
        elif operation == ColumnStatisticsOperation.heads_and_tails:
            sql_query = "SELECT * FROM basic.heads_and_tails_breaks(:table_name, :column_mapped, :where, :breaks)"
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Operation not supported",
            )

        # Execute the query
        res = await async_session.execute(sql_query, args)
        res = res.fetchall()
        return res[0][0] if res else None


layer = CRUDLayer(Layer)
