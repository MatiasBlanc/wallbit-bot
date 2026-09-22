"""Persistencia y entrega idempotente de notificaciones Telegram."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.logging import get_logger
from app.infrastructure.notifications.models import NotificationOutbox

logger = get_logger(__name__)


class NotificationOutboxRepository:
    """Gestiona el patrón transactional outbox para mensajes de Telegram."""

    def enqueue(
        self,
        session: Session,
        *,
        user_id: int,
        event_key: str,
        text: str,
        keyboard: list[list[dict[str, str]]] | None = None,
    ) -> NotificationOutbox:
        """Guarda una notificación solo si su evento aún no fue encolado.

        Args:
            session: Sesión que debe confirmarse junto con el cambio de dominio.
            user_id: Destinatario propietario del evento.
            event_key: Identificador único y estable del evento de negocio.
            text: Cuerpo HTML que se enviará a Telegram.
            keyboard: Filas serializables con ``text`` y ``callback_data``.

        Returns:
            Notificación existente o creada.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: Si la consulta o inserción falla.
        """
        existing = session.scalar(select(NotificationOutbox).where(NotificationOutbox.event_key == event_key))
        if existing is not None:
            return existing
        notification = NotificationOutbox(
            user_id=user_id,
            event_key=event_key,
            text=text,
            keyboard_json=json.dumps(keyboard, ensure_ascii=False) if keyboard else None,
        )
        session.add(notification)
        session.flush()
        return notification

    def recover_interrupted_deliveries(self, session: Session) -> int:
        """Devuelve al outbox entregas interrumpidas por un reinicio.

        Args:
            session: Sesión de inicio; el llamador confirma la transacción.

        Returns:
            Cantidad de mensajes recuperados.
        """
        result = session.connection().execute(
            update(NotificationOutbox)
            .where(NotificationOutbox.status == "delivering")
            .values(status="pending", next_attempt_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
        return result.rowcount

    def claim_next(self, session: Session) -> NotificationOutbox | None:
        """Reclama atómicamente una notificación lista para entregar.

        Args:
            session: Sesión corta de escritura.

        Returns:
            Notificación con estado ``delivering`` o None si no hay trabajo.
        """
        now = datetime.now(timezone.utc)
        candidate_id = session.scalar(
            select(NotificationOutbox.id)
            .where(
                NotificationOutbox.status == "pending",
                NotificationOutbox.next_attempt_at <= now,
            )
            .order_by(NotificationOutbox.created_at)
            .limit(1)
        )
        if candidate_id is None:
            return None
        claimed = session.connection().execute(
            update(NotificationOutbox)
            .where(NotificationOutbox.id == candidate_id, NotificationOutbox.status == "pending")
            .values(status="delivering")
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            return None
        session.flush()
        return session.scalar(
            select(NotificationOutbox)
            .options(joinedload(NotificationOutbox.user))
            .where(NotificationOutbox.id == candidate_id)
        )

    def mark_sent(self, session: Session, notification_id: int) -> None:
        """Confirma que Telegram aceptó el mensaje.

        Args:
            session: Sesión de escritura.
            notification_id: Identificador del mensaje reclamado.
        """
        session.execute(
            update(NotificationOutbox)
            .where(NotificationOutbox.id == notification_id, NotificationOutbox.status == "delivering")
            .values(status="sent", sent_at=datetime.now(timezone.utc), last_error=None)
        )

    def mark_retry(self, session: Session, notification_id: int, error: Exception) -> None:
        """Agenda un reintento con espera exponencial acotada.

        Args:
            session: Sesión de escritura.
            notification_id: Identificador del mensaje reclamado.
            error: Excepción de entrega; solo se persiste su tipo, no su texto.
        """
        notification = session.get(NotificationOutbox, notification_id)
        if notification is None or notification.status != "delivering":
            return
        attempts = notification.attempts + 1
        delay_seconds = min(300, 2 ** min(attempts, 8))
        notification.status = "pending"
        notification.attempts = attempts
        notification.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        notification.last_error = type(error).__name__
        session.flush()


def _keyboard_from_json(raw_keyboard: str | None) -> InlineKeyboardMarkup | None:
    """Reconstruye un teclado validando el contenido serializado localmente."""
    if not raw_keyboard:
        return None
    try:
        rows = json.loads(raw_keyboard)
        if not isinstance(rows, list):
            raise ValueError("Formato de teclado inválido")
        keyboard = [
            [
                InlineKeyboardButton(button["text"], callback_data=button["callback_data"])
                for button in row
            ]
            for row in rows
        ]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        logger.error("No se pudo reconstruir el teclado de una notificación: %s", type(error).__name__)
        return None
    return InlineKeyboardMarkup(keyboard)


async def dispatch_pending_notifications(bot: Bot, repository: NotificationOutboxRepository, limit: int = 20) -> int:
    """Entrega mensajes persistidos sin mantener una transacción abierta durante I/O.

    Args:
        bot: Cliente Telegram ya inicializado.
        repository: Repositorio de outbox.
        limit: Máximo de mensajes a enviar en este ciclo.

    Returns:
        Cantidad de entregas aceptadas por Telegram.
    """
    from app.infrastructure.database.database import get_db_session

    delivered = 0
    for _ in range(limit):
        with get_db_session() as session:
            notification = repository.claim_next(session)
            if notification is None:
                return delivered
            notification_id = notification.id
            chat_id = notification.user.telegram_user_id
            text = notification.text
            keyboard = _keyboard_from_json(notification.keyboard_json)

        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as error:
            logger.warning("No se pudo entregar la notificación %s: %s", notification_id, type(error).__name__)
            with get_db_session() as session:
                repository.mark_retry(session, notification_id, error)
            continue

        with get_db_session() as session:
            repository.mark_sent(session, notification_id)
        delivered += 1
    return delivered
