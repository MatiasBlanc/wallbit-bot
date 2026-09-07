"""User settings ORM model."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    default_currency = Column(String(10), default="CLP", nullable=False)
    report_time = Column(String(5), default="09:00", nullable=False)
    timezone = Column(String(50), default="America/Santiago", nullable=False)
    alerts_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_daily_report = Column(String(10), nullable=True)

    dca_rules = relationship("DCARule", back_populates="user", cascade="all, delete-orphan")
    pending_orders = relationship("PendingOrder", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("LocalTransaction", back_populates="user", cascade="all, delete-orphan")
