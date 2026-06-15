import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.role.models import RoleFeature


class Feature(Base, TimestampMixin):
    __tablename__ = "feature"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    role_features: Mapped[list["RoleFeature"]] = relationship(back_populates="feature")
