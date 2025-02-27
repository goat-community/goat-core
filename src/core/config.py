from typing import Any, Dict, Optional
from uuid import UUID

import boto3
from pydantic import BaseSettings, HttpUrl, PostgresDsn, validator


class AsyncPostgresDsn(PostgresDsn):
    allowed_schemes = {"postgres+asyncpg", "postgresql+asyncpg"}


# For old versions of SQLAlchemy (< 1.4)
class SyncPostgresDsn(PostgresDsn):
    allowed_schemes = {"postgresql", "postgresql+psycopg2", "postgresql+pg8000"}


class Settings(BaseSettings):
    AUTH: Optional[bool] = True
    TEST_MODE: Optional[bool] = False
    ENVIRONMENT: Optional[str] = "dev"
    API_V2_STR: str = "/api/v2"
    DATA_DIR: str = "/app/data"
    TEST_DATA_DIR: str = "/app/tests/data"
    PROJECT_NAME: Optional[str] = "GOAT Core API"
    USER_DATA_SCHEMA: Optional[str] = "user_data"
    CUSTOMER_SCHEMA: Optional[str] = "customer"
    ACCOUNTS_SCHEMA: Optional[str] = "accounts"
    REGION_MAPPING_PT_TABLE: Optional[str] = "basic.region_mapping_pt"
    BASE_STREET_NETWORK: Optional[UUID] = "903ecdca-b717-48db-bbce-0219e41439cf"

    JOB_TIMEOUT_DEFAULT: int = 120
    ASYNC_CLIENT_DEFAULT_TIMEOUT: Optional[float] = (
        10.0  # Default timeout for async http client
    )
    ASYNC_CLIENT_READ_TIMEOUT: Optional[float] = (
        30.0  # Read timeout for async http client
    )
    CRUD_NUM_RETRIES: Optional[int] = 30  # Number of times to retry calling an endpoint
    CRUD_RETRY_INTERVAL: Optional[int] = 3  # Number of seconds to wait between retries

    HEATMAP_GRAVITY_MAX_SENSITIVITY: int = 1000000

    SENTRY_DSN: Optional[HttpUrl] = None
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: Optional[str] = "5432"
    POSTGRES_DATABASE_URI: str = None

    @validator("POSTGRES_DATABASE_URI", pre=True)
    def postgres_database_uri_(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        return f'postgresql://{values.get("POSTGRES_USER")}:{values.get("POSTGRES_PASSWORD")}@{values.get("POSTGRES_SERVER")}:{values.get("POSTGRES_PORT")}/{values.get("POSTGRES_DB")}'

    ASYNC_SQLALCHEMY_DATABASE_URI: Optional[AsyncPostgresDsn] = None

    @validator("ASYNC_SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_async_db_connection(
        cls, v: Optional[str], values: Dict[str, Any]
    ) -> Any:
        if isinstance(v, str):
            return v
        return AsyncPostgresDsn.build(
            scheme="postgresql+asyncpg",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    # R5 config
    R5_WORKER_VERSION: str = "v7.0"
    R5_VARIANT_INDEX: int = -1
    R5_HOST: str = None
    R5_MONGO_DB_URL: Optional[str] = None

    @validator("R5_MONGO_DB_URL", pre=True)
    def r5_mongodb_url(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        # mongodb://172.17.0.1:27017/analysis
        return f'mongodb://{values.get("R5_HOST")}:27017/analysis'

    R5_API_PORT: Optional[int] = 80
    R5_API_URL: Optional[str] = None

    @validator("R5_API_URL", pre=True)
    def r5_api_url(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        return f'http://{values.get("R5_HOST")}:{values.get("R5_API_PORT")}/api'

    R5_AUTHORIZATION: str = None

    @validator("R5_AUTHORIZATION", pre=True)
    def r5_authorization(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if v:
            return f"Basic {v}"
        return None

    # GOAT GEOAPI config
    GOAT_GEOAPI_HOST: str = None

    # GOAT Routing config
    GOAT_ROUTING_HOST: str = None
    GOAT_ROUTING_PORT: Optional[int] = 80
    GOAT_ROUTING_URL: Optional[str] = None

    @validator("GOAT_ROUTING_URL", pre=True)
    def goat_routing_url(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        return f'{values.get("GOAT_ROUTING_HOST")}:{values.get("GOAT_ROUTING_PORT")}/api/v2/routing'

    GOAT_ROUTING_AUTHORIZATION: str = None

    @validator("GOAT_ROUTING_AUTHORIZATION", pre=True)
    def goat_routing_authorization(
        cls, v: Optional[str], values: Dict[str, Any]
    ) -> Any:
        if v:
            return f"Basic {v}"
        return None

    SAMPLE_AUTHORIZATION = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICI0OG80Z1JXelh3YXBTY3NTdHdTMXZvREFJRlNOa0NtSVFpaDhzcEJTc2kwIn0.eyJleHAiOjE2OTEwMDQ1NTYsImlhdCI6MTY5MTAwNDQ5NiwiYXV0aF90aW1lIjoxNjkxMDAyNjIzLCJqdGkiOiI1MjBiN2RhNC0xYmM0LTRiM2QtODY2ZC00NDU0ODY2YThiYjIiLCJpc3MiOiJodHRwczovL2Rldi5hdXRoLnBsYW40YmV0dGVyLmRlL3JlYWxtcy9tYXN0ZXIiLCJzdWIiOiI3NDRlNGZkMS02ODVjLTQ5NWMtOGIwMi1lZmViY2U4NzUzNTkiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJzZWN1cml0eS1hZG1pbi1jb25zb2xlIiwibm9uY2UiOiJjNGIzMDQ3Yi0xODVmLTQyOWEtOGZlNS1lNDliNTVhMzE3MzIiLCJzZXNzaW9uX3N0YXRlIjoiMzk5ZTc2NWMtYjM1MC00NDEwLTg4YTMtYjU5NDIyMmJkZDlhIiwiYWNyIjoiMCIsImFsbG93ZWQtb3JpZ2lucyI6WyJodHRwczovL2Rldi5hdXRoLnBsYW40YmV0dGVyLmRlIl0sInNjb3BlIjoib3BlbmlkIGVtYWlsIHByb2ZpbGUiLCJzaWQiOiIzOTllNzY1Yy1iMzUwLTQ0MTAtODhhMy1iNTk0MjIyYmRkOWEiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInByZWZlcnJlZF91c2VybmFtZSI6InA0YiJ9.mjywr9Dv19egsXwM1fK6g3sZ0trk87X0tEfK7oOizuBuCdkr6PZN1Eg58FCdjIgEBXqjltOWV43UIkXde4iPVa-KU5Q34Qjv6w0STa3Aq9vFbaUfSm_690qCdr8XSKMJUWQXWYwD2cjck5UCqf7-QqsF2Ab56i40_CJLZkJOi25WKIC855qPDi8BkJgh5eWoxobdyCbwJMEeoM-3QnxY5ikib5a2_AASEN3_5MYmT6-fvpW2t-MS6u4vtcG-WfqriK8YNoGPS2a1pFjLqQLHkM__j0O_t4wXP56x9yjkUdHCXqVcSlDvZYNWrv5CLqecqjOoliNMs6RTu9gV0Gr-cA"
    KEYCLOAK_SERVER_URL: Optional[str] = "http://auth-keycloak:8080"
    REALM_NAME: Optional[str] = "p4b"
    CELERY_TASK_TIME_LIMIT: Optional[int] = 60  # seconds
    RUN_AS_BACKGROUND_TASK: Optional[bool] = True
    MAX_NUMBER_PARALLEL_JOBS: Optional[int] = 6
    TESTING: Optional[bool] = False
    MAX_FOLDER_COUNT: Optional[int] = 100

    MAPBOX_TOKEN: Optional[str] = None
    MAPTILER_TOKEN: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = "eu-central-1"
    AWS_S3_ASSETS_BUCKET: Optional[str] = "plan4better-assets"
    S3_CLIENT: Optional[Any] = None

    @validator("S3_CLIENT", pre=True)
    def assemble_s3_client(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return boto3.client(
            "s3",
            aws_access_key_id=values.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=values.get("AWS_SECRET_ACCESS_KEY"),
            region_name=values.get("AWS_REGION"),
        )

    DEFAULT_PROJECT_THUMBNAIL: Optional[str] = (
        "https://assets.plan4better.de/img/goat_new_project_artwork.png"
    )
    DEFAULT_LAYER_THUMBNAIL: Optional[str] = (
        "https://assets.plan4better.de/img/goat_new_dataset_thumbnail.png"
    )
    DEFAULT_REPORT_THUMBNAIL: Optional[str] = (
        "https://goat-app-assets.s3.eu-central-1.amazonaws.com/logos/goat_green.png"
    )
    ASSETS_URL: Optional[str] = None
    THUMBNAIL_DIR_LAYER: Optional[str] = None

    @validator("THUMBNAIL_DIR_LAYER", pre=True)
    def set_thumbnail_dir_layer(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        environment = values.get("ENVIRONMENT", "dev")
        if v is None:
            return f"img/users/{environment}/thumbnails/layer"
        return v

    THUMBNAIL_DIR_PROJECT: Optional[str] = None

    @validator("THUMBNAIL_DIR_PROJECT", pre=True)
    def set_thumbnail_dir_project(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        environment = values.get("ENVIRONMENT", "dev")
        if v is None:
            return f"img/users/{environment}/thumbnails/project"
        return v

    MARKER_DIR: Optional[str] = "icons/maki"
    MARKER_PREFIX: Optional[str] = "goat-marker-"

    class Config:
        case_sensitive = True


settings = Settings()
