import pytest
from src.infra.database.models import ErrorLog, Audit, Role
from sqlalchemy import select
from unittest.mock import patch, AsyncMock
from src.modules.audit.audit_service import audit_service


@pytest.mark.asyncio
async def test_should_log_error_to_db_on_exception(client, session):
    with patch("src.modules.user.user_service.UserService.create", side_effect=ValueError("Simulated Crash")):
        from src.infra.auth.auth_provider import auth_provider

        token = auth_provider.generate_token({"id": "admin", "name": "Admin User", "email": "admin@test.com", "roleId": "administrator"})
        try:
            await client.post(
                "/v1/user",
                json={"name": "Crash", "email": "crash@test.com", "id_role": "admin"},
                headers={"Authorization": f"Bearer {token}"},
            )
        except ValueError:
            pass

        stmt = select(ErrorLog).where(ErrorLog.error_message == "Simulated Crash")
        result = await session.execute(stmt)
        error_log = result.scalar_one_or_none()
        assert error_log is not None
        assert error_log.id_user == "admin"


@pytest.mark.asyncio
async def test_should_log_audit_with_details(client, session):
    from src.infra.auth.auth_provider import auth_provider

    token = auth_provider.generate_token(
        {"id": "audit-user", "name": "Audit User", "email": "audit-test@test.com", "roleId": "administrator"}
    )
    response = await client.get("/v1/user?page=1&size=10", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    from src.infra.outbox.outbox_service import outbox_service
    await outbox_service.process_pending()

    stmt = select(Audit).where(Audit.id_user == "audit-user", Audit.method == "GET")
    result = await session.execute(stmt)
    audit_log = result.scalar_one_or_none()
    assert audit_log is not None
    assert "page" in audit_log.params

    session.add(Role(id="administrator", name="Admin", description="D", active=True))
    await session.commit()
    post_data = {"name": "Audit Body", "email": "body@test.com", "id_role": "administrator"}
    await client.post("/v1/user", json=post_data, headers={"Authorization": f"Bearer {token}"})

    await outbox_service.process_pending()

    stmt = select(Audit).where(Audit.id_user == "audit-user", Audit.method == "POST")
    result = await session.execute(stmt)
    audit_log_post = result.scalar_one_or_none()
    assert audit_log_post is not None
    assert "Audit Body" in audit_log_post.raw


@pytest.mark.asyncio
async def test_should_not_log_if_not_authenticated(client, session):
    await client.get("/v1/user")
    stmt = select(Audit)
    result = await session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_audit_service_save_audit_failure_coverage():
    with patch("src.modules.audit.audit_service.get_session") as mock_session:
        mock_session.side_effect = Exception("DB error")
        await audit_service.save_audit({"data": "test"})


@pytest.mark.asyncio
async def test_audit_service_save_error_log_failure_coverage():
    with patch("src.modules.audit.audit_service.get_session") as mock_session:
        mock_session.side_effect = Exception("DB error")
        await audit_service.save_error_log({"data": "test"})
