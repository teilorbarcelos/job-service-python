import os
import subprocess
import sys

from src.infra.database.db import get_session
from src.shared.utils.logging import get_logger
from src.shared.utils.seed_helpers import seed_admin, seed_features, seed_roles

logger = get_logger("bootstrap")


async def run_migrations():
    logger.info("Running database migrations...")
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "heads"], cwd=root_dir, check=True)
        logger.info("Migrations applied successfully.")
    except Exception as e:
        logger.error(f"Failed to apply migrations: {e}")


async def bootstrap_system():

    await run_migrations()

    async with get_session() as session:
        await seed_features(session)
        await seed_roles(session)
        await seed_admin(session)
        await session.commit()
