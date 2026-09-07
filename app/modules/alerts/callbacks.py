"""Callback query handlers for alert actions."""

from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.alerts.keyboards import get_alerts_menu_keyboard
from app.modules.alerts.service import AlertService
from app.modules.settings.repository import UserSettingsRepository

logger = get_logger(__name__)


def get_alert_callbacks(alert_service: AlertService, user_repo: UserSettingsRepository):
    @restricted
    async def handle_alert_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        page = int(query.data.rsplit(":", 1)[-1]) if query.data.count(":") == 2 else 1
        page_size = 5
        lines = [f"<b>Tus alertas</b> · {page}\n"]
        buttons = []
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            alerts = alert_service.list_user_alerts(session, user.id, limit=page_size + 1, offset=(page - 1) * page_size)
            has_next = len(alerts) > page_size
            for alert in alerts[:page_size]:
                status = "🟢 Activa" if alert.enabled and not alert.triggered else "⚪ Disparada / Inactiva"
                lines.append(
                    f"<b>#{alert.id} {escape(alert.symbol)}</b> {escape(alert.operator)} ${alert.target_value:,.2f}\n{status}\n"
                )
                buttons.append([InlineKeyboardButton(f"Borrar #{alert.id}", callback_data=f"alert_delete:{alert.id}")])
            if not alerts:
                lines.append("No hay alertas en esta página.")
        navigation = []
        if page > 1:
            navigation.append(InlineKeyboardButton("Anterior", callback_data=f"alert_menu:list:{page - 1}"))
        if has_next:
            navigation.append(InlineKeyboardButton("Siguiente", callback_data=f"alert_menu:list:{page + 1}"))
        if navigation:
            buttons.append(navigation)
        buttons.append([InlineKeyboardButton("Nueva alerta", callback_data="alert_menu:create")])
        buttons.append([InlineKeyboardButton("Volver", callback_data="alert_menu:back")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    @restricted
    async def handle_alert_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        alert_id = int(query.data.split(":")[1])

        with get_db_session() as session:
            alert = alert_service.alert_repo.get_by_id(session, alert_id)
            if not alert or alert.user.telegram_user_id != update.effective_user.id:
                await query.edit_message_text("Alerta no encontrada.")
                return
            if alert:
                sym = alert.symbol
                alert_service.delete_alert(session, alert)
                session.commit()
                await query.edit_message_text(f"Eliminé la alerta de <b>{sym}</b>.", parse_mode="HTML")

    @restricted
    async def handle_alert_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        text = (
            "<b>Alertas</b>\n\n"
            "Te aviso cuando una acción o un tipo de cambio llegue al precio que elijas."
        )
        await query.edit_message_text(text, reply_markup=get_alerts_menu_keyboard(), parse_mode="HTML")

    @restricted
    async def handle_alert_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Listo.")

    return {
        "list": handle_alert_list,
        "delete": handle_alert_delete,
        "back": handle_alert_back,
        "close": handle_alert_close,
    }
