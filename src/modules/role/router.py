from fastapi import APIRouter, Depends, HTTPException, Request

from src.modules.feature.schemas import FeatureSchema
from src.modules.role.role_service import role_service
from src.modules.role.schemas import CreateRoleDto, RoleSchema, ToggleStatusDto, UpdateRoleDto
from src.shared.middlewares.permission_middleware import check_permission
from src.shared.schemas.generic_schema import PaginatedResponse

router = APIRouter(prefix="/v1/role", tags=["role"])


@router.get("/features", response_model=list[FeatureSchema])
async def list_role_features(_=Depends(check_permission("role", "view"))):
    return await role_service.list_features()


@router.get("", response_model=PaginatedResponse[RoleSchema])
async def list_roles(request: Request, _=Depends(check_permission("role", "view"))):
    return await role_service.list_items(dict(request.query_params))


@router.get("/all", response_model=PaginatedResponse[RoleSchema])
async def get_all_roles(request: Request, _=Depends(check_permission("role", "view"))):
    return await role_service.list_all_items(dict(request.query_params))


@router.get("/{id}", response_model=RoleSchema)
async def get_role(id: str, _=Depends(check_permission("role", "view"))):
    return await role_service.repo.find_one_by_id(id)


@router.post("", status_code=201, response_model=RoleSchema)
async def create_role(req: CreateRoleDto, _=Depends(check_permission("role", "create"))):
    return await role_service.create(req.model_dump())


@router.put("/{id}", response_model=RoleSchema)
async def update_role(id: str, req: UpdateRoleDto, _=Depends(check_permission("role", "create"))):
    return await role_service.update(id, req.model_dump(exclude_unset=True))


@router.delete("/{id}", status_code=204)
async def delete_role(id: str, _=Depends(check_permission("role", "delete"))):
    result = await role_service.delete(id)
    if not result:
        raise HTTPException(status_code=404, detail="Role not found")
    return None


@router.patch("/{id}/status", response_model=RoleSchema)
async def toggle_status(id: str, req: ToggleStatusDto, _=Depends(check_permission("role", "activate"))):
    result = await role_service.set_status(id, req.active)
    if not result:
        raise HTTPException(status_code=404, detail="Role not found")
    return result
