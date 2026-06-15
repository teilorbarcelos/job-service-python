import asyncio
from src.modules.role.role_service import role_service
from datetime import datetime

async def test_date_range():
    # Mocking filters from URL
    filters = {
        "page": 0,
        "size": 25,
        "active": True,
        "createdAt_start": "2026-05-01",
        "createdAt_end": "2026-05-05",
        "orderBy": "name",
        "orderDirection": "asc"
    }
    
    print(f"Testing with filters: {filters}")
    result = await role_service.list_all_items(filters)
    
    print(f"Total items found: {result['total']}")
    for item in result['items']:
        print(f"Found item: {item['name']} created at {item['created_at']}")

if __name__ == "__main__":
    asyncio.run(test_date_range())
