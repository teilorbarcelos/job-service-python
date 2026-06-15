from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoleFeatureSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_feature: str
    create: bool
    view: bool
    delete: bool
    activate: bool


class RoleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    active: bool | None = True
    is_deleted: bool | None = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    RoleFeature: list[RoleFeatureSchema] | None = []


class CreateRoleDto(BaseModel):
    id: str | None = None
    name: str
    description: str
    permissions: list[dict] | None = []


class UpdateRoleDto(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: list[dict] | None = []


class ToggleStatusDto(BaseModel):
    active: bool
