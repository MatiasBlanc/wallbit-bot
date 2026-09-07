"""/dca command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.dca.keyboards import get_dca_menu_keyboard
from app.modules.dca.service import DCAService
from app.modules.settings.repository import UserSettingsRepository


def get_dca_handler(dca_service: DCAService, user_repo: UserSettingsRepository):
    @restricted
    async def dca_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user_repo.get_or_create(session, user_id)

        text = (
            "<b>Compras periódicas</b>\n\n"
            "Programa una compra semanal o mensual. Ese día te aviso para confirmarla."
        )
        await update.effective_message.reply_text(
            text,
            reply_markup=get_dca_menu_keyboard(),
            parse_mode="HTML",
        )

    return dca_command
