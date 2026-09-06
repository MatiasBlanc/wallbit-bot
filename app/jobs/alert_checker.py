"""Alert checker background job."""

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.logging import get_logger
from app.db.database import get_db_session
from app.db.models import UserSettings
from app.services.alert_service import AlertService

logger = get_logger(__name__)


async def run_alert_checker(bot: Bot, alert_service: AlertService) -> None:
    """Check active alerts and dispatch notifications when thresholds are reached."""
    with get_db_session() as session:
        try:
            triggered = await alert_service.check_active_alerts(session)
            for item in triggered:
                user = session.query(UserSettings).filter(UserSettings.id == item.alert.user_id).first()
                if not user:
                    continue

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("Crear otra", callback_data="alert_menu:create"),
                            InlineKeyboardButton("Eliminar", callback_data=f"alert_delete:{item.alert.id}"),
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
