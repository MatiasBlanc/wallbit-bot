"""Alert checker background job."""

from telegram import Bot

from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.infrastructure.notifications.repository import NotificationOutboxRepository
from app.modules.alerts.service import AlertService
from app.modules.auth.jobs import for_each_account, job_telegram_user_id

logger = get_logger(__name__)


@for_each_account
async def run_alert_checker(
    bot: Bot, alert_service: AlertService, notification_repo: NotificationOutboxRepository
) -> None:
    """Detecta alertas y persiste cada aviso antes de intentar enviarlo.

    Args:
        bot: Se conserva por compatibilidad con la firma de jobs del scheduler.
        alert_service: Servicio que evalúa y desactiva alertas disparadas.
        notification_repo: Outbox transaccional de Telegram.
    """
    del bot
    with get_db_session() as session:
        try:
            triggered = await alert_service.check_active_alerts(session, telegram_user_id=job_telegram_user_id())
            for item in triggered:
                user = item.alert.user
                if user is None:
                    continue
                notification_repo.enqueue(
                    session,
                    user_id=user.id,
                    event_key=f"alert:{item.alert.id}",
                    text=item.message,
                    keyboard=[[
                        {"text": "➕ Crear alerta", "callback_data": "alert_menu:create"},
                        {"text": "🗑️ Eliminar", "callback_data": f"alert_delete:{item.alert.id}"},
                    ]],
                )
        except Exception as error:
            logger.exception("Error comprobando alertas: %s", type(error).__name__)
