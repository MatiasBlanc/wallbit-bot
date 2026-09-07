"""Credenciales cifradas y códigos de vinculación, separados del esquema existente."""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, Text

from app.infrastructure.database.base import Base


class WallbitCredential(Base):
    """Una cuenta Wallbit por identidad Telegram; no contiene claves en texto plano."""

    __tablename__ = "wallbit_credentials"

    telegram_user_id = Column(BigInteger, primary_key=True, autoincrement=False)
    encrypted_api_key = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    wallbit_plan = Column(String(20), nullable=False, default="classic")
    login_code_hash = Column(String(64), nullable=True)
    login_expires_at = Column(DateTime(timezone=True), nullable=True)
