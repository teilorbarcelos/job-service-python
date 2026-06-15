import asyncio
from src.modules.user.user_service import user_service

async def test_nested_filter():
    # Filter users where role name contains 'Admin'
    filters = {
        "page": 0,
        "size": 10,
        "role.name": "Admin"
    }
    
    print(f"Testing with nested filter: {filters}")
    result = await user_service.list_all_items(filters)
    
    print(f"Total users found: {result['total']}")
    for user in result['items']:
        print(f"Found user: {user['name']} (Email: {user['email']})")

if __name__ == "__main__":
    asyncio.run(test_nested_filter())
