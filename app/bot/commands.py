from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from app.modules.orders.service import OrderService

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.infrastructure.wallbit.client import WallbitClient
from app.modules.settings.keyboards import get_main_reply_keyboard
from app.modules.settings.repository import UserSettingsRepository

logger = get_logger(__name__)


def get_start_handler(client: WallbitClient, user_repo: UserSettingsRepository):
    @restricted
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user_repo.get_or_create(session, user_id)
            session.commit()

        mode = "Operación real" if settings.TRADING_ENABLED else "Simulación"
        hint = "Usa los botones de abajo. Si es la primera vez, entra a Ajustes."
        if settings.MULTI_USER_ENABLED:
            hint += "\n/logout desconecta tu cuenta."

        def start_text(conn_status: str) -> str:
            return (
                "<b>Wallbit Assistant</b>\n\n"
                "Consulta saldo e inversiones, programa compras y recibe alertas.\n"
                "No es un producto oficial ni está desarrollado por Wallbit.\n\n"
                f"Wallbit · {conn_status}\n"
                f"Modo · {mode}\n\n"
                f"{hint}"
            )

        if not update.effective_message:
            return
        health = context.application.bot_data.get("wallbit_health")
        if health is not None:
            conn_status = health.label()
        else:
            conn_status = "🟢 Conectado" if await client.check_connection() else "🔴 Desconectado"
        await update.effective_message.reply_text(
            start_text(conn_status),
            parse_mode="HTML",
            reply_markup=get_main_reply_keyboard(),
        )

    return start_command


def get_status_handler():
    """Manejador para /estado y /status (observabilidad y métricas del bot)."""
    @restricted
    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_message:
            return
        from app.infrastructure.monitoring.metrics import metrics
        report = metrics.format_telegram_report()
        await update.effective_message.reply_text(report, parse_mode="HTML")

    return status_command


def get_orders_handler(order_service: "OrderService"):
    """Manejador para /ordenes (revisión de órdenes con verificación pendiente)."""

    @restricted
    async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_message:
            return
        user_id = update.effective_user.id
        with get_db_session() as session:
            unverified = order_service.list_orders_needing_verification(session, user_id)
            if not unverified:
                await update.effective_message.reply_text(
                    "✅ <b>Órdenes al día</b>\n\n"
                    "No hay órdenes pendientes de verificación por problemas de red o timeouts.",
                    parse_mode="HTML",
                )
                return

            lines = ["⚠️ <b>Órdenes que requieren verificación manual:</b>\n"]
            for o in unverified:
                created = o.created_at.strftime("%Y-%m-%d %H:%M UTC") if o.created_at else "desconocida"
                lines.append(
                    f"• ID #{o.id}: <b>{o.ticker}</b> por <b>${o.amount_usd:.2f}</b>\n"
                    f"  Fecha: <code>{created}</code>\n"
                    f"  Idempotency Key: <code>{o.idempotency_key}</code>\n"
                )
            lines.append(
                "\n<i>Revisa en tu cuenta de Wallbit si la orden se completó antes de ejecutar una nueva compra.</i>"
            )
            await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")

    return orders_command

