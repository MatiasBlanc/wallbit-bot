"""Conversation for setting custom report time in config."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.keyboards.config import get_config_main_keyboard
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository

CONFIG_STATE_TIME = 1


def get_config_time_conversation_handler(user_repo: UserSettingsRepository) -> ConversationHandler:
    @restricted
    async def prompt_report_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = (
            "⏰ <b>Hora del reporte diario</b>\n\n"
            "Ingresa la hora en formato <b>HH:MM</b> (24 horas, ej: 09:00 o 18:30):"
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel_config_conv")]]
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        elif update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
        return CONFIG_STATE_TIME

    @restricted
    async def receive_report_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        raw_text = update.effective_message.text.strip()
        parts = raw_text.split(":")
        valid = False
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                valid = True
                formatted_time = f"{h:02d}:{m:02d}"

        if not valid:
            await update.effective_message.reply_text(
                "⚠️ Formato inválido. Ingresa una hora válida en formato <b>HH:MM</b> (ej: 09:00):",
                parse_mode="HTML",
            )
            return CONFIG_STATE_TIME

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            user_repo.update_report_time(session, user, formatted_time)
            session.commit()
            alerts_enabled = user.alerts_enabled

        await update.effective_message.reply_text(
            f"✅ Hora del reporte actualizada a las <b>{formatted_time}</b>.",
            reply_markup=get_config_main_keyboard(alerts_enabled),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    @restricted
    async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = "Configuración de hora cancelada."
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            alerts_enabled = user.alerts_enabled

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
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_report_time),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_config_conv$"),
        ],
        per_user=True,
    )
