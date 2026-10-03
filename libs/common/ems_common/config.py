from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    JWT_SECRET: str = "default_jwt_secret_change_me_in_prod"
    JWT_ALGORITHM: str = "HS256"

    # HTTP Client Config
    HTTP_CLIENT_TIMEOUT_SECONDS: float = 5.0
    HTTP_CLIENT_RETRY_COUNT: int = 3
    HTTP_CLIENT_BACKOFF_FACTOR: float = 0.5
    HTTP_CLIENT_BREAKER_FAIL_THRESHOLD: int = 5
    HTTP_CLIENT_BREAKER_RESET_TIMEOUT_SECONDS: float = 30.0

    # Outbox Publisher Config
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "ems.events"

    # Idempotent Consumer Config
    CONSUMER_QUEUE_NAME: str = "ems.queue"
    CONSUMER_DLQ_NAME: str = "ems.dlq"
    CONSUMER_MAX_ATTEMPTS: int = 3
    CONSUMER_RECONNECT_INITIAL_DELAY_SECONDS: float = 1.0
    CONSUMER_RECONNECT_MAX_DELAY_SECONDS: float = 30.0
    CONSUMER_CONNECT_TIMEOUT_SECONDS: float = 5.0
    CONSUMER_STOP_POLL_SECONDS: float = 1.0




settings = CommonSettings()
