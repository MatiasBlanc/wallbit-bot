"""Alert checker background job."""

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.modules.alerts.service import AlertService
from app.modules.auth.jobs import for_each_account, job_telegram_user_id

logger = get_logger(__name__)


@for_each_account
async def run_alert_checker(bot: Bot, alert_service: AlertService) -> None:
    """Check active alerts and dispatch notifications when thresholds are reached."""
    with get_db_session() as session:
        try:
            triggered = await alert_service.check_active_alerts(session, telegram_user_id=job_telegram_user_id())
            for item in triggered:
                user = item.alert.user
                if not user:
                    continue

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("Nueva alerta", callback_data="alert_menu:create"),
                            InlineKeyboardButton("Borrar", callback_data=f"alert_delete:{item.alert.id}"),
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=user.telegram_user_id,
                    text=item.message,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
