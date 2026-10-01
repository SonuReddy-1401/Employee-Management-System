from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ems_common.config import CommonSettings


class AuthSettings(CommonSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/auth_db",
        description="Async PostgreSQL DSN",
    )
    JWT_EXPIRY_MINUTES: int = 60
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None


settings = AuthSettings()
