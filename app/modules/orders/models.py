"""Modelo ORM de las órdenes pendientes de confirmación."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PendingOrder(Base):
    __tablename__ = "pending_orders"
    __table_args__ = (Index("ix_pending_orders_status_expires", "status", "expires_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    dca_rule_id = Column(Integer, ForeignKey("dca_rules.id", ondelete="SET NULL"), nullable=True)
    ticker = Column(String(20), nullable=False)
    amount_usd = Column(Float, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    external_order_id = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=False)

    user = relationship("UserSettings", back_populates="pending_orders")
    dca_rule = relationship("DCARule", back_populates="pending_orders")
