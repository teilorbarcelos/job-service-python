from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    port: int = Field(default=8888, alias="PORT")
    first_user: str = Field(default="admin@email.com", alias="FIRST_USER")
    first_password: str = Field(default="admin123", alias="FIRST_PASSWORD")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    rate_limit_max: int = Field(default=60, alias="RATE_LIMIT_MAX")
    rate_limit_window: int = Field(default=60, alias="RATE_LIMIT_WINDOW")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    app_deploy_timestamp: str = Field(default="unknown", alias="APP_DEPLOY_TIMESTAMP")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    auth_mode: str = Field(default="local", alias="AUTH_MODE")
    auth_service_url: str = Field(default="http://localhost:8001", alias="AUTH_SERVICE_URL")

    jwt_issuer: str = Field(default="backend-python", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="backend-python-api", alias="JWT_AUDIENCE")
    jwt_access_expiration_hours: int = Field(default=24, alias="JWT_ACCESS_EXPIRATION_HOURS")
    jwt_refresh_expiration_days: int = Field(default=7, alias="JWT_REFRESH_EXPIRATION_DAYS")
    password_bcrypt_cost: int = Field(default=12, alias="PASSWORD_BCRYPT_COST")
    cors_allowed_origins: str = Field(default="http://localhost:3000", alias="CORS_ALLOWED_ORIGINS")
    db_pool_size: int = Field(default=25, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=25, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=3600, alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")

    messaging_enabled: bool = Field(default=False, alias="MESSAGING_ENABLED")
    rabbit_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBIT_URL")
    rabbit_user: str = Field(default="guest", alias="RABBIT_USER")
    rabbit_password: str = Field(default="guest", alias="RABBIT_PASSWORD")

    storage_disk: str = Field(default="local", alias="STORAGE_DISK")
    storage_path: str = Field(default="./storage/app", alias="STORAGE_PATH")
    storage_url: str = Field(default="http://localhost:8888/storage", alias="STORAGE_URL")

    s3_key: str = Field(default="", alias="S3_KEY")
    s3_secret: str = Field(default="", alias="S3_SECRET")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_bucket: str = Field(default="", alias="S3_BUCKET")

    gcs_key_file: str = Field(default="", alias="GCS_KEY_FILE")
    gcs_bucket: str = Field(default="", alias="GCS_BUCKET")

    azure_connection_string: str = Field(default="", alias="AZURE_CONNECTION_STRING")
    azure_container: str = Field(default="", alias="AZURE_CONTAINER")
    pdf_service_url: str = Field(default="http://localhost:8889", alias="PDF_SERVICE_URL")

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str, info):
        if info.data.get("environment") == "production" and len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters in production")
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
