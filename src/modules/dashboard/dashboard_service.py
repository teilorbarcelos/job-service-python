from datetime import datetime, time, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import coalesce

from src.infra.database.models import Product, User
from src.modules.dashboard.schemas import DashboardStatsResponseSchema, TimeSeriesStatSchema, UserProductStatSchema


def parse_start_date(date_str: str) -> datetime:
    if not date_str or not date_str.strip():
        return datetime.now() - timedelta(days=30)
    try:
        parsed_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        return datetime.combine(parsed_date, time.min)
    except Exception:
        return datetime.now() - timedelta(days=30)


def parse_end_date(date_str: str) -> datetime:
    if not date_str or not date_str.strip():
        return datetime.now()
    try:
        parsed_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        return datetime.combine(parsed_date, time(23, 59, 59))
    except Exception:
        return datetime.now()


class DashboardService:
    async def get_stats(
        self, session: AsyncSession, created_at_start: str = None, created_at_end: str = None
    ) -> DashboardStatsResponseSchema:
        start = parse_start_date(created_at_start)
        end = parse_end_date(created_at_end)

        user_creation_stats = await self.get_user_creation_stats(session, start, end)
        product_creation_stats = await self.get_product_creation_stats(session, start, end)
        products_per_user = await self.get_products_per_user(session, start, end)

        return DashboardStatsResponseSchema(
            userCreationStats=user_creation_stats, productCreationStats=product_creation_stats, productsPerUser=products_per_user
        )

    async def get_user_creation_stats(self, session: AsyncSession, start: datetime, end: datetime) -> list[TimeSeriesStatSchema]:
        if session.bind.dialect.name == "sqlite":
            date_expr = func.strftime("%Y-%m-%d", User.created_at)
        else:
            date_expr = func.to_char(User.created_at, "YYYY-MM-DD")

        stmt = (
            select(date_expr.label("date"), func.count(User.id).label("count"))
            .where(and_(User.created_at >= start, User.created_at <= end, User.is_deleted == False))
            .group_by(date_expr)
            .order_by(date_expr.asc())
        )

        result = await session.execute(stmt)
        return [TimeSeriesStatSchema(date=row.date, count=row.count) for row in result.all()]

    async def get_product_creation_stats(self, session: AsyncSession, start: datetime, end: datetime) -> list[TimeSeriesStatSchema]:
        if session.bind.dialect.name == "sqlite":
            date_expr = func.strftime("%Y-%m-%d", Product.created_at)
        else:
            date_expr = func.to_char(Product.created_at, "YYYY-MM-DD")

        stmt = (
            select(date_expr.label("date"), func.count(Product.id).label("count"))
            .where(and_(Product.created_at >= start, Product.created_at <= end, Product.is_deleted == False))
            .group_by(date_expr)
            .order_by(date_expr.asc())
        )

        result = await session.execute(stmt)
        return [TimeSeriesStatSchema(date=row.date, count=row.count) for row in result.all()]

    async def get_products_per_user(self, session: AsyncSession, start: datetime, end: datetime) -> list[UserProductStatSchema]:
        stmt = (
            select(
                Product.id_user.label("userId"), coalesce(User.name, "Anonymous").label("userName"), func.count(Product.id).label("count")
            )
            .select_from(Product)
            .outerjoin(User, Product.id_user == User.id)
            .where(and_(Product.created_at >= start, Product.created_at <= end, Product.is_deleted == False))
            .group_by(Product.id_user, User.name)
            .order_by(func.count(Product.id).desc())
        )

        result = await session.execute(stmt)
        return [UserProductStatSchema(userId=row.userId, userName=row.userName, count=row.count) for row in result.all()]


dashboard_service = DashboardService()
