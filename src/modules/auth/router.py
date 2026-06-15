from fastapi import APIRouter, Depends, Header, HTTPException

from src.modules.auth.auth_service import auth_service
from src.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    PasswordChangeRequest,
    PasswordRequestRequest,
    PasswordValidateRequest,
    RefreshRequest,
    TokenValidationResponse,
)
from src.shared.config import messages
from src.shared.middlewares.auth_middleware import check_auth


def _extract_token(authorization: str) -> str:
    return authorization.replace("Bearer ", "").strip().strip('"')


router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    return await auth_service.login(req.email, req.password)


@router.get("/me", response_model=LoginResponse)
async def get_me(authorization: str = Header(None), _=Depends(check_auth)):
    if not authorization:
        raise HTTPException(status_code=401, detail=messages.INVALID_OR_EXPIRED_TOKEN)
    token = _extract_token(authorization)
    return await auth_service.get_me(token)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(req: RefreshRequest):
    return await auth_service.refresh(req.refreshToken)


@router.post("/logout", response_model=MessageResponse)
async def logout(authorization: str = Header(None)):
    if authorization:
        token = _extract_token(authorization)
        return await auth_service.logout(token)
    return {"message": messages.LOGGED_OUT_SUCCESSFULLY}


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(authorization: str = Header(None)):
    if authorization:
        token = _extract_token(authorization)
        return await auth_service.logout_all(token)
    return {"message": messages.LOGGED_OUT_SUCCESSFULLY}


@router.post("/password/request", response_model=MessageResponse)
async def request_password(req: PasswordRequestRequest):
    return await auth_service.request_password_reset(req.email)


@router.post("/password/validate", response_model=TokenValidationResponse)
async def validate_password(req: PasswordValidateRequest):
    return await auth_service.validate_password_reset_token(req.email, req.token)


@router.post("/password/change", response_model=MessageResponse)
async def change_password(req: PasswordChangeRequest):
    return await auth_service.change_password(req.email, req.token, req.password)
