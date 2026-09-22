"""Pruebas de entrega persistente de notificaciones Telegram."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database import database
from app.infrastructure.notifications.repository import NotificationOutboxRepository, dispatch_pending_notifications


@pytest.mark.asyncio
async def test_dispatch_retries_failed_notification(db_session, test_user, monkeypatch):
    """Un fallo de Telegram conserva el evento y lo reintenta sin duplicarlo."""
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
    )
    repository = NotificationOutboxRepository()
    repository.enqueue(
        db_session,
        user_id=test_user.id,
        event_key="alert:1",
        text="<b>Alerta</b>",
        keyboard=[[{"text": "Abrir", "callback_data": "alert_menu:list"}]],
    )
    db_session.commit()

    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("Telegram no disponible")
    assert await dispatch_pending_notifications(bot, repository) == 0

    db_session.expire_all()
    from app.infrastructure.notifications.models import NotificationOutbox

    queued = db_session.query(NotificationOutbox).one()
    assert queued.status == "pending"
    assert queued.attempts == 1
    assert queued.last_error == "RuntimeError"

    queued.next_attempt_at = queued.created_at
    db_session.commit()
    bot.send_message.side_effect = None
    assert await dispatch_pending_notifications(bot, repository) == 1

    db_session.expire_all()
    assert db_session.query(NotificationOutbox).one().status == "sent"
    assert bot.send_message.await_count == 2


def test_recover_interrupted_delivery(db_session, test_user):
    """Un reinicio devuelve mensajes reclamados a estado pendiente."""
    repository = NotificationOutboxRepository()
    queued = repository.enqueue(db_session, user_id=test_user.id, event_key="dca:1", text="Propuesta")
    queued.status = "delivering"
    db_session.commit()

    assert repository.recover_interrupted_deliveries(db_session) == 1
    db_session.commit()
    assert queued.status == "pending"
