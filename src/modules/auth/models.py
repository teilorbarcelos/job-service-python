import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.user.models import User


class Auth(Base, TimestampMixin):
    __tablename__ = "auth"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    password: Mapped[str] = mapped_column(String(255), nullable=True)
    password_algo: Mapped[str] = mapped_column(String(20), default="bcrypt")
    password_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    request_password_token: Mapped[str] = mapped_column(String(255), nullable=True)
    request_password_expiration: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    retries: Mapped[int] = mapped_column(default=0)
    first_access: Mapped[bool] = mapped_column(default=True)
    active: Mapped[bool] = mapped_column(default=True)

    user: Mapped[Optional["User"]] = relationship(back_populates="auth")
