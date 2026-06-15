import pytest

from src.shared.config.settings import Settings


def test_validate_jwt_secret_rejects_short_in_production():
    info = type("Info", (), {"data": {"environment": "production"}})
    with pytest.raises(ValueError, match="JWT_SECRET must be at least 32"):
        Settings.validate_jwt_secret("short", info())


def test_validate_jwt_secret_accepts_long_in_production():
    info = type("Info", (), {"data": {"environment": "production"}})
    result = Settings.validate_jwt_secret("a" * 32, info())
    assert result == "a" * 32


def test_validate_jwt_secret_accepts_short_in_local():
    info = type("Info", (), {"data": {"environment": "local"}})
    result = Settings.validate_jwt_secret("short", info())
    assert result == "short"
