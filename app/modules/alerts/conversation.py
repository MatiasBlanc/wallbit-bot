"""Conversation flow for creating price and FX alerts."""

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

from app.core.constants import (
    ALERT_TYPE_FX,
    ALERT_TYPE_PRICE,
    OPERATOR_GTE,
    OPERATOR_LTE,
)
from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.infrastructure.wallbit.exceptions import WallbitApiException
from app.modules.alerts.service import AlertService
from app.modules.settings.repository import UserSettingsRepository

logger = get_logger(__name__)


def parse_fx_pair(symbol: str) -> tuple[str, str]:
    """Valida y separa un par de divisas escrito como USD/CLP o USDCLP."""
    normalized = symbol.replace("/", "").strip().upper()
    if len(normalized) != 6 or not normalized.isalpha():
        raise ValueError("Escribe un par válido, por ejemplo <b>USD/CLP</b>.")
    return normalized[:3], normalized[3:]


async def get_current_alert_value(alert_service: AlertService, alert_type: str, symbol: str) -> tuple[float, str]:
    """Consulta el valor actual y devuelve el valor junto con su unidad visible."""
    if alert_type == ALERT_TYPE_PRICE:
        asset = await alert_service.client.get_asset(symbol)
        return asset.price, asset.currency or "USD"

    source, destination = parse_fx_pair(symbol)
    rate = await alert_service.exchange_service.get_rate(source, destination)
    return rate, destination


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
        text = "<b>Nueva alerta</b>\n\n¿De una acción o de un tipo de cambio?"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📈 Acción / ETF", callback_data=f"alert_type:{ALERT_TYPE_PRICE}"),
                    InlineKeyboardButton("💱 Dólar / moneda", callback_data=f"alert_type:{ALERT_TYPE_FX}"),
                ],
                [InlineKeyboardButton("✕ Cancelar", callback_data="cancel_alert_conv")],
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
            [[InlineKeyboardButton("✕ Cancelar", callback_data="cancel_alert_conv")]]
        )

        if alert_type == ALERT_TYPE_PRICE:
            msg = "¿Cuál? Escribe el símbolo, por ejemplo <b>VOO</b> o <b>AAPL</b>."
        else:
            msg = "¿Qué par? Por ejemplo <b>USD/CLP</b> o <b>USD/ARS</b>."

        await query.edit_message_text(msg, reply_markup=cancel_kb, parse_mode="HTML")
        return ALERT_STATE_SYMBOL

    @restricted
    async def receive_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        symbol = update.effective_message.text.upper().strip()
        alert_type = context.user_data["alert_type"]
        try:
            current_value, value_label = await get_current_alert_value(alert_service, alert_type, symbol)
        except ValueError as error:
            await update.effective_message.reply_text(
                f"⚠️ {error}\n\nEscribe el símbolo o par nuevamente.",
                parse_mode="HTML",
            )
            return ALERT_STATE_SYMBOL
        except WallbitApiException as error:
            logger.warning("No se pudo consultar la cotización de alerta %s: %s", symbol, error)
            await update.effective_message.reply_text(
                f"⚠️ {error.user_message}\n\nEscribe otro símbolo o toca Cancelar.",
                parse_mode="HTML",
            )
            return ALERT_STATE_SYMBOL
        except Exception:
            logger.exception("Error consultando la cotización de alerta %s", symbol)
            await update.effective_message.reply_text(
                "⚠️ No pude consultar el valor actual. Inténtalo nuevamente o toca Cancelar.",
            )
            return ALERT_STATE_SYMBOL

        if alert_type == ALERT_TYPE_FX:
            source, destination = parse_fx_pair(symbol)
            symbol = f"{source}/{destination}"
            current_text = f"1 {source} = <b>{current_value:,.2f} {destination}</b>"
        else:
            current_text = f"<b>${current_value:,.2f} {value_label}</b>"

        context.user_data["alert_symbol"] = symbol
        context.user_data["alert_current_value"] = current_value

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📈 Cuando suba a", callback_data=f"alert_op:{OPERATOR_GTE}"),
                    InlineKeyboardButton("📉 Cuando baje a", callback_data=f"alert_op:{OPERATOR_LTE}"),
                ],
                [InlineKeyboardButton("✕ Cancelar", callback_data="cancel_alert_conv")],
            ]
        )
        await update.effective_message.reply_text(
            f"<b>{symbol}</b>\nValor actual: {current_text}\n\n¿Te aviso si sube o si baja?",
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
            [[InlineKeyboardButton("✕ Cancelar", callback_data="cancel_alert_conv")]]
        )
        direction = "suba a" if op == OPERATOR_GTE else "baje a"
        current_value = context.user_data["alert_current_value"]
        symbol = context.user_data["alert_symbol"]
        current_text = f"${current_value:,.2f}"
        if context.user_data.get("alert_type") == ALERT_TYPE_FX:
            source, destination = parse_fx_pair(symbol)
            current_text = f"1 {source} = {current_value:,.2f} {destination}"
        await query.edit_message_text(
            f"<b>{symbol}</b> · valor actual: <b>{current_text}</b>\n\n"
            f"Te aviso si {direction}.\nEscribe el valor objetivo, por ejemplo <b>500</b>.",
            reply_markup=cancel_kb,
            parse_mode="HTML",
        )
        return ALERT_STATE_TARGET

    @restricted
    async def receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.effective_message.text.strip().replace("$", "")
        try:
            val = float(text)
            if not math.isfinite(val) or val <= 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("Escribe un número, por ejemplo <b>500</b>.", parse_mode="HTML")
            return ALERT_STATE_TARGET

        context.user_data["alert_target"] = val
        symbol = context.user_data["alert_symbol"]
        op = context.user_data["alert_operator"]
        direction = "suba a" if op == OPERATOR_GTE else "baje a"
        summary_text = (
            "<b>Revisa la alerta</b>\n\n"
            f"Te aviso si <b>{symbol}</b> {direction} <b>${val:,.2f}</b>."
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Activar alerta", callback_data="alert_confirm:yes"),
                    InlineKeyboardButton("✕ Cancelar", callback_data="cancel_alert_conv"),
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
            f"<b>Alerta activada</b>\n\n"
            f"Te aviso si <b>{alert.symbol}</b> llega a <b>${alert.target_value:,.2f}</b>.",
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
