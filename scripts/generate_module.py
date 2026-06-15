import os
import sys
import re

def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def generate_module(module_name):
    module_snake = camel_to_snake(module_name)
    module_dir = f"src/modules/{module_snake}"
    
    if os.path.exists(module_dir):
        print(f"Error: Module {module_snake} already exists.")
        sys.exit(1)
        
    os.makedirs(module_dir, exist_ok=True)
    
    # Templates
    templates = {
        "models.py": f"""from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
import uuid
from src.infra.database.base import Base, TimestampMixin

class {module_name}(Base, TimestampMixin):
    __tablename__ = "{module_snake}"
    
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
""",
        f"{module_snake}_repository.py": f"""from src.core.base_repository import BaseRepository
from src.infra.database.models import {module_name}
from src.infra.database.db import SessionLocal

class {module_name}Repository(BaseRepository[{module_name}]):
    def __init__(self):
        super().__init__(model={module_name}, session_factory=SessionLocal)
""",
        f"{module_snake}_service.py": f"""from src.core.base_service import BaseService
from src.modules.{module_snake}.{module_snake}_repository import {module_name}Repository

class {module_name}Service(BaseService):
    def __init__(self):
        super().__init__({module_name}Repository())
        self.allow_filters([
            {{"key": "name", "qt": "contains"}},
            {{"key": "active"}}
        ])
        self.allow_search([
            {{"key": "name"}}
        ])

{module_snake}_service = {module_name}Service()
""",
        "schemas.py": f"""from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class {module_name}Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Create{module_name}Dto(BaseModel):
    name: str

class Update{module_name}Dto(BaseModel):
    name: Optional[str] = None

class ToggleStatusDto(BaseModel):
    active: bool
""",
        "router.py": f"""from fastapi import APIRouter, Depends, HTTPException, Request
from src.modules.{module_snake}.{module_snake}_service import {module_snake}_service
from src.modules.{module_snake}.schemas import {module_name}Schema, Create{module_name}Dto, Update{module_name}Dto, ToggleStatusDto
from src.shared.middlewares.permission_middleware import check_permission
from src.shared.schemas.generic_schema import PaginatedResponse

router = APIRouter(prefix="/v1/{module_snake}", tags=["{module_snake}"])

@router.post("", status_code=201, response_model={module_name}Schema)
async def create_{module_snake}(req: Create{module_name}Dto, _=Depends(check_permission("{module_snake}", "create"))):
    return await {module_snake}_service.create(req.model_dump())

@router.get("", response_model=PaginatedResponse[{module_name}Schema])
async def list_{module_snake}s(request: Request, _=Depends(check_permission("{module_snake}", "view"))):
    return await {module_snake}_service.list_items(dict(request.query_params))

@router.get("/all", response_model=PaginatedResponse[{module_name}Schema])
async def list_all_{module_snake}s(request: Request, _=Depends(check_permission("{module_snake}", "view"))):
    return await {module_snake}_service.list_all_items(dict(request.query_params))

@router.get("/{{id}}", response_model={module_name}Schema)
async def get_{module_snake}(id: str, _=Depends(check_permission("{module_snake}", "view"))):
    item = await {module_snake}_service.repo.find_one_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="{module_name} not found")
    return item

@router.put("/{{id}}", response_model={module_name}Schema)
async def update_{module_snake}(id: str, req: Update{module_name}Dto, _=Depends(check_permission("{module_snake}", "create"))):
    return await {module_snake}_service.update(id, req.model_dump(exclude_unset=True))

@router.delete("/{{id}}", status_code=204)
async def delete_{module_snake}(id: str, _=Depends(check_permission("{module_snake}", "delete"))):
    await {module_snake}_service.delete(id)
    return None

@router.patch("/{{id}}/status", response_model={module_name}Schema)
async def toggle_status(id: str, req: ToggleStatusDto, _=Depends(check_permission("{module_snake}", "activate"))):
    result = await {module_snake}_service.set_status(id, req.active)
    if not result:
        raise HTTPException(status_code=404, detail="{module_name} not found")
    return result
"""
    }
    
    for filename, content in templates.items():
        with open(f"{module_dir}/{filename}", "w") as f:
            f.write(content)
        print(f"Created: {module_dir}/{filename}")

    # Generate Test
    test_template = f"""import pytest
import uuid
from httpx import AsyncClient
from src.infra.database.models import {module_name}
from src.shared.middlewares.auth_middleware import check_auth
from src.main import app

@pytest.mark.asyncio
class Test{module_name}Endpoints:

    @pytest.fixture(autouse=True)
    def setup_auth_override(self, mocker):
        app.dependency_overrides[check_auth] = lambda: {{"id": "admin-id", "email": "admin@email.com", "roleId": "administrator"}}
        yield
        app.dependency_overrides.clear()

    async def test_should_create_a_{module_snake}(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        payload = {{
            "name": f"{module_name} {{uid}}"
        }}
        response = await client.post("/v1/{module_snake}", json=payload, headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 201
        assert response.json()["name"] == f"{module_name} {{uid}}"

    async def test_should_list_{module_snake}s_with_pagination(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add({module_name}(id=f"p1_{{uid}}", name="P1"))
        session.add({module_name}(id=f"p2_{{uid}}", name="P2"))
        await session.commit()

        response = await client.get("/v1/{module_snake}?page=0&size=10", headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2

    async def test_should_list_all_{module_snake}s(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add({module_name}(id=f"all1_{{uid}}", name="A1"))
        await session.commit()

        response = await client.get("/v1/{module_snake}/all", headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

    async def test_should_get_{module_snake}_by_id(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        item = {module_name}(id=f"get_{{uid}}", name="Get Me")
        session.add(item)
        await session.commit()

        response = await client.get(f"/v1/{module_snake}/get_{{uid}}", headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 200
        assert response.json()["name"] == "Get Me"

    async def test_should_return_404_when_get_non_existent_{module_snake}(self, client: AsyncClient, session):
        response = await client.get("/v1/{module_snake}/non-existent", headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 404

    async def test_should_update_{module_snake}(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        item = {module_name}(id=f"upd_{{uid}}", name="Old")
        session.add(item)
        await session.commit()

        payload = {{"name": "Updated Name"}}
        response = await client.put(f"/v1/{module_snake}/upd_{{uid}}", json=payload, headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    async def test_should_delete_{module_snake}(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        item = {module_name}(id=f"del_{{uid}}", name="Del")
        session.add(item)
        await session.commit()

        response = await client.delete(f"/v1/{module_snake}/del_{{uid}}", headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 204

    async def test_should_toggle_{module_snake}_status(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        item = {module_name}(id=f"tog_{{uid}}", name="Tog", active=True)
        session.add(item)
        await session.commit()

        response = await client.patch(f"/v1/{module_snake}/tog_{{uid}}/status", json={{"active": False}}, headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 200
        assert response.json()["active"] is False

    async def test_should_return_404_when_toggle_non_existent_{module_snake}_status(self, client: AsyncClient, session):
        response = await client.patch("/v1/{module_snake}/non-existent/status", json={{"active": False}}, headers={{"Authorization": "Bearer token"}})
        assert response.status_code == 404

    async def test_router_functions_directly_for_coverage(self, session):
        # This test calls the router functions directly to ensure 100% coverage
        # bypassing any potential middleware instrumentation issues.
        from src.modules.{module_snake}.router import get_{module_snake}, delete_{module_snake}, toggle_status, create_{module_snake}, list_{module_snake}s, list_all_{module_snake}s
        from src.modules.{module_snake}.schemas import Create{module_name}Dto, Update{module_name}Dto, ToggleStatusDto
        from fastapi import HTTPException
        from unittest.mock import MagicMock

        mock_req = MagicMock()
        mock_req.query_params = {{}}
        admin_payload = {{"roleId": "administrator", "email": "admin@test.com"}}

        # Test create
        res = await create_{module_snake}(Create{module_name}Dto(name="Direct"), _=admin_payload)
        assert res["name"] == "Direct"

        # Test list
        res = await list_{module_snake}s(mock_req, _=admin_payload)
        assert "items" in res

        # Test list all
        res = await list_all_{module_snake}s(mock_req, _=admin_payload)
        assert "items" in res

        # Test get non-existent
        with pytest.raises(HTTPException) as exc:
            await get_{module_snake}("missing_id", _=admin_payload)
        assert exc.value.status_code == 404

        # Test get success
        uid = str(uuid.uuid4())[:8]
        item = {module_name}(id=f"direct_{{uid}}", name="Direct Get")
        session.add(item)
        await session.commit()
        res = await get_{module_snake}(f"direct_{{uid}}", _=admin_payload)
        assert res["name"] == "Direct Get"

        # Test delete
        res = await delete_{module_snake}(f"direct_{{uid}}", _=admin_payload)
        assert res is None

        # Test toggle success
        uid2 = str(uuid.uuid4())[:8]
        item2 = {module_name}(id=f"direct_tog_{{uid2}}", name="Direct Tog")
        session.add(item2)
        await session.commit()
        res = await toggle_status(f"direct_tog_{{uid2}}", ToggleStatusDto(active=False), _=admin_payload)
        assert res["active"] is False

        # Test toggle non-existent
        with pytest.raises(HTTPException) as exc:
            await toggle_status("missing_tog", ToggleStatusDto(active=False), _=admin_payload)
        assert exc.value.status_code == 404
"""
    test_file_path = f"tests/modules/{module_snake}/test_{module_snake}_router.py"
    os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
    with open(test_file_path, "w") as f:
        f.write(test_template)
    print(f"Created: {test_file_path}")
    
    # Register model in src/infra/database/models.py
    models_path = "src/infra/database/models.py"
    with open(models_path, "r") as f:
        content = f.read()
        
    if f"src.modules.{module_snake}.models" not in content:
        # Add import
        import_line = f"from src.modules.{module_snake}.models import {module_name}\n"
        content = re.sub(r'(from src\.modules\..*import.*\n)(?!from src\.modules\.)', r'\1' + import_line, content)
        
        # Add to __all__
        content = re.sub(r'(__all__\s*=\s*\[.*)\]', r'\1, "' + module_name + '"]', content)
        
        with open(models_path, "w") as f:
            f.write(content)
        print(f"Registered: Model in {models_path}")
        
    # Register router in src/main.py
    main_path = "src/main.py"
    with open(main_path, "r") as f:
        lines = f.readlines()
        
    new_lines = []
    import_added = False
    include_added = False
    
    for line in lines:
        new_lines.append(line)
        if not import_added and "from src.modules." in line and "import router as" in line:
            # Check next lines to find the last import
            pass # We'll do it differently
            
    # Better main.py registration
    content = "".join(lines)
    if f"from src.modules.{module_snake}.router" not in content:
        # Add import
        import_stmt = f"from src.modules.{module_snake}.router import router as {module_snake}_router\n"
        content = re.sub(r'(from src\.modules\..*\.router import router as .*\n)(?!from src\.modules\..*\.router)', r'\1' + import_stmt, content)
        
        # Add include_router
        include_stmt = f"app.include_router({module_snake}_router)\n"
        content = re.sub(r'(app\.include_router\(.*_router\)\n)(?!app\.include_router)', r'\1' + include_stmt, content)
        
        with open(main_path, "w") as f:
            f.write(content)
        print(f"Registered: Router in {main_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        module_name = input("Enter Module Name (e.g. Category): ").strip()
        if not module_name:
            print("Usage: python scripts/generate_module.py ModuleName")
            sys.exit(1)
    else:
        module_name = sys.argv[1]
    
    module_snake = camel_to_snake(module_name)
    generate_module(module_name)

    import subprocess
    print("\nGenerating Alembic migration...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", f"add_{module_snake}_module"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"Migration created: {result.stdout.strip()}")
    else:
        print(f"Warning: Could not auto-generate migration: {result.stderr.strip()}")
