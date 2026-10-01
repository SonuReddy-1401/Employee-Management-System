from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ems_common.config import CommonSettings


class PayrollSettings(CommonSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/payroll_db",
        description="Async PostgreSQL DSN",
    )
    CONSUMER_ENABLED: bool = False
    PAYROLL_QUEUE_NAME: str = "ems.payroll.queue"
    PAYROLL_DLQ_NAME: str = "ems.payroll.dlq"
    PAYROLL_DLX_NAME: str = "ems.payroll.dlx"


settings = PayrollSettings()
