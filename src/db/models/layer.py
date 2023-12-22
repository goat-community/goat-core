from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Union
from uuid import UUID

from geoalchemy2 import Geometry, WKBElement
from geoalchemy2.shape import to_shape
from pydantic import validator, root_validator
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as UUID_PG
from sqlmodel import (
    ARRAY,
    Column,
    Field,
    ForeignKey,
    Integer,
    Relationship,
    SQLModel,
    Text,
    UniqueConstraint,
)

from src.db.models._base_class import ContentBaseAttributes, DateTimeBase
from src.db.models.scenario_feature import ScenarioType
from src.core.config import settings
from pydantic import BaseModel

if TYPE_CHECKING:
    from ._link_model import LayerProjectLink
    from .data_store import DataStore
    from .scenario import Scenario
    from .scenario_feature import ScenarioFeature

class ToolType(str, Enum):
    """Indicator types."""

    isochrone_active_mobility = "isochrone_active_mobility"
    isochrone_pt = "isochrone_pt"
    isochrone_car = "isochrone_car"
    oev_gueteklasse = "oev_gueteklasse"
    join = "join"
    aggregation_point = "aggregation_point"


class FeatureType(str, Enum):
    """Feature layer types."""

    standard = "standard"
    tool = "tool"
    scenario = "scenario"
    street_network = "street_network"


class FeatureExportType(str, Enum):
    """Feature layer data types."""

    geojson = "geojson"
    shapefile = "shapefile"
    geopackage = "geopackage"
    geobuf = "geobuf"
    csv = "csv"
    xlsx = "xlsx"
    kml = "kml"


class FeatureServeType(str, Enum):
    mvt = "mvt"
    wfs = "wfs"
    binary = "binary"


class ExternalImageryDataType(str, Enum):
    """Imagery layer data types."""

    wms = "wms"
    xyz = "xyz"
    wmts = "wmts"


class LayerType(str, Enum):
    """Layer types that are supported."""

    feature = "feature"
    external_imagery = "external_imagery"
    external_vector_tile = "external_vector_tile"
    table = "table"


class ExternalVectorTileDataType(str, Enum):
    """VectorTile layer data types."""

    mvt = "mvt"


class FeatureGeometryType(str, Enum):
    """Feature layer geometry types."""

    point = "point"
    line = "line"
    polygon = "polygon"


class GeospatialAttributes(SQLModel):
    """Some general geospatial attributes."""

    extent: str | None = Field(
        sa_column=Column(
            Geometry(geometry_type="MultiPolygon", srid="4326", spatial_index=True),
            nullable=True,
        ),
        description="Geographical Extent of the layer",
    )

    @validator("extent", pre=True)
    def wkt_to_geojson(cls, v):
        if v and isinstance(v, WKBElement):
            return to_shape(v).wkt
        else:
            return v


class LayerBase(ContentBaseAttributes):
    """Base model for layers."""

    data_source: str | None = Field(
        sa_column=Column(Text, nullable=True),
        description="Data source of the layer",
    )
    data_reference_year: int | None = Field(
        sa_column=Column(Integer, nullable=True),
        description="Data reference year of the layer",
    )


layer_base_example = {
    "data_source": "data_source plan4better example",
    "data_reference_year": 2020,
}

def internal_layer_table_name(values: SQLModel | BaseModel):
    """Get the table name for the internal layer."""

    # Get table name
    if values.type == LayerType.feature.value:
        # If of type enum return value
        if isinstance(values.feature_layer_geometry_type, Enum):
            feature_layer_geometry_type = values.feature_layer_geometry_type.value
        else:
            feature_layer_geometry_type = values.feature_layer_geometry_type
    elif values.type == LayerType.table.value:
        feature_layer_geometry_type = "no_geometry"
    else:
        raise ValueError(f"The passed layer type {values.type} is not supported.")

    return f"{settings.USER_DATA_SCHEMA}.{feature_layer_geometry_type}_{str(values.user_id).replace('-', '')}"


