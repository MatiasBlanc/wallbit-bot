"""/alerta command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards.alerts import get_alerts_menu_keyboard
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository


def get_alerts_handler(user_repo: UserSettingsRepository):
    @restricted
    async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user_repo.get_or_create(session, user_id)

        text = (
            "🔔 <b>Gestión de Alertas</b>\n\n"
            "Configura avisos automáticos cuando un activo o divisa alcance determinado precio objetivo."
        )
        await update.effective_message.reply_text(
            text,
            reply_markup=get_alerts_menu_keyboard(),
            parse_mode="HTML",
        )

    return alerts_command
