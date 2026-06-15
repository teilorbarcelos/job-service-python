import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.database.base import Base
from src.shared.config.settings import settings

SCHEMA_NAME = "audit" if "sqlite" not in settings.database_url.lower() else None


class Audit(Base):
    __tablename__ = "tb_audit"
    __table_args__ = {"schema": SCHEMA_NAME} if SCHEMA_NAME else {}

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user: Mapped[str] = mapped_column(String(255), nullable=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=True)
    action_type: Mapped[str] = mapped_column(String(255), nullable=True)
    execute_type: Mapped[str] = mapped_column(String(255), nullable=True)
    class_name: Mapped[str] = mapped_column("class", String(255), nullable=True)
    function_name: Mapped[str] = mapped_column("function", String(255), nullable=True)
    params: Mapped[str] = mapped_column(Text, nullable=True)
    raw: Mapped[str] = mapped_column(Text, nullable=True)
    table_name: Mapped[str] = mapped_column(String(255), nullable=True)
    diff_value: Mapped[str] = mapped_column(Text, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    host: Mapped[str] = mapped_column(Text, nullable=True)
    ip: Mapped[str] = mapped_column(Text, nullable=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(Text, nullable=True)
    hostname: Mapped[str] = mapped_column(Text, nullable=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ErrorLog(Base):
    __tablename__ = "tb_error_log"
    __table_args__ = {"schema": SCHEMA_NAME} if SCHEMA_NAME else {}

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user: Mapped[str] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    error_data: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
