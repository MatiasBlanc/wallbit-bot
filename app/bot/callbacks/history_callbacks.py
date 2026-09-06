"""Callback query handler for history pagination."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.history import build_history_page
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.history_service import HistoryService

logger = get_logger(__name__)


def get_history_callback(history_service: HistoryService, user_repo: UserSettingsRepository):
    @restricted
    async def handle_history_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        try:
            page = int(query.data.split(":")[1])
        except (IndexError, ValueError):
            page = 1

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            items, page, total_pages = await history_service.get_history(
                session=session, user_id=user.id, page=page, limit=5
            )

        text, reply_markup = build_history_page(items, page, total_pages)
        await query.edit_message_text(
            text,
            reply_markup=reply_markup if reply_markup.inline_keyboard else None,
            parse_mode="HTML",
        )

    return handle_history_page
