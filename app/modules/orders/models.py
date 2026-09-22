"""Modelo ORM de las órdenes pendientes de confirmación."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.modules.dca.models import DCARule
    from app.modules.settings.models import UserSettings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PendingOrder(Base):
    __tablename__ = "pending_orders"
    __table_args__ = (Index("ix_pending_orders_status_expires", "status", "expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_settings.id", ondelete="CASCADE"))
    dca_rule_id: Mapped[int | None] = mapped_column(ForeignKey("dca_rules.id", ondelete="SET NULL"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(20))
    amount_usd: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    user: Mapped["UserSettings"] = relationship(back_populates="pending_orders")
    dca_rule: Mapped["DCARule | None"] = relationship(back_populates="pending_orders")
