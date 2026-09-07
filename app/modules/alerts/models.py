"""Alert ORM model."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_active_user", "enabled", "triggered", "user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(20), nullable=False)
    symbol = Column(String(30), nullable=False)
    operator = Column(String(5), nullable=False)
    target_value = Column(Float, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    triggered = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("UserSettings", back_populates="alerts")
