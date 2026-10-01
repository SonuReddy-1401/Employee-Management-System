from pydantic_settings import BaseSettings, SettingsConfigDict


class LeaveSettings(BaseSettings):
    SERVICE_NAME: str = "leave-service"
    PORT: int = 8003
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ems_leave"
    REDIS_URL: str = "redis://localhost:6379/0"
    EMPLOYEE_SERVICE_URL: str = "http://localhost:8002"
    EMPLOYEE_CACHE_TTL_SECONDS: int = 60
    ANNUAL_PAID_LEAVE_DAYS: int = 20
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    OUTBOX_PUBLISHER_ENABLED: bool = True

    JWT_SECRET: str = "default_jwt_secret_change_me_in_prod"
    JWT_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = LeaveSettings()
