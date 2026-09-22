"""Modelo de outbox para notificaciones que no se deben perder."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.modules.settings.models import UserSettings


def utcnow() -> datetime:
    """Devuelve la hora actual en UTC para campos persistidos."""
    return datetime.now(timezone.utc)


class NotificationOutbox(Base):
    """Mensaje Telegram pendiente, con una clave única por evento de dominio."""

    __tablename__ = "notification_outbox"
    __table_args__ = (Index("ix_notification_outbox_delivery", "status", "next_attempt_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_settings.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    keyboard_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)

    user: Mapped["UserSettings"] = relationship()
