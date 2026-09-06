"""Callback query handlers for confirming or skipping pending orders."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.order_service import OrderService

logger = get_logger(__name__)


def get_order_callbacks(order_service: OrderService, user_repo: UserSettingsRepository):
    @restricted
    async def handle_order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        try:
            order_id = int(query.data.split(":")[1])
        except (IndexError, ValueError):
            await query.answer("ID de orden inválido.", show_alert=True)
            return

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            result = await order_service.confirm_order(
                session=session, order_id=order_id, user=user
            )

        if result.already_processed:
            await query.answer("Esta operación ya fue procesada.", show_alert=True)
            return

        if not result.success:
            msg = (
                f"❌ <b>No pudimos ejecutar la compra.</b>\n\n"
                f"{result.error_message or 'Error en la validación o fondos insuficientes.'}"
            )
            await query.edit_message_text(msg, parse_mode="HTML")
            return

        if result.is_simulation:
            msg = (
                "🧪 <b>Modo simulación</b>\n\n"
                "Se habría ejecutado:\n\n"
                f"Compra <b>{result.ticker}</b>\n"
                f"Monto: <b>${result.amount_usd:,.2f} USD</b>\n\n"
                f"Sim ID:\n<code>{result.order_id}</code>\n\n"
                "<i>(El modo real se activa con TRADING_ENABLED=true)</i>"
            )
        else:
            msg = (
                "✅ <b>Compra ejecutada</b>\n\n"
                f"<b>{result.ticker}</b>\n"
                f"Monto: <b>${result.amount_usd:,.2f} USD</b>\n\n"
                f"Order ID:\n<code>{result.order_id}</code>"
            )

        await query.edit_message_text(msg, parse_mode="HTML")

    @restricted
    async def handle_order_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer("Operación omitida.")
        await query.edit_message_text("⏭ <b>Operación omitida por el usuario.</b>", parse_mode="HTML")

    return handle_order_confirm, handle_order_skip
