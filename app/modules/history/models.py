"""Modelo ORM del historial local de operaciones."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.modules.settings.models import UserSettings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LocalTransaction(Base):
    __tablename__ = "local_transactions"
    __table_args__ = (
        Index("ix_local_transactions_user_date", "user_id", "created_at", "id"),
        Index("ix_local_transactions_user_ticker_type", "user_id", "ticker", "transaction_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_settings.id", ondelete="CASCADE"))
    transaction_type: Mapped[str] = mapped_column(String(20))
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_usd: Mapped[float] = mapped_column(Float)
    external_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="MANUAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["UserSettings"] = relationship(back_populates="transactions")
