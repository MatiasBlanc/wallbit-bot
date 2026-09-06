"""Conversation flow for creating price and FX alerts."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.constants import (
    ALERT_TYPE_FX,
    ALERT_TYPE_PRICE,
    OPERATOR_GTE,
    OPERATOR_LTE,
)
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.alert_service import AlertService

logger = get_logger(__name__)

(
    ALERT_STATE_TYPE,
    ALERT_STATE_SYMBOL,
    ALERT_STATE_OPERATOR,
    ALERT_STATE_TARGET,
    ALERT_STATE_CONFIRM,
) = range(5)


def get_alert_conversation_handler(alert_service: AlertService, user_repo: UserSettingsRepository) -> ConversationHandler:
    @restricted
    async def start_create_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        text = "➕ <b>Crear alerta</b>\n\nSelecciona el tipo de alerta que deseas configurar:"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📈 Precio de activo", callback_data=f"alert_type:{ALERT_TYPE_PRICE}"),
                    InlineKeyboardButton("💱 Tipo de cambio", callback_data=f"alert_type:{ALERT_TYPE_FX}"),
                ],
                [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_alert_conv")],
            ]
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        elif update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
        return ALERT_STATE_TYPE

    @restricted
    async def receive_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        alert_type = query.data.split(":")[1]
        context.user_data["alert_type"] = alert_type

        cancel_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel_alert_conv")]]
        )

        if alert_type == ALERT_TYPE_PRICE:
            msg = "Ingresa el <b>ticker</b> del activo (ej: VOO, AAPL, SPY):"
        else:
            msg = "Ingresa el <b>par de divisas</b> (ej: USD/CLP o USD/ARS):"

        await query.edit_message_text(msg, reply_markup=cancel_kb, parse_mode="HTML")
        return ALERT_STATE_SYMBOL

    @restricted
    async def receive_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        symbol = update.effective_message.text.upper().strip()
        context.user_data["alert_symbol"] = symbol

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Mayor o igual (>=)", callback_data=f"alert_op:{OPERATOR_GTE}"),
                    InlineKeyboardButton("Menor o igual (<=)", callback_data=f"alert_op:{OPERATOR_LTE}"),
                ],
                [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_alert_conv")],
            ]
        )
        await update.effective_message.reply_text(
            f"Símbolo: <b>{symbol}</b>\n\nSelecciona el operador de condición:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return ALERT_STATE_OPERATOR

    @restricted
    async def receive_operator_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        op = query.data.split(":")[1]
        context.user_data["alert_operator"] = op

        cancel_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel_alert_conv")]]
        )
        await query.edit_message_text(
            f"Condición elegida: <b>{context.user_data['alert_symbol']} {op}</b>\n\n"
            "Ingresa el <b>valor objetivo</b> numérico (ej: 500 o 980):",
            reply_markup=cancel_kb,
            parse_mode="HTML",
        )
        return ALERT_STATE_TARGET

    @restricted
    async def receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.effective_message.text.strip().replace("$", "")
        try:
            val = float(text)
            if val <= 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("⚠️ Ingresa un valor numérico positivo válido:")
            return ALERT_STATE_TARGET

        context.user_data["alert_target"] = val
        symbol = context.user_data["alert_symbol"]
        op = context.user_data["alert_operator"]
        alert_type = context.user_data["alert_type"]

        type_str = "Precio de activo" if alert_type == ALERT_TYPE_PRICE else "Tipo de cambio"
        summary_text = (
            "📋 <b>Resumen de la alerta:</b>\n\n"
            f"<b>Tipo:</b> {type_str}\n"
            f"<b>Condición:</b> {symbol} {op} ${val:,.2f}\n\n"
            "¿Deseas activar esta alerta?"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Activar alerta", callback_data="alert_confirm:yes"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel_alert_conv"),
                ]
            ]
        )
        await update.effective_message.reply_text(summary_text, reply_markup=keyboard, parse_mode="HTML")
        return ALERT_STATE_CONFIRM

    @restricted
    async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            alert = alert_service.create_alert(
                session=session,
                user=user,
                alert_type=context.user_data["alert_type"],
                symbol=context.user_data["alert_symbol"],
                operator=context.user_data["alert_operator"],
                target_value=context.user_data["alert_target"],
            )
            session.commit()

        context.user_data.clear()
        await query.edit_message_text(
            f"✅ <b>Alerta activada</b>\n\n"
            f"Te notificaremos cuando <b>{alert.symbol}</b> sea <b>{alert.operator} ${alert.target_value:,.2f}</b>.",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    @restricted
    async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        text = "Operación cancelada."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text)
        elif update.effective_message:
            await update.effective_message.reply_text(text)
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_create_alert, pattern=r"^alert_menu:create$"),
            CommandHandler("crear_alerta", start_create_alert),
        ],
        states={
            ALERT_STATE_TYPE: [
                CallbackQueryHandler(receive_type_callback, pattern=r"^alert_type:"),
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_alert_conv$"),
            ],
            ALERT_STATE_SYMBOL: [
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_alert_conv$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_symbol),
            ],
            ALERT_STATE_OPERATOR: [
                CallbackQueryHandler(receive_operator_callback, pattern=r"^alert_op:"),
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_alert_conv$"),
            ],
            ALERT_STATE_TARGET: [
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_alert_conv$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_target),
            ],
            ALERT_STATE_CONFIRM: [
                CallbackQueryHandler(handle_confirm, pattern=r"^alert_confirm:yes$"),
                CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_alert_conv$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=r"^cancel_alert_conv$"),
        ],
        per_user=True,
    )
