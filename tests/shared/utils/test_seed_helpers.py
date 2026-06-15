import pytest
from unittest.mock import patch, MagicMock
from src.shared.utils.seed_helpers import seed_admin


@pytest.mark.asyncio
async def test_seed_admin_missing_config():

    with patch("src.shared.utils.seed_helpers.settings") as mock_settings:
        mock_settings.first_user = None
        mock_settings.first_password = None

        session = MagicMock()
        await seed_admin(session)

        assert not session.execute.called
