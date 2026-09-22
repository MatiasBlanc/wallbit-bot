"""DCA rule ORM model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.modules.orders.models import PendingOrder
    from app.modules.settings.models import UserSettings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DCARule(Base):
    __tablename__ = "dca_rules"
    __table_args__ = (
        Index("ix_dca_rules_enabled_execution", "enabled", "next_execution_at"),
        Index("ix_dca_rules_user_enabled_execution", "user_id", "enabled", "next_execution_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_settings.id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(20))
    asset_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount_usd: Mapped[float] = mapped_column(Float)
    frequency: Mapped[str] = mapped_column(String(20))
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_execution_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["UserSettings"] = relationship(back_populates="dca_rules")
    pending_orders: Mapped[list["PendingOrder"]] = relationship(back_populates="dca_rule")
