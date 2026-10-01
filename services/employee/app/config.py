from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ems_common.config import CommonSettings


class EmployeeSettings(CommonSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/employee_db",
        description="Async PostgreSQL DSN",
    )


settings = EmployeeSettings()
