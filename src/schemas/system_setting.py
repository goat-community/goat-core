from uuid import UUID
from pydantic import Field
from src.db.models.system_setting import SystemSetting, SystemSettingBase
from src.utils import optional


class SystemSettingsRead(SystemSetting):
    pass


@optional
class SystemSettingsUpdate(SystemSettingBase):
    pass


class SystemSettingsCreate(SystemSettingBase):
    user_id: UUID | None = Field(None, description="System settings owner ID")


default_system_settings = SystemSettingsCreate(
    client_theme="dark",
    preferred_language="de",
    unit="metric",
)

# Body of request examples
request_examples = {
    "create": {"client_theme": "dark", "preferred_language": "en", "unit": "metric"},
    "update": {
        "client_theme": "light",
        "preferred_language": "de",
        "unit": "imperial",
    },
}
