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
            result = session.connection().execute(sql_update(PendingOrder).where(
                PendingOrder.id == order_id, PendingOrder.user_id == user.id, PendingOrder.status == "pending",
            ).values(status="skipped"))
            is_skipped = result.rowcount == 1
        await query.edit_message_text(
            "Cancelé esta compra." if is_skipped else "Esa compra ya no está disponible."
        )

    return handle_order_confirm, handle_order_skip


def get_order_reconciliation_callback(
    order_service: OrderService, user_repo: UserSettingsRepository,
):
    """Construye el callback que resuelve órdenes tras verificarlas en Wallbit.

    Args:
        order_service: Servicio que aplica la transición atómica y registra el historial.
        user_repo: Repositorio usado para resolver el propietario local autorizado.

    Returns:
        Handler que marca una orden incierta como ejecutada o no ejecutada.
    """

    @restricted
    async def handle_order_reconciliation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or update.effective_user is None or not query.data:
            return

        try:
            _, resolution, raw_order_id = query.data.split(":", 2)
            order_id = int(raw_order_id)
            if resolution not in {"executed", "failed"}:
                raise ValueError
        except ValueError:
            await query.answer("Resolución de orden inválida.", show_alert=True)
            return

        with get_db_session() as session:
            user = user_repo.get_or_create(session, update.effective_user.id)
            is_resolved = order_service.reconcile_order(
                session=session,
                user_id=user.id,
                order_id=order_id,
                was_executed_on_wallbit=resolution == "executed",
            )

        if not is_resolved:
            await query.answer("La orden ya fue resuelta o no te pertenece.", show_alert=True)
            return

        await query.answer("Orden reconciliada.")
        if resolution == "executed":
            message = (
                f"✅ <b>Orden #{order_id} marcada como ejecutada</b>\n\n"
                "Se agregó al historial local. No se envió una nueva compra a Wallbit."
            )
        else:
            message = (
                f"❌ <b>Orden #{order_id} marcada como no ejecutada</b>\n\n"
                "No se envió una nueva compra a Wallbit."
            )
        await query.edit_message_text(message, parse_mode="HTML")

    return handle_order_reconciliation
