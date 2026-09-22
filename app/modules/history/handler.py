"""/historial command handler."""


from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.history.service import HistoryService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.formatting.currency import format_usd

logger = get_logger(__name__)


def build_history_page(items, page: int, total_pages: int) -> tuple[str, InlineKeyboardMarkup]:
    lines = [f"<b>Movimientos</b> · {page}/{total_pages}\n"]
    if not items:
        lines.append("No hay movimientos registrados.")
    else:
        for it in items:
            lines.append(f"{it.icon} <b>{it.title}</b>")
            lines.append(f"{format_usd(it.amount_usd)}")
            lines.append(f"{it.date_str}\n")

    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"history_page:{page - 1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"history_page:{page + 1}"))

    keyboard_rows = []
    if nav_buttons:
        keyboard_rows.append(nav_buttons)

    return "\n".join(lines).strip(), InlineKeyboardMarkup(keyboard_rows)


def get_history_handler(history_service: HistoryService, user_repo: UserSettingsRepository):
    @restricted
    async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            items, page, total_pages = await history_service.get_history(
                session=session, user_id=user.id, page=1, limit=5
            )

        text, reply_markup = build_history_page(items, page, total_pages)
        await update.effective_message.reply_text(
            text,
            reply_markup=reply_markup if reply_markup.inline_keyboard else None,
            parse_mode="HTML",
        )

    return history_command
