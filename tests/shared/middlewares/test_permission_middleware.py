import pytest
from fastapi import HTTPException
from src.shared.middlewares.permission_middleware import check_permission


@pytest.mark.asyncio
class TestPermissionMiddleware:
    async def test_should_allow_administrator_bypass(self):

        payload = {"roleId": "administrator"}
        dependency = check_permission("any-feature", "any-action")

        result = await dependency(payload)
        assert result == payload

    async def test_should_allow_user_with_specific_permission(self):
        payload = {"roleId": "operator", "permissions": [{"feature": "role", "view": True, "create": False}]}
        dependency = check_permission("role", "view")

        result = await dependency(payload)
        assert result == payload

    async def test_should_deny_user_without_specific_permission(self):
        payload = {"roleId": "operator", "permissions": [{"feature": "role", "view": True, "create": False}]}
        dependency = check_permission("role", "create")

        with pytest.raises(HTTPException) as exc:
            await dependency(payload)

        assert exc.value.status_code == 403
        assert "Permission denied" in exc.value.detail

    async def test_should_deny_user_with_no_permissions_for_feature(self):
        payload = {"roleId": "operator", "permissions": [{"feature": "other", "view": True}]}
        dependency = check_permission("role", "view")

        with pytest.raises(HTTPException) as exc:
            await dependency(payload)

        assert exc.value.status_code == 403

    async def test_should_deny_user_with_empty_permissions(self):
        payload = {"roleId": "operator", "permissions": []}
        dependency = check_permission("role", "view")

        with pytest.raises(HTTPException) as exc:
            await dependency(payload)

        assert exc.value.status_code == 403

    async def test_should_handle_missing_permissions_key(self):
        payload = {"roleId": "operator"}
        dependency = check_permission("role", "view")

        with pytest.raises(HTTPException) as exc:
            await dependency(payload)

        assert exc.value.status_code == 403
