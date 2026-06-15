from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


class PasswordRequestRequest(BaseModel):
    email: str


class PasswordValidateRequest(BaseModel):
    email: str
    token: str


class PasswordChangeRequest(BaseModel):
    email: str
    token: str
    password: str


class PermissionResponse(BaseModel):
    feature: str
    create: bool
    view: bool
    delete: bool
    activate: bool


class AuthRoleResponse(BaseModel):
    id: str
    name: str
    description: str
    permissions: list[PermissionResponse]


class AuthUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: AuthRoleResponse


class LoginResponse(BaseModel):
    message: str
    valid: bool
    token: str
    refreshToken: str
    user: AuthUserResponse


class TokenValidationResponse(BaseModel):
    valid: bool


class MessageResponse(BaseModel):
    message: str
