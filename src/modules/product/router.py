from fastapi import APIRouter, Depends, HTTPException, Request

from src.modules.product.product_service import product_service
from src.modules.product.schemas import CreateProductDto, ProductSchema, ToggleStatusDto, UpdateProductDto
from src.shared.middlewares.permission_middleware import check_permission
from src.shared.schemas.generic_schema import PaginatedResponse

PRODUCT_NOT_FOUND_MSG = "Product not found"

router = APIRouter(prefix="/v1/product", tags=["product"])


@router.post("", status_code=201, response_model=ProductSchema)
async def create_product(req: CreateProductDto, user=Depends(check_permission("product", "create"))):
    data = req.model_dump()
    data["id_user"] = user.get("id")
    return await product_service.create(data)


@router.get("", response_model=PaginatedResponse[ProductSchema])
async def list_products(request: Request, _=Depends(check_permission("product", "view"))):
    return await product_service.list_items(dict(request.query_params))


@router.get("/all", response_model=PaginatedResponse[ProductSchema])
async def list_all_products(request: Request, _=Depends(check_permission("product", "view"))):
    return await product_service.list_all_items(dict(request.query_params))


@router.get("/{id}", response_model=ProductSchema)
async def get_product(id: str, _=Depends(check_permission("product", "view"))):
    product = await product_service.repo.find_one_by_id(id)
    if not product:
        raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND_MSG)
    return product


@router.put("/{id}", response_model=ProductSchema)
async def update_product(id: str, req: UpdateProductDto, _=Depends(check_permission("product", "create"))):
    return await product_service.update(id, req.model_dump(exclude_unset=True))


@router.delete("/{id}", status_code=204)
async def delete_product(id: str, _=Depends(check_permission("product", "delete"))):
    result = await product_service.delete(id)
    if not result:
        raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND_MSG)
    return None


@router.patch("/{id}/status", response_model=ProductSchema)
async def toggle_status(id: str, req: ToggleStatusDto, _=Depends(check_permission("product", "activate"))):
    result = await product_service.set_status(id, req.active)
    if not result:
        raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND_MSG)
    return result
