"""Callback query handlers for alert actions."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.keyboards.alerts import get_alert_item_keyboard, get_alerts_menu_keyboard
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.alert_service import AlertService

logger = get_logger(__name__)


def get_alert_callbacks(alert_service: AlertService, user_repo: UserSettingsRepository):
    @restricted
    async def handle_alert_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            alerts = alert_service.list_user_alerts(session, user.id)

            if not alerts:
                await query.edit_message_text(
                    "🔔 <b>No tienes alertas configuradas actualmente.</b>",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("➕ Crear alerta", callback_data="alert_menu:create")],
                            [InlineKeyboardButton("⬅️ Volver", callback_data="alert_menu:back")],
                        ]
                    ),
                    parse_mode="HTML",
                )
                return

            for i, alert in enumerate(alerts, 1):
                status_icon = "🟢 Activa" if (alert.enabled and not alert.triggered) else "⚪ Disparada / Inactiva"
                text = (
                    f"🔔 <b>Alerta #{i}</b>\n\n"
                    f"<b>Condición:</b> {alert.symbol} {alert.operator} ${alert.target_value:,.2f}\n"
                    f"<b>Estado:</b> {status_icon}"
                )
                keyboard = get_alert_item_keyboard(alert.id)
                await query.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

            await query.edit_message_text(
                "Mostrando tus alertas arriba.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Menú Alertas", callback_data="alert_menu:back")]]
                ),
            )

    @restricted
    async def handle_alert_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        alert_id = int(query.data.split(":")[1])

        with get_db_session() as session:
            alert = alert_service.alert_repo.get_by_id(session, alert_id)
            if alert:
                sym = alert.symbol
                alert_service.delete_alert(session, alert)
                session.commit()
                await query.edit_message_text(f"🗑 Alerta para <b>{sym}</b> eliminada.", parse_mode="HTML")

    @restricted
    async def handle_alert_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        text = (
            "🔔 <b>Gestión de Alertas</b>\n\n"
            "Configura avisos automáticos cuando un activo o divisa alcance determinado precio objetivo."
        )
        await query.edit_message_text(text, reply_markup=get_alerts_menu_keyboard(), parse_mode="HTML")

    @restricted
    async def handle_alert_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Menú de alertas cerrado.")

    return {
        "list": handle_alert_list,
        "delete": handle_alert_delete,
        "back": handle_alert_back,
        "close": handle_alert_close,
    }
