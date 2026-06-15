from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    sku: str
    category: str
    price: float
    active: bool | None = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    description: str | None = None
    stock: int | None = 0
    id_user: str | None = None


class CreateProductDto(BaseModel):
    name: str
    sku: str
    category: str
    price: float
    stock: int
    description: str | None = None


class UpdateProductDto(BaseModel):
    name: str | None = None
    category: str | None = None
    price: float | None = None
    stock: int | None = None
    description: str | None = None


class ToggleStatusDto(BaseModel):
    active: bool
