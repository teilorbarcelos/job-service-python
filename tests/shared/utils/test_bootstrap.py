import pytest
from src.shared.utils.bootstrap import bootstrap_system, run_migrations
from src.infra.database.models import User, Role, Feature
from sqlalchemy import select
from src.shared.config.settings import settings
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
class TestBootstrapUtility:
    async def test_should_populate_features_and_roles(self, session):
        await bootstrap_system()
        features = (await session.execute(select(Feature))).scalars().all()
        assert len(features) >= 3
        assert any(f.id == "product" for f in features)

        roles = (await session.execute(select(Role))).scalars().all()
        assert len(roles) >= 2
        assert any(r.id == "administrator" for r in roles)

    async def test_should_create_admin_user_from_settings(self, session):
        settings.first_user = "testadmin@email.com"
        settings.first_password = "password123"
        await bootstrap_system()

        stmt = select(User).where(User.email == "testadmin@email.com")
        user = (await session.execute(stmt)).scalar_one_or_none()
        assert user is not None
        assert user.name == "Admin"
        assert user.id_role == "administrator"

    async def test_should_not_duplicate_admin_user(self, session):
        settings.first_user = "unique@email.com"
        settings.first_password = "password123"
        await bootstrap_system()
        await bootstrap_system()

        stmt = select(User).where(User.email == "unique@email.com")
        users = (await session.execute(stmt)).scalars().all()
        assert len(users) == 1

    async def test_run_migrations_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Migration Failed")
            await run_migrations()
            mock_run.assert_called_once()

    async def test_run_migrations_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            await run_migrations()
            mock_run.assert_called_once()
