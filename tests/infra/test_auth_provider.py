import pytest
from src.infra.auth.auth_provider import JWTAuthProvider


@pytest.fixture
def auth_provider():

    return JWTAuthProvider(secret="test-secret")


def test_should_generate_a_token(auth_provider):
    payload = {"id": "1", "email": "test@test.com", "roleId": "role-1"}
    token = auth_provider.generate_token(payload)
    assert isinstance(token, str)
    assert len(token) > 0


def test_should_generate_a_token_pair(auth_provider):
    payload = {"id": "1", "email": "test@test.com", "roleId": "role-1"}
    pair = auth_provider.generate_token_pair(payload)
    assert "token" in pair
    assert "refreshToken" in pair
    assert isinstance(pair["token"], str)
    assert isinstance(pair["refreshToken"], str)


def test_should_verify_a_token(auth_provider):
    payload = {"id": "1", "email": "test@test.com", "roleId": "role-1"}
    token = auth_provider.generate_token(payload)

    result = auth_provider.verify_token(token)
    assert result["id"] == "1"
    assert result["email"] == "test@test.com"


def test_should_return_none_for_invalid_token(auth_provider):
    assert auth_provider.verify_token("invalid-token") is None


def test_should_return_none_for_expired_token(auth_provider):
    import time
    import jwt

    payload = {"id": "1", "email": "test@test.com", "roleId": "role-1", "exp": int(time.time()) - 10}
    token = jwt.encode(payload, auth_provider.secret, algorithm="HS256")
    assert auth_provider.verify_token(token) is None


def test_token_pair_includes_ver(auth_provider):
    pair = auth_provider.generate_token_pair({"id": "1"}, ver=2)
    decoded = auth_provider.verify_token(pair["token"])
    assert decoded.get("ver") == 2
    decoded_refresh = auth_provider.verify_token(pair["refreshToken"])
    assert decoded_refresh.get("ver") == 2
    assert decoded_refresh.get("type") == "refresh"
