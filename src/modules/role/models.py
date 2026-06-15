from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.feature.models import Feature
    from src.modules.user.models import User


class RoleFeature(Base):
    __tablename__ = "role_feature"

    id_role: Mapped[str] = mapped_column(String(40), ForeignKey("role.id"), primary_key=True)
    id_feature: Mapped[str] = mapped_column(String(40), ForeignKey("feature.id"), primary_key=True)

    create: Mapped[bool] = mapped_column(Boolean, default=False)
    view: Mapped[bool] = mapped_column(Boolean, default=False)
    activate: Mapped[bool] = mapped_column(Boolean, default=False)
    delete: Mapped[bool] = mapped_column(Boolean, default=False)

    role: Mapped["Role"] = relationship(back_populates="role_features")
    feature: Mapped["Feature"] = relationship(back_populates="role_features")


class Role(Base, TimestampMixin):
    __tablename__ = "role"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="role")
    role_features: Mapped[list["RoleFeature"]] = relationship(back_populates="role")
