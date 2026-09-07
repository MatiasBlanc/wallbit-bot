"""Conversation for setting custom report time in config."""

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.settings.keyboards import get_config_main_keyboard, get_report_time_keyboard
from app.modules.settings.repository import UserSettingsRepository

CONFIG_STATE_TIME = 1


def parse_report_time(raw_text: str) -> str | None:
    """Valida HH:MM en 24 horas.

    Args:
        raw_text: Texto ingresado por el usuario.

    Returns:
        Hora normalizada HH:MM, o None si el formato no es válido.
    """
    parts = raw_text.strip().split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    hours, minutes = int(parts[0]), int(parts[1])
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return f"{hours:02d}:{minutes:02d}"


def get_config_time_conversation_handler(user_repo: UserSettingsRepository) -> ConversationHandler:
    def save_report_time(user_id: int, formatted_time: str) -> bool:
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            user_repo.update_report_time(session, user, formatted_time)
            session.commit()
            return user.alerts_enabled

    @restricted
    async def prompt_report_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = (
            "<b>Hora del reporte</b>\n\n"
            "Elige un horario o escribe uno, por ejemplo <b>09:00</b> o <b>18:30</b>."
        )
        keyboard = get_report_time_keyboard()
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        elif update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
        return CONFIG_STATE_TIME

    @restricted
    async def receive_report_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        formatted_time = parse_report_time(update.effective_message.text)
        if formatted_time is None:
            await update.effective_message.reply_text(
                "Usa el formato <b>09:00</b> (24 horas) o elige un botón.",
                parse_mode="HTML",
                reply_markup=get_report_time_keyboard(),
            )
            return CONFIG_STATE_TIME
        alerts_enabled = save_report_time(update.effective_user.id, formatted_time)
        await update.effective_message.reply_text(
            f"Listo. El reporte diario llega a las <b>{formatted_time}</b>.",
            reply_markup=get_config_main_keyboard(alerts_enabled),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    @restricted
    async def receive_report_time_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        formatted_time = parse_report_time(query.data.split(":", 1)[1])
        if formatted_time is None:
            await query.edit_message_text("Hora inválida.")
            return ConversationHandler.END
        alerts_enabled = save_report_time(update.effective_user.id, formatted_time)
        await query.edit_message_text(
            f"Listo. El reporte diario llega a las <b>{formatted_time}</b>.",
            reply_markup=get_config_main_keyboard(alerts_enabled),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    @restricted
    async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            alerts_enabled = user.alerts_enabled
        text = "No cambié la hora."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, reply_markup=get_config_main_keyboard(alerts_enabled)
            )
        elif update.effective_message:
            await update.effective_message.reply_text(
                text, reply_markup=get_config_main_keyboard(alerts_enabled)
            )
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(prompt_report_time, pattern=r"^config:report_time$")
        ],
        states={
            CONFIG_STATE_TIME: [
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_config_conv$"),
                CallbackQueryHandler(receive_report_time_button, pattern=r"^report_time:\d{2}:\d{2}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_report_time),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_config_conv$"),
        ],
        per_user=True,
    )
