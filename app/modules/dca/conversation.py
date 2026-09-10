"""Conversation flow for creating a new DCA rule."""

import math

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.constants import DCA_FREQ_MONTHLY, DCA_FREQ_WEEKLY, WEEKDAY_NAMES_ES
from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.dca.service import DCAService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.datetime import format_date_short

logger = get_logger(__name__)


def format_asset_label(ticker: str, name: str | None = None) -> str:
    """Muestra el ticker y el nombre del fondo o acción, si se conoce."""
    if name and name.strip() and name.strip().upper() != ticker.upper():
        return f"{ticker} ({name.strip()})"
    return ticker


(
    DCA_STATE_TICKER,
    DCA_STATE_AMOUNT,
    DCA_STATE_FREQUENCY,
    DCA_STATE_DAY,
    DCA_STATE_CONFIRM,
) = range(5)


def get_dca_conversation_handler(dca_service: DCAService, user_repo: UserSettingsRepository) -> ConversationHandler:
    @restricted
    async def start_create_dca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        text = (
            "<b>Nueva compra periódica</b>\n\n"
            "¿Qué quieres comprar? Escribe el símbolo, por ejemplo <b>VOO</b> o <b>AAPL</b>."
        )
        cancel_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Cancelar", callback_data="cancel_conv")]]
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=cancel_kb, parse_mode="HTML")
        elif update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=cancel_kb, parse_mode="HTML")
        return DCA_STATE_TICKER

    @restricted
    async def receive_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        ticker = update.effective_message.text.upper().strip()
        resolved = await dca_service.resolve_ticker(ticker)
        if not resolved:
            await update.effective_message.reply_text(
                f"No encontré <b>{ticker}</b> en Wallbit. Prueba otro símbolo o toca Cancelar.",
                parse_mode="HTML",
            )
            return DCA_STATE_TICKER

        ticker, asset_name = resolved
        context.user_data["dca_ticker"] = ticker
        context.user_data["dca_asset_name"] = asset_name
        cancel_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Cancelar", callback_data="cancel_conv")]]
        )
        await update.effective_message.reply_text(
            f"Comprarás <b>{format_asset_label(ticker, asset_name)}</b>.\n\n"
            "¿Cuántos USD cada vez? Por ejemplo <b>50</b>.",
            reply_markup=cancel_kb,
            parse_mode="HTML",
        )
        return DCA_STATE_AMOUNT

    @restricted
    async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.effective_message.text.strip().replace("$", "")
        try:
            amount = float(text)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text(
                "Escribe un monto en USD, por ejemplo <b>50</b>:", parse_mode="HTML",
            )
            return DCA_STATE_AMOUNT

        context.user_data["dca_amount"] = amount
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Cada semana", callback_data="dca_freq:weekly"),
                    InlineKeyboardButton("Cada mes", callback_data="dca_freq:monthly"),
                ],
                [InlineKeyboardButton("Cancelar", callback_data="cancel_conv")],
            ]
        )
        await update.effective_message.reply_text(
            f"<b>${amount:,.2f} USD</b> cada vez.\n\n"
            "¿Cada cuánto?",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return DCA_STATE_FREQUENCY

    @restricted
    async def receive_frequency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "dca_freq:weekly":
            context.user_data["dca_frequency"] = DCA_FREQ_WEEKLY
            buttons = [
                [
                    InlineKeyboardButton("Lunes", callback_data="dca_day:0"),
                    InlineKeyboardButton("Martes", callback_data="dca_day:1"),
                    InlineKeyboardButton("Miércoles", callback_data="dca_day:2"),
                ],
                [
                    InlineKeyboardButton("Jueves", callback_data="dca_day:3"),
                    InlineKeyboardButton("Viernes", callback_data="dca_day:4"),
                ],
                [
                    InlineKeyboardButton("Sábado", callback_data="dca_day:5"),
                    InlineKeyboardButton("Domingo", callback_data="dca_day:6"),
                ],
                [InlineKeyboardButton("Cancelar", callback_data="cancel_conv")],
            ]
            await query.edit_message_text(
                "¿Qué día de la semana?",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return DCA_STATE_DAY

        elif data == "dca_freq:monthly":
            context.user_data["dca_frequency"] = DCA_FREQ_MONTHLY
            buttons = [
                [
                    InlineKeyboardButton("Día 01", callback_data="dca_day:1"),
                    InlineKeyboardButton("Día 05", callback_data="dca_day:5"),
                    InlineKeyboardButton("Día 10", callback_data="dca_day:10"),
                ],
                [
                    InlineKeyboardButton("Día 15", callback_data="dca_day:15"),
                    InlineKeyboardButton("Día 20", callback_data="dca_day:20"),
                    InlineKeyboardButton("Día 25", callback_data="dca_day:25"),
                ],
                [InlineKeyboardButton("Cancelar", callback_data="cancel_conv")],
            ]
            await query.edit_message_text(
                "¿Qué día del mes? También puedes escribir un número del 1 al 28.",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return DCA_STATE_DAY

        return DCA_STATE_FREQUENCY

    @restricted
    async def receive_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        val = int(query.data.split(":")[1])
        freq = context.user_data.get("dca_frequency")

        if freq == DCA_FREQ_WEEKLY:
            context.user_data["dca_weekday"] = val
            day_desc = f"Todos los {WEEKDAY_NAMES_ES.get(val, '')}"
        else:
            context.user_data["dca_day_of_month"] = val
            day_desc = f"Día {val:02d} de cada mes"

        return await show_dca_confirmation(query, context, day_desc)

    @restricted
    async def receive_day_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        freq = context.user_data.get("dca_frequency")
        if freq != DCA_FREQ_MONTHLY:
            await update.effective_message.reply_text("Usa los botones para elegir el día.")
            return DCA_STATE_DAY

        text = update.effective_message.text.strip()
        try:
            val = int(text)
            if not (1 <= val <= 31):
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("Escribe un día entre 1 y 28.")
            return DCA_STATE_DAY

        context.user_data["dca_day_of_month"] = val
        day_desc = f"Día {val:02d} de cada mes"
        return await show_dca_confirmation(update.effective_message, context, day_desc)

    async def show_dca_confirmation(target, context, day_desc: str) -> int:
        ticker = context.user_data["dca_ticker"]
        amount = context.user_data["dca_amount"]
        asset_name = context.user_data.get("dca_asset_name")

        text = (
            "<b>Revisa tu compra</b>\n\n"
            f"{format_asset_label(ticker, asset_name)}\n"
            f"${amount:,.2f} USD · {day_desc}\n\n"
            "Ese día te aviso para confirmar. No se compra sola."
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Activar", callback_data="dca_confirm:yes"),
                    InlineKeyboardButton("Cancelar", callback_data="cancel_conv"),
                ]
            ]
        )
        if hasattr(target, "edit_message_text"):
            await target.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await target.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
        return DCA_STATE_CONFIRM

    @restricted
    async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            rule = dca_service.create_rule(
                session=session,
                user=user,
                ticker=context.user_data["dca_ticker"],
                amount_usd=context.user_data["dca_amount"],
                frequency=context.user_data["dca_frequency"],
                weekday=context.user_data.get("dca_weekday"),
                day_of_month=context.user_data.get("dca_day_of_month"),
                asset_name=context.user_data.get("dca_asset_name"),
            )
            session.commit()
            next_date_str = format_date_short(rule.next_execution_at)
            asset_name = context.user_data.get("dca_asset_name")

        context.user_data.clear()
        await query.edit_message_text(
            f"<b>Compra activada</b>\n\n"
            f"{format_asset_label(rule.ticker, asset_name)}\n"
            f"${rule.amount_usd:,.2f} USD\n"
            f"Próxima: {next_date_str}\n\n"
            "Ese día te aviso para confirmar la compra.",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    @restricted
    async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        text = "Cancelado."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text)
        elif update.effective_message:
            await update.effective_message.reply_text(text)
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_create_dca, pattern=r"^dca_menu:create$"),
            CommandHandler("crear_dca", start_create_dca),
        ],
        states={
            DCA_STATE_TICKER: [
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_conv$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticker),
            ],
            DCA_STATE_AMOUNT: [
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_conv$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount),
            ],
            DCA_STATE_FREQUENCY: [
                CallbackQueryHandler(receive_frequency_callback, pattern=r"^dca_freq:"),
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_conv$"),
            ],
            DCA_STATE_DAY: [
                CallbackQueryHandler(receive_day_callback, pattern=r"^dca_day:"),
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_conv$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_day_text),
            ],
            DCA_STATE_CONFIRM: [
                CallbackQueryHandler(handle_confirm, pattern=r"^dca_confirm:yes$"),
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_conv$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_conv$"),
        ],
        per_user=True,
    )
