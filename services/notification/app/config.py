from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ems_common.config import CommonSettings


class NotificationSettings(CommonSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/notification_db",
        description="Async PostgreSQL DSN",
    )
    CONSUMER_ENABLED: bool = False
    NOTIFICATION_QUEUE_NAME: str = "ems.notification.queue"
    NOTIFICATION_DLQ_NAME: str = "ems.notification.dlq"
    NOTIFICATION_DLX_NAME: str = "ems.notification.dlx"


settings = NotificationSettings()
