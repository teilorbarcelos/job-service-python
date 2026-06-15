import asyncio
from sqlalchemy import select
from src.infra.database.models import User
from src.modules.user.user_repository import UserRepository
from src.infra.database.db import engine, SessionLocal

async def test_filter():
    repo = UserRepository()
    filters = {"andRules": [{"key": "name", "qt": "contains", "search": "admin"}]}
    stmt = select(User)
    stmt = repo._apply_filters(stmt, filters)
    print(f"Generated SQL: {stmt}")

if __name__ == "__main__":
    asyncio.run(test_filter())
