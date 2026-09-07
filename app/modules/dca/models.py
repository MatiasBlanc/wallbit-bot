"""DCA rule ORM model."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DCARule(Base):
    __tablename__ = "dca_rules"
    __table_args__ = (
        Index("ix_dca_rules_enabled_execution", "enabled", "next_execution_at"),
        Index("ix_dca_rules_user_enabled_execution", "user_id", "enabled", "next_execution_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False)
    asset_name = Column(String(200), nullable=True)
    amount_usd = Column(Float, nullable=False)
    frequency = Column(String(20), nullable=False)
    weekday = Column(Integer, nullable=True)
    day_of_month = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    next_execution_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("UserSettings", back_populates="dca_rules")
    pending_orders = relationship("PendingOrder", back_populates="dca_rule")
