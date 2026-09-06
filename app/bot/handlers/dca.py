"""/dca command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards.dca import get_dca_menu_keyboard
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.dca_service import DCAService


def get_dca_handler(dca_service: DCAService, user_repo: UserSettingsRepository):
    @restricted
    async def dca_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user_repo.get_or_create(session, user_id)

        text = (
            "📈 <b>Gestión de DCA (Dollar-Cost Averaging)</b>\n\n"
            "Elige una opción:"
        )
        await update.effective_message.reply_text(
            text,
            reply_markup=get_dca_menu_keyboard(),
            parse_mode="HTML",
        )

    return dca_command
