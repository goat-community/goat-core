from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, validator, root_validator
from src.schemas.toolbox_base import IsochroneStartingPointsBase, IsochroneType
from src.schemas.layer import ToolType


class IsochroneStartingPointsActiveMobility(IsochroneStartingPointsBase):
    """Model for the active mobility isochrone starting points."""

    # Check that the starting points for active mobility are below 1000
    @root_validator(pre=True)
    def check_starting_points(cls, values):
        lat = values.get("latitude")
        long = values.get("longitude")

        if lat and long:
            if len(lat) > 1000:
                raise ValueError("The maximum number of starting points is 1000.")
            if len(long) > 1000:
                raise ValueError("The maximum number of starting points is 1000.")
        return values


class RoutingActiveMobilityType(str, Enum):
    """Routing active mobility type schema."""

    walking = "walking"
    bicycle = "bicycle"
    pedelec = "pedelec"


class TravelTimeCostActiveMobility(BaseModel):
    """Travel time cost schema."""

    max_traveltime: int = Field(
        ...,
        title="Max Travel Time",
        description="The maximum travel time in minutes.",
        ge=1,
        le=45,
    )
    traveltime_step: int = Field(
        ...,
        title="Travel Time Step",
        description="The travel time step in minutes.",
    )
    speed: int = Field(
        ...,
        title="Speed",
        description="The speed in km/h.",
        ge=1,
        le=25,
    )


# TODO: Check how to treat miles
class TravelDistanceCostActiveMobility(BaseModel):
    """Travel distance cost schema."""

    max_distance: int = Field(
        ...,
        title="Max Distance",
        description="The maximum distance in meters.",
        ge=50,
        le=20000,
    )
    distance_step: int = Field(
        ...,
        title="Distance Step",
        description="The distance step in meters.",
    )

    # Make sure that the distance step can be divided by 50 m
    @validator("distance_step", pre=True, always=True)
    def distance_step_divisible_by_50(cls, v):
        if v % 50 != 0:
            raise ValueError("The distance step must be divisible by 50 m.")
        return v


class IIsochroneActiveMobility(BaseModel):
    """Model for the active mobility isochrone"""

    starting_points: IsochroneStartingPointsActiveMobility = Field(
        ...,
        title="Starting Points",
        description="The starting points of the isochrone.",
    )
    routing_type: RoutingActiveMobilityType = Field(
        ...,
        title="Routing Type",
        description="The routing type of the isochrone.",
    )
    travel_cost: TravelTimeCostActiveMobility | TravelDistanceCostActiveMobility = (
        Field(
            ...,
            title="Travel Cost",
            description="The travel cost of the isochrone.",
        )
    )
    scenario_id: UUID | None = Field(
        None,
        title="Scenario ID",
        description="The ID of the scenario that is used for the routing.",
    )
    isochrone_type: IsochroneType = Field(
        ...,
        title="Return Type",
        description="The return type of the isochrone.",
    )
    polygon_difference: bool | None = Field(
        None,
        title="Polygon Difference",
        description="If true, the polygons returned will be the geometrical difference of two following calculations.",
    )

    @property
    def tool_type(self):
        return ToolType.isochrone_active_mobility

    @property
    def geofence_table(self):
        mode = ToolType.isochrone_active_mobility.value.replace("isochrone_", "")
        return f"basic.geofence_{mode}"


request_examples = {
    "isochrone_active_mobility": {
        "single_point_walking": {
            "summary": "Single point isochrone walking",
            "value": {
                "starting_points": {"latitude": [13.4050], "longitude": [52.5200]},
                "routing_type": "walking",
                "travel_cost": {
                    "max_traveltime": 30,
                    "traveltime_step": 10,
                    "speed": 5,
                },
            },
        },
        "single_point_cycling": {
            "summary": "Single point isochrone cycling",
            "value": {
                "starting_points": {"latitude": [13.4050], "longitude": [52.5200]},
                "routing_type": "bicycle",
                "travel_cost": {
                    "max_traveltime": 15,
                    "traveltime_step": 5,
                    "speed": 15,
                },
            },
        },
        "single_point_walking_scenario": {
            "summary": "Single point isochrone walking",
            "value": {
                "starting_points": {"latitude": [13.4050], "longitude": [52.5200]},
                "routing_type": "walking",
                "travel_cost": {
                    "max_traveltime": 30,
                    "traveltime_step": 10,
                    "speed": 5,
                },
                "scenario_id": "e7dcaae4-1750-49b7-89a5-9510bf2761ad",
            },
        },
        "multi_point_walking": {
            "summary": "Multi point isochrone walking",
            "value": {
                "starting_points": {
                    "latitude": [
                        13.4050,
                        13.4060,
                        13.4070,
                        13.4080,
                        13.4090,
                        13.4100,
                        13.4110,
                        13.4120,
                        13.4130,
                        13.4140,
                    ],
                    "longitude": [
                        52.5200,
                        52.5210,
                        52.5220,
                        52.5230,
                        52.5240,
                        52.5250,
                        52.5260,
                        52.5270,
                        52.5280,
                        52.5290,
                    ],
                },
                "routing_type": "walking",
                "travel_cost": {
                    "max_traveltime": 30,
                    "traveltime_step": 10,
                    "speed": 5,
                },
            },
        },
        "multi_point_cycling": {
            "summary": "Multi point isochrone cycling",
            "value": {
                "starting_points": {
                    "latitude": [
                        13.4050,
                        13.4060,
                        13.4070,
                        13.4080,
                        13.4090,
                        13.4100,
                        13.4110,
                        13.4120,
                        13.4130,
                        13.4140,
                    ],
                    "longitude": [
                        52.5200,
                        52.5210,
                        52.5220,
                        52.5230,
                        52.5240,
                        52.5250,
                        52.5260,
                        52.5270,
                        52.5280,
                        52.5290,
                    ],
                },
                "routing_type": "bicycle",
                "travel_cost": {
                    "max_traveltime": 15,
                    "traveltime_step": 5,
                    "speed": 15,
                },
            },
        },
        "layer_based_walking": {
            "summary": "Layer based isochrone walking",
            "value": {
                "starting_points": {
                    "layer_id": "39e16c27-2b03-498e-8ccc-68e798c64b8d"  # Sample UUID for the layer
                },
                "routing_type": "walking",
                "travel_cost": {
                    "max_traveltime": 30,
                    "traveltime_step": 10,
                    "speed": 5,
                },
            },
        },
    }
}
