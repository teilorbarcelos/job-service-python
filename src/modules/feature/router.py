from fastapi import APIRouter, Depends, Request

from src.modules.feature.feature_service import feature_service
from src.modules.feature.schemas import CreateFeatureDto, FeatureSchema, ToggleStatusDto, UpdateFeatureDto
from src.shared.middlewares.permission_middleware import check_permission
from src.shared.schemas.generic_schema import PaginatedResponse

router = APIRouter(prefix="/v1/feature", tags=["feature"])


@router.get("", response_model=PaginatedResponse[FeatureSchema])
async def get_features(request: Request, _=Depends(check_permission("feature", "view"))):
    return await feature_service.list_items(dict(request.query_params))


@router.get("/all", response_model=PaginatedResponse[FeatureSchema])
async def get_all_features(request: Request, _=Depends(check_permission("feature", "view"))):
    return await feature_service.list_all_items(dict(request.query_params))


@router.get("/{id}", response_model=FeatureSchema)
async def get_feature(id: str, _=Depends(check_permission("feature", "view"))):
    return await feature_service.repo.find_one_by_id(id)


@router.post("", status_code=201, response_model=FeatureSchema)
async def create_feature(req: CreateFeatureDto, _=Depends(check_permission("feature", "create"))):
    return await feature_service.create(req.model_dump())


@router.put("/{id}", response_model=FeatureSchema)
async def update_feature(id: str, req: UpdateFeatureDto, _=Depends(check_permission("feature", "create"))):
    return await feature_service.update(id, req.model_dump(exclude_unset=True))


@router.delete("/{id}", status_code=204)
async def delete_feature(id: str, _=Depends(check_permission("feature", "delete"))):
    return await feature_service.delete(id)


@router.patch("/{id}/status", response_model=FeatureSchema)
async def toggle_status(id: str, req: ToggleStatusDto, _=Depends(check_permission("feature", "activate"))):
    return await feature_service.set_status(id, req.active)
