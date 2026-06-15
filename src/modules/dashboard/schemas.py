from pydantic import BaseModel, Field


class TimeSeriesStatSchema(BaseModel):
    date: str = Field(..., examples=["2026-05-23"])
    count: int = Field(..., examples=[10])


class UserProductStatSchema(BaseModel):
    userId: str | None = Field(None, examples=["user-uuid-123"])
    userName: str = Field(..., examples=["João Silva"])
    count: int = Field(..., examples=[5])


class DashboardStatsResponseSchema(BaseModel):
    userCreationStats: list[TimeSeriesStatSchema]
    productCreationStats: list[TimeSeriesStatSchema]
    productsPerUser: list[UserProductStatSchema]
