"""Tests for the Settings class (pydantic-settings)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.shared.config.settings import Settings, build_settings


def test_settings_uses_defaults_when_no_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    # Wipe any env vars that could influence the test
    for key in (
        "ENVIRONMENT",
        "LOG_LEVEL",
        "SHUTDOWN_TIMEOUT_S",
        "JOB_EXECUTION_TIMEOUT_S",
        "DATABASE_URL",
        "DATABASE_POOL_MAX",
        "DATABASE_COMMAND_TIMEOUT_S",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "REDIS_DB",
        "REDIS_COMMAND_TIMEOUT_S",
        "MESSAGING_ENABLED",
        "RABBIT_URL",
        "RABBIT_USER",
        "RABBIT_PASSWORD",
        "RABBITMQ_PUBLISH_TIMEOUT",
        "HEALTH_CHECK_CRON",
        "HEALTH_CHECK_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    s = build_settings()
    assert s.environment == "local"
    assert s.log_level == "INFO"
    assert s.shutdown_timeout_s == 30.0
    assert s.job_execution_timeout_s == 300.0
    assert s.database_pool_max == 20
    assert s.database_command_timeout_s == 10.0
    assert s.redis_host == "localhost"
    assert s.redis_port == 6379
    assert s.redis_password == ""
    assert s.redis_db == 0
    assert s.redis_command_timeout_s == 5.0
    assert s.messaging_enabled is False
    assert s.rabbit_url.startswith("amqp://")
    assert "@localhost:5672/" in s.rabbit_url
    assert s.rabbit_user == "guest"
    assert s.rabbit_password == "guest"
    assert s.rabbit_publish_timeout_s == 5.0
    assert s.health_check_cron == "*/1 * * * *"
    assert s.health_check_enabled is True


def test_settings_database_url_default_used_when_env_var_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = build_settings()
    assert s.database_url == "postgresql+asyncpg://postgres:postgrespw@localhost:5432/backend_python"


def test_settings_database_url_env_var_overrides_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://custom:secret@custom:5433/custom_db")
    s = build_settings()
    assert s.database_url == "postgresql+asyncpg://custom:secret@custom:5433/custom_db"


def test_settings_messaging_enabled_coerces_string_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESSAGING_ENABLED", "true")
    s = build_settings()
    assert s.messaging_enabled is True


def test_settings_messaging_enabled_coerces_string_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESSAGING_ENABLED", "false")
    s = build_settings()
    assert s.messaging_enabled is False


def test_settings_health_check_enabled_coerces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEALTH_CHECK_ENABLED", "false")
    s = build_settings()
    assert s.health_check_enabled is False


def test_settings_cron_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEALTH_CHECK_CRON", "0 0 * * *")
    s = build_settings()
    assert s.health_check_cron == "0 0 * * *"


def test_settings_pool_sizes_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_POOL_MAX", "50")
    monkeypatch.setenv("REDIS_PORT", "7000")
    s = build_settings()
    assert s.database_pool_max == 50
    assert s.redis_port == 7000


def test_settings_validates_rabbit_url_required_when_messaging_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MESSAGING_ENABLED", "true")
    monkeypatch.setenv("RABBIT_URL", "")
    with pytest.raises(ValidationError, match="RABBIT_URL is required"):
        build_settings()


def test_settings_does_not_require_rabbit_url_when_messaging_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MESSAGING_ENABLED", "false")
    monkeypatch.setenv("RABBIT_URL", "")
    s = build_settings()
    assert s.messaging_enabled is False
    assert s.rabbit_url == ""


def test_settings_log_level_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = build_settings()
    assert s.log_level == "DEBUG"


def test_settings_is_constructible_multiple_times(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each call to build_settings() returns a fresh instance with current env."""
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    a = build_settings()
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    b = build_settings()
    assert a.log_level == "INFO"
    assert b.log_level == "ERROR"


def test_settings_uses_default_factory_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings() with no env override works because of Field defaults."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DATABASE_POOL_MAX", raising=False)
    s = Settings(_env_file=None)  # bypass .env file
    assert s.environment == "local"
    assert s.database_pool_max == 20
