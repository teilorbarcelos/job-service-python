import asyncio
from src.modules.role.role_service import role_service

async def main():
    try:
        print("Buscando roles...")
        roles = await role_service.list_all_items({})
        print(f"Resultado: {roles}")
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
