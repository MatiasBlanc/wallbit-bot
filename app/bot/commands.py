from html import escape
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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


def get_orders_handler(
    order_service: "OrderService", user_repo: UserSettingsRepository,
):
    """Construye `/ordenes` para revisar resultados inciertos sin reintentar compras.

    Args:
        order_service: Servicio que consulta órdenes en verificación.
        user_repo: Repositorio que traduce el ID de Telegram al propietario local.

    Returns:
        Handler autorizado para listar y resolver cada orden manualmente.
    """

    @restricted
    async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_message or not update.effective_user:
            return
        with get_db_session() as session:
            user = user_repo.get_or_create(session, update.effective_user.id)
            pending_orders = order_service.list_pending_orders(session, user.id)
            unverified = order_service.list_orders_needing_verification(session, user.id)

        if not pending_orders and not unverified:
            await update.effective_message.reply_text(
                "✅ <b>Órdenes al día</b>\n\n"
                "No hay compras esperando confirmación ni resultados pendientes de verificación.",
                parse_mode="HTML",
            )
            return

        lines = ["<b>Órdenes</b>\n"]
        keyboard_rows = []
        if pending_orders:
            lines.append("⏳ <b>Esperando confirmación</b>")
            for order in pending_orders:
                expires = order.expires_at.strftime("%Y-%m-%d %H:%M UTC") if order.expires_at else "desconocido"
                lines.append(
                    f"• ID #{order.id}: <b>{escape(order.ticker)}</b> por <b>${order.amount_usd:.2f}</b>\n"
                    f"  Vence: <code>{expires}</code>\n"
                )
                keyboard_rows.append(
                    [
                        InlineKeyboardButton("Comprar", callback_data=f"order_confirm:{order.id}"),
                        InlineKeyboardButton("Ahora no", callback_data=f"order_skip:{order.id}"),
                    ]
                )
        if unverified:
            lines.append("⚠️ <b>Requieren verificación manual</b>")
        for order in unverified:
            created = order.created_at.strftime("%Y-%m-%d %H:%M UTC") if order.created_at else "desconocida"
            lines.append(
                f"• ID #{order.id}: <b>{escape(order.ticker)}</b> por <b>${order.amount_usd:.2f}</b>\n"
                f"  Fecha: <code>{created}</code>\n"
                f"  Clave: <code>{escape(order.idempotency_key)}</code>\n"
            )
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        f"✅ Ejecutada #{order.id}",
                        callback_data=f"order_reconcile:executed:{order.id}",
                    ),
                    InlineKeyboardButton(
                        f"❌ No ejecutada #{order.id}",
                        callback_data=f"order_reconcile:failed:{order.id}",
                    ),
                ]
            )
        lines.append(
            "\n<i>Primero comprueba la operación en Wallbit. Esta decisión actualiza "
            "el historial local y no envía otra compra.</i>"
        )
        await update.effective_message.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
        )

    return orders_command

