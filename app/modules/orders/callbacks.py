"""Callback query handlers for confirming or skipping pending orders."""

from sqlalchemy import update as sql_update
from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.orders.models import PendingOrder
from app.modules.orders.service import OrderService
from app.modules.settings.repository import UserSettingsRepository

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
                f"<b>No pude completar la compra</b>\n\n"
                f"{result.error_message or 'Revisa el saldo e inténtalo de nuevo.'}"
            )
            await query.edit_message_text(msg, parse_mode="HTML")
            return

        if result.is_simulation:
            msg = (
                "<b>Simulación</b> · no se envió a Wallbit\n\n"
                f"{result.ticker}\n"
                f"${result.amount_usd:,.2f} + comisión est. ${result.estimated_fee_usd:,.2f}\n"
                f"Total ≈ <b>${result.estimated_total_usd:,.2f} USD</b>\n\n"
                f"<code>{result.order_id}</code>"
            )
        else:
            msg = (
                "<b>Compra enviada</b>\n\n"
                f"{result.ticker} · ${result.amount_usd:,.2f} USD\n"
                f"Comisión est. ${result.estimated_fee_usd:,.2f}\n\n"
                f"<code>{result.order_id}</code>"
            )

        await query.edit_message_text(msg, parse_mode="HTML")

    @restricted
    async def handle_order_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        try:
            order_id = int(query.data.split(":")[1])
        except (IndexError, ValueError):
            await query.edit_message_text("Orden inválida.")
            return
        with get_db_session() as session:
            user = user_repo.get_or_create(session, update.effective_user.id)
            result = session.execute(sql_update(PendingOrder).where(
                PendingOrder.id == order_id, PendingOrder.user_id == user.id, PendingOrder.status == "pending",
            ).values(status="skipped"))
            is_skipped = result.rowcount == 1
        await query.edit_message_text(
            "Cancelé esta compra." if is_skipped else "Esa compra ya no está disponible."
        )

    return handle_order_confirm, handle_order_skip
