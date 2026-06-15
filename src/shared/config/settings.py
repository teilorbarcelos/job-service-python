r"""Settings for the job service.

Pydantic-Settings reads from environment variables (and optionally from
`.env`). The shape is deliberately narrow: only what the job runner needs
to connect to PostgreSQL, Redis, and RabbitMQ and to schedule itself.

If a required-for-connection variable is missing, a sensible default is
provided so the service can boot without a `.env` file. The defaults
match the local infra used by \`backend-python\`:

- DATABASE_URL  → postgresql+asyncpg://postgres:postgrespw@localhost:5432/backend_python
- REDIS_HOST    → localhost
- RABBIT_URL    → amqp://guest:guest@localhost:5672/

For production, override via env or \`.env\`.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    shutdown_timeout_s: float = Field(default=30.0, alias="SHUTDOWN_TIMEOUT_S")
    job_execution_timeout_s: float = Field(default=300.0, alias="JOB_EXECUTION_TIMEOUT_S")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgrespw@localhost:5432/backend_python",
        alias="DATABASE_URL",
    )
    database_pool_max: int = Field(default=20, alias="DATABASE_POOL_MAX")
    database_command_timeout_s: float = Field(default=10.0, alias="DATABASE_COMMAND_TIMEOUT_S")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_command_timeout_s: float = Field(default=5.0, alias="REDIS_COMMAND_TIMEOUT_S")

    messaging_enabled: bool = Field(default=False, alias="MESSAGING_ENABLED")
    rabbit_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBIT_URL")
    rabbit_user: str = Field(default="guest", alias="RABBIT_USER")
    rabbit_password: str = Field(default="guest", alias="RABBIT_PASSWORD")
    rabbit_publish_timeout_s: float = Field(default=5.0, alias="RABBITMQ_PUBLISH_TIMEOUT")

    health_check_cron: str = Field(default="*/1 * * * *", alias="HEALTH_CHECK_CRON")
    health_check_enabled: bool = Field(default=True, alias="HEALTH_CHECK_ENABLED")

    @model_validator(mode="after")
    def _check_rabbit_when_messaging_enabled(self) -> Settings:
        if self.messaging_enabled and not self.rabbit_url:
            raise ValueError("RABBIT_URL is required when MESSAGING_ENABLED=true")
        return self


def build_settings() -> Settings:
    r"""Factory for fresh Settings instances.

    Bypasses the `.env` file so callers (mainly tests) see only
    what's in the current process environment. Production code that
    wants the `.env` file should instantiate `Settings()` directly.
    """
    return Settings(_env_file=None)  # type: ignore[call-arg]


settings: Settings = Settings()
