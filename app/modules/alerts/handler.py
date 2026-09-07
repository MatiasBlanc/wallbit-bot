"""/alerta command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.alerts.keyboards import get_alerts_menu_keyboard
from app.modules.settings.repository import UserSettingsRepository


def get_alerts_handler(user_repo: UserSettingsRepository):
    @restricted
    async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user_repo.get_or_create(session, user_id)

        text = (
            "<b>Alertas</b>\n\n"
            "Te aviso cuando una acción o un tipo de cambio llegue al precio que elijas."
        )
        await update.effective_message.reply_text(
            text,
            reply_markup=get_alerts_menu_keyboard(),
            parse_mode="HTML",
        )

    return alerts_command
