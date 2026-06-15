import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.user.models import User


class Product(Base, TimestampMixin):
    __tablename__ = "product"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(255))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(2000))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    id_user: Mapped[str | None] = mapped_column(String(40), ForeignKey("user.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)
    user: Mapped[Optional["User"]] = relationship("User")
