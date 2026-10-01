from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ems_common.config import CommonSettings


class EmployeeSettings(CommonSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/employee_db",
        description="Async PostgreSQL DSN",
    )
    AUTH_SERVICE_URL: str = Field(
        default="http://localhost:8001",
        description="Auth service base URL",
    )
    PAYROLL_SERVICE_URL: str = Field(
        default="http://localhost:8004",
        description="Payroll service base URL",
    )
    OUTBOX_PUBLISHER_ENABLED: bool = Field(
        default=True,
        description="Whether to run outbox publisher background loop",
    )


settings = EmployeeSettings()
