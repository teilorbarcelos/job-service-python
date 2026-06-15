from fastapi import APIRouter, Depends, Query

from src.infra.database.db import get_session
from src.modules.dashboard.dashboard_service import dashboard_service
from src.modules.dashboard.schemas import DashboardStatsResponseSchema
from src.shared.middlewares.permission_middleware import check_permission

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponseSchema)
async def get_dashboard_stats(
    created_at_start: str | None = Query(None, alias="createdAt_start"),
    created_at_end: str | None = Query(None, alias="createdAt_end"),
    _=Depends(check_permission("dashboard", "view")),
):
    async with get_session() as session:
        return await dashboard_service.get_stats(session, created_at_start, created_at_end)
