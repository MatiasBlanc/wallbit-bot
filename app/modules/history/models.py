"""Modelo ORM del historial local de operaciones."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LocalTransaction(Base):
    __tablename__ = "local_transactions"
    __table_args__ = (
        Index("ix_local_transactions_user_date", "user_id", "created_at", "id"),
        Index("ix_local_transactions_user_ticker_type", "user_id", "ticker", "transaction_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    transaction_type = Column(String(20), nullable=False)
    ticker = Column(String(20), nullable=True)
    amount_usd = Column(Float, nullable=False)
    external_order_id = Column(String(100), nullable=True)
    source = Column(String(20), default="MANUAL", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("UserSettings", back_populates="transactions")
