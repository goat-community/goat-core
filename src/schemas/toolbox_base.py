# Standard Libraries
from enum import Enum
from typing import List
from uuid import UUID

from fastapi import BackgroundTasks, Depends, Query

# Third-party Libraries
from pydantic import BaseModel, Field, root_validator
from sqlalchemy.ext.asyncio import AsyncSession

# Local Packages
from src.endpoints.deps import get_db, get_user_id


class ColumnStatisticsOperation(str, Enum):
    count = "count"
    sum = "sum"
    mean = "mean"
    median = "median"
    min = "min"
    max = "max"


class ColumnStatistic(BaseModel):
    """Column statistic schema."""

    operation: ColumnStatisticsOperation
    field: str

class DefaultResultLayerName(str, Enum):
    """Default result layer name schema."""

    join = "Join"
    isochrone_starting_points = "Isochrone Starting Points"
    isochrone_active_mobility = "Active Mobility Isochrone"
    isochrone_pt = "Public Transport Isochrone"
    isochrone_car = "Car Isochrone"
    oev_gueteklasse = "ÖV-Güteklassen"
    oev_gueteklasse_station = "ÖV-Güteklassen Station"
    aggregation_point = "Aggregation Point"

class MaxFeatureCnt(int, Enum):
    """Max feature count schema."""

    area_statistics = 100000
    join = 100000
    isochrone_active_mobility = 1000
    oev_gueteklasse = 10000

class ToolsWithReferenceAreaCheck(str, Enum):
    """Tools with reference area check schema."""

    oev_gueteklasse = "oev_gueteklasse"

class MaxSizeReferenceArea(int, Enum):
    """Max size reference in km2."""

    oev_gueteklasse = 500000


class GeofenceTable(str, Enum):
    """Geofence tool table mapping."""
    isochrone_active_mobility = "basic.geofence_active_mobility"
    isochrone_pt = "basic.geofence_pt"
    isochrone_car = "basic.geofence_car"
    oev_gueteklasse = "basic.geofence_pt"


class IToolResponse(BaseModel):
    """Tool response schema."""

    job_id: UUID = Field(
        ...,
        title="Job ID",
        description="The ID of the job that is used to track the tool execution.",
    )


class IsochroneStartingPointsBase(BaseModel):
    """Base model for isochrone attributes."""

    latitude: List[float] | None = Field(
        None,
        title="Latitude",
        description="The latitude of the isochrone center.",
    )
    longitude: List[float] | None = Field(
        None,
        title="Longitude",
        description="The longitude of the isochrone center.",
    )
    layer_project_id: UUID | None = Field(
        None,
        title="Layer ID",
        description="The ID of the layer that contains the starting points.",
    )

    @root_validator(pre=True)
    def check_either_coords_or_layer_project_id(cls, values):
        lat = values.get("latitude")
        long = values.get("longitude")
        layer_project_id = values.get("layer_project_id")

        if lat and long:
            if layer_project_id:
                raise ValueError(
                    "Either provide latitude and longitude or layer_project_id, not both."
                )
            if len(lat) != len(long):
                raise ValueError("Latitude and longitude must have the same length.")

            # Check if lat/lon are within WGS84 bounds
            for lat_val in lat:
                if lat_val < -90 or lat_val > 90:
                    raise ValueError("Latitude must be between -90 and 90.")
            for lon_val in long:
                if lon_val < -180 or lon_val > 180:
                    raise ValueError("Longitude must be between -180 and 180.")

        if not (lat and long) and not layer_project_id:
            raise ValueError(
                "Must provide either latitude and longitude or layer_project_id."
            )

        return values


class PTSupportedDay(str, Enum):
    """PT supported days schema."""

    weekday = "weekday"
    saturday = "saturday"
    sunday = "sunday"


class CommonToolParams:
    def __init__(
        self,
        background_tasks: BackgroundTasks,
        async_session: AsyncSession = Depends(get_db),
        user_id: UUID = Depends(get_user_id),
        project_id: str = Query(
            ...,
            title="Project ID of the project that contains the layers.",
            description="The project ID of the project that contains the layers.",
        ),
    ):
        self.background_tasks = background_tasks
        self.async_session = async_session
        self.user_id = user_id
        self.project_id = project_id
