from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.modules.user.schemas import CreateUserDto, ToggleStatusDto, UpdateUserDto, UserSchema
from src.modules.user.user_service import user_service
from src.shared.config import messages
from src.shared.middlewares.permission_middleware import check_permission
from src.shared.schemas.generic_schema import PaginatedResponse

router = APIRouter(prefix="/v1/user", tags=["user"])


@router.get("", response_model=PaginatedResponse[UserSchema])
async def get_users(request: Request, _=Depends(check_permission("user", "view"))):
    return await user_service.list_items(dict(request.query_params))


@router.get("/all", response_model=PaginatedResponse[UserSchema])
async def get_all_users(request: Request, _=Depends(check_permission("user", "view"))):
    return await user_service.list_all_items(dict(request.query_params))


@router.get("/export/pdf")
async def export_users_pdf(request: Request, _=Depends(check_permission("user", "view"))):
    stream = await user_service.export_pdf(dict(request.query_params))
    return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="usuarios.pdf"'})


@router.post("", status_code=201, response_model=UserSchema)
async def create_user(req: CreateUserDto, _=Depends(check_permission("user", "create"))):
    return await user_service.create(req.model_dump())


@router.get("/{id}", response_model=UserSchema)
async def get_user_by_id(id: str, _=Depends(check_permission("user", "view"))):
    user = await user_service.repo.find_one_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail=messages.USER_NOT_FOUND)
    return user


@router.put("/{id}", response_model=UserSchema)
async def update_user(id: str, req: UpdateUserDto, _=Depends(check_permission("user", "create"))):
    return await user_service.update(id, req.model_dump(exclude_unset=True))


@router.delete("/{id}", status_code=204)
async def delete_user(id: str, _=Depends(check_permission("user", "delete"))):
    result = await user_service.delete(id)
    if not result:
        raise HTTPException(status_code=404, detail=messages.USER_NOT_FOUND)
    return None


@router.patch("/{id}/status", response_model=UserSchema)
async def toggle_status(id: str, req: ToggleStatusDto, _=Depends(check_permission("user", "activate"))):
    result = await user_service.set_status(id, req.active)
    if not result:
        raise HTTPException(status_code=404, detail=messages.USER_NOT_FOUND)
    return result
