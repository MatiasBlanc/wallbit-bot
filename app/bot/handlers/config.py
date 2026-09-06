"""/config command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards.config import get_config_main_keyboard
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository

logger = get_logger(__name__)


def build_config_text(user) -> str:
    alerts_status = "Activadas" if user.alerts_enabled else "Desactivadas"
    return (
        "⚙️ <b>Configuración Personal</b>\n\n"
        f"<b>Moneda por defecto:</b> {user.default_currency}\n"
        f"<b>Hora del reporte diario:</b> {user.report_time}\n"
        f"<b>Zona horaria:</b> {user.timezone}\n"
        f"<b>Alertas:</b> {alerts_status}\n\n"
        "Selecciona qué opción deseas modificar:"
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
