from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.modules.role.schemas import RoleSchema


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    phone: str | None = None
    document: str | None = None
    active: bool | None = True
    id_role: str
    role: RoleSchema | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateUserDto(BaseModel):
    name: str
    email: str
    password: str | None = None
    id_role: str
    phone: str | None = None
    document: str | None = None


class UpdateUserDto(BaseModel):
    name: str | None = None
    email: str | None = None
    id_role: str | None = None
    password: str | None = None


class ToggleStatusDto(BaseModel):
    active: bool
