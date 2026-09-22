"""Credenciales cifradas y códigos de vinculación, separados del esquema existente."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class WallbitCredential(Base):
    """Una cuenta Wallbit por identidad Telegram; no contiene claves en texto plano."""

    __tablename__ = "wallbit_credentials"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    wallbit_plan: Mapped[str] = mapped_column(String(20), default="classic")
    login_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    login_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
