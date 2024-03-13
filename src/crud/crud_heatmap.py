from src.core.tool import CRUDToolBase
from src.schemas.heatmap import (
    IHeatmapGravityActive,
    IHeatmapGravityMotorized,
    IHeatmapClosestAverageActive,
    IHeatmapClosestAverageMotorized,
    IHeatmapConnectivityActive,
    IHeatmapConnectivityMotorized,
)
from src.crud.crud_layer_project import layer_project as crud_layer_project


class CRUDHeatmapBase(CRUDToolBase):
    def __init__(self, job_id, background_tasks, async_session, user_id, project_id):
        super().__init__(job_id, background_tasks, async_session, user_id, project_id)

    async def fetch_opportunity_layers(self, params: IHeatmapGravityActive | IHeatmapGravityMotorized |
        IHeatmapClosestAverageActive | IHeatmapClosestAverageMotorized | IHeatmapConnectivityActive |
        IHeatmapConnectivityMotorized,
    ):
        # Iterate over opportunity layers supplied by user
        opportunity_layers = []
        for layer in params.opportunities:
            # Get project for this layer
            input_layer_types = params.input_layer_types
            layer_project = await crud_layer_project.get_internal(
                async_session=self.async_session,
                id=layer.opportunity_layer_project_id,
                project_id=self.project_id,
                expected_layer_types=input_layer_types[
                    "opportunity_layer_project_id"
                ].layer_types,
                expected_geometry_types=input_layer_types[
                    "opportunity_layer_project_id"
                ].feature_layer_geometry_types,
            )

            # Check Max feature count
            await self.check_max_feature_cnt(
                layers_project=[layer_project],
                tool_type=params.tool_type,
            )

            opportunity_layers.append({
                "table_name": layer_project.table_name,
                "where_query": layer_project.where_query,
                "layer": layer,
            })

        return opportunity_layers
