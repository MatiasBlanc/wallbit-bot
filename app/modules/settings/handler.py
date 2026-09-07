"""/config command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.constants import CURRENCY_FLAGS
from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.settings.keyboards import get_config_main_keyboard, timezone_label
from app.modules.settings.repository import UserSettingsRepository

logger = get_logger(__name__)


def build_config_text(user) -> str:
    alerts_status = "Activadas" if user.alerts_enabled else "Desactivadas"
    flag = CURRENCY_FLAGS.get(user.default_currency, "")
    currency = f"{flag} {user.default_currency}".strip()
    trading_status = "🔴 Desactivado" if not settings.TRADING_ENABLED else "🟢 Activado"
    ai_status = "🟢 Activada" if settings.AI_ENABLED else "🔴 Desactivada"
    return (
        "<b>⚙️ Configuración</b>\n\n"
        f"Moneda · {currency}\n"
        f"Reporte · {user.report_time} ({timezone_label(user.timezone)})\n"
        f"Alertas · {alerts_status.lower()}\n"
        f"Trading real · {trading_status}\n"
        f"IA · {ai_status}\n\n"
        "Toca lo que quieras cambiar."
    )


def get_config_handler(user_repo: UserSettingsRepository):
    @restricted
    async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            text = build_config_text(user)
            keyboard = get_config_main_keyboard(user.alerts_enabled)

        await update.effective_message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    return config_command
