"""User settings ORM model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.modules.alerts.models import Alert
    from app.modules.dca.models import DCARule
    from app.modules.history.models import LocalTransaction
    from app.modules.orders.models import PendingOrder


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    default_currency: Mapped[str] = mapped_column(String(10), default="CLP")
    report_time: Mapped[str] = mapped_column(String(5), default="09:00")
    timezone: Mapped[str] = mapped_column(String(50), default="America/Santiago")
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_daily_report: Mapped[str | None] = mapped_column(String(10), nullable=True)

    dca_rules: Mapped[list["DCARule"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pending_orders: Mapped[list["PendingOrder"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["LocalTransaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
