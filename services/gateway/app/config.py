from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    EMPLOYEE_SERVICE_URL: str = "http://localhost:8002"
    LEAVE_SERVICE_URL: str = "http://localhost:8003"
    PAYROLL_SERVICE_URL: str = "http://localhost:8004"
    NOTIFICATION_SERVICE_URL: str = "http://localhost:8005"

    UPSTREAM_TIMEOUT_SECONDS: float = 10.0
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_REQUESTS: int = 10

    JWT_SECRET: str = "default_jwt_secret_change_me_in_prod"
    JWT_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