# TODO: Relation to check if opportunities_uuids exist in layers
class Layer(LayerBase, GeospatialAttributes, DateTimeBase, table=True):
    """Layer model."""

    __tablename__ = "layer"
    __table_args__ = {"schema": "customer"}

    id: UUID | None = Field(
        sa_column=Column(
            UUID_PG(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=text("uuid_generate_v4()"),
        ),
        description="Layer ID",
    )
    user_id: UUID = Field(
        sa_column=Column(
            UUID_PG(as_uuid=True),
            ForeignKey("customer.user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="Layer owner ID",
    )
    folder_id: UUID = Field(
        sa_column=Column(
            UUID_PG(as_uuid=True),
            ForeignKey("customer.folder.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="Layer folder ID",
    )
    type: LayerType = Field(
        sa_column=Column(Text, nullable=False), description="Layer type"
    )
    data_store_id: UUID | None = Field(
        sa_column=Column(UUID_PG(as_uuid=True), ForeignKey("customer.data_store.id")),
        description="Data store ID of the layer",
    )
    extent: str | None = Field(
        sa_column=Column(
            Geometry(geometry_type="MultiPolygon", srid="4326", spatial_index=False),
            nullable=True,
        ),
        description="Geographical Extent of the layer",
    )
    properties: dict | None = Field(
        sa_column=Column(JSONB, nullable=True),
        description="Properties of the layer",
    )
    other_properties: dict | None = Field(
        sa_column=Column(JSONB, nullable=True),
        description="Other properties of the layer",
    )
    url: str | None = Field(
        sa_column=Column(Text, nullable=True),
        description="Layer URL for tile and imagery layers",
    )
    data_type: Optional[
        Union["ExternalImageryDataType", "ExternalVectorTileDataType"]
    ] = Field(
        sa_column=Column(Text, nullable=True),
        description="Data type for imagery layers and tile layers",
    )
    tool_type: Optional[ToolType] = Field(
        sa_column=Column(Text, nullable=True),
        description="If it is an tool layer, the tool type",
    )
    scenario_id: UUID | None = Field(
        sa_column=Column(
            UUID_PG(as_uuid=True), ForeignKey("customer.scenario.id"), nullable=True
        ),
        description="Scenario ID if there is a scenario associated with this layer",
    )
    scenario_type: Optional["ScenarioType"] = Field(
        sa_column=Column(Text, nullable=True),
        description="Scenario type if the layer is a scenario layer",
    )
    feature_layer_type: Optional["FeatureType"] = Field(
        sa_column=Column(Text, nullable=True), description="Feature layer type"
    )
    feature_layer_geometry_type: FeatureGeometryType | None = Field(
        sa_column=Column(Text, nullable=True),
        description="Geometry type for feature layers",
    )
    size: int | None = Field(
        sa_column=Column(Integer, nullable=True),
        description="Size of the layer in bytes",
    )
    attribute_mapping: dict | None = Field(
        sa_column=Column(JSONB, nullable=True),
        description="Attribute mapping for feature layers",
    )

    # Relationships

    scenario: "Scenario" = Relationship(back_populates="layers")
    scenario_features: List["ScenarioFeature"] = Relationship(
        back_populates="original_layer"
    )
    data_store: "DataStore" = Relationship(back_populates="layers")
    layer_projects: List["LayerProjectLink"] = Relationship(back_populates="layer")

    @validator("extent", pre=True)
    def wkt_to_geojson(cls, v):
        if v and isinstance(v, WKBElement):
            return to_shape(v).wkt
        else:
            return v

    @property
    def table_name(self):
        return internal_layer_table_name(self)
    @property
    def layer_id(self):
        return self.id

# Constraints
UniqueConstraint(Layer.__table__.c.folder_id, Layer.__table__.c.name)
Layer.update_forward_refs()
