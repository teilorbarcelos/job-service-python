from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeatureSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    active: bool | None = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateFeatureDto(BaseModel):
    name: str
    description: str


class UpdateFeatureDto(BaseModel):
    name: str | None = None
    description: str | None = None


class ToggleStatusDto(BaseModel):
    active: bool
