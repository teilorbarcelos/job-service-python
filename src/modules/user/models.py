import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.auth.models import Auth
    from src.modules.role.models import Role


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(15), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    document: Mapped[str] = mapped_column(String(11), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    avatar: Mapped[str] = mapped_column(String(255), nullable=True)

    id_auth: Mapped[str] = mapped_column(String(40), ForeignKey("auth.id"), unique=True, nullable=True)
    id_role: Mapped[str] = mapped_column(String(40), ForeignKey("role.id"))

    auth: Mapped[Optional["Auth"]] = relationship(back_populates="user")
    role: Mapped["Role"] = relationship(back_populates="users")

    __table_args__ = (Index("ix_user_email_is_deleted", "email", "is_deleted"),)
