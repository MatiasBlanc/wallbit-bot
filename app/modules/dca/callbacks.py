"""Callback query handlers for DCA management actions."""

from html import escape

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.modules.dca.conversation import format_asset_label
from app.core.constants import DCA_FREQ_WEEKLY, WEEKDAY_NAMES_ES
from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.dca.keyboards import get_dca_item_keyboard, get_dca_menu_keyboard
from app.modules.dca.service import DCAService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.datetime import format_date_short

logger = get_logger(__name__)


def get_dca_callbacks(dca_service: DCAService, user_repo: UserSettingsRepository):
    async def show_rules(query: CallbackQuery, user_id: int, is_active: bool) -> None:
        page = int(query.data.rsplit(":", 1)[-1]) if query.data.count(":") == 2 else 1
        page_size = 5
        menu = "active" if is_active else "paused"
        status = "activas" if is_active else "pausadas"
        lines = [f"<b>Compras {status}</b> · {page}\n"]
        buttons = []
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            list_rules = dca_service.list_active_rules if is_active else dca_service.list_paused_rules
            rules = list_rules(session, user.id, limit=page_size + 1, offset=(page - 1) * page_size)
            has_next = len(rules) > page_size
            for rule in rules[:page_size]:
                day = (f"Cada {WEEKDAY_NAMES_ES.get(rule.weekday, 'semana')}" if rule.frequency == DCA_FREQ_WEEKLY
                       else f"Día {rule.day_of_month:02d} de cada mes")
                asset_name = rule.asset_name or rule.ticker
                lines.append(f"<b>#{rule.id} {escape(rule.ticker)}</b> ({escape(asset_name)})\n{day} — ${rule.amount_usd:,.2f} USD")
                if is_active:
                    lines.append(f"Próxima: {format_date_short(rule.next_execution_at)}")
                action, label = ("pause", "Pausar") if is_active else ("resume", "Reactivar")
                buttons.append([
                    InlineKeyboardButton(f"{label} #{rule.id}", callback_data=f"dca_{action}:{rule.id}"),
                    InlineKeyboardButton(f"Borrar #{rule.id}", callback_data=f"dca_delete:{rule.id}"),
                ])
            if not rules:
                lines.append("No hay compras en esta lista.")
        navigation = []
        if page > 1:
            navigation.append(InlineKeyboardButton("Anterior", callback_data=f"dca_menu:{menu}:{page - 1}"))
        if has_next:
            navigation.append(InlineKeyboardButton("Siguiente", callback_data=f"dca_menu:{menu}:{page + 1}"))
        if navigation:
            buttons.append(navigation)
        buttons.append([InlineKeyboardButton("Nueva compra", callback_data="dca_menu:create")])
        buttons.append([InlineKeyboardButton("Volver", callback_data="dca_menu:back")])
        # Una sola edición por página, después de cerrar la sesión de base de datos.
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    @restricted
    async def handle_dca_menu_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.callback_query.answer()
        await show_rules(update.callback_query, update.effective_user.id, True)

    @restricted
    async def handle_dca_menu_paused(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.callback_query.answer()
        await show_rules(update.callback_query, update.effective_user.id, False)

    @restricted
    async def handle_dca_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        rule_id = int(query.data.split(":")[1])

        with get_db_session() as session:
            rule = dca_service.get_rule(session, rule_id)
            if not rule or rule.user.telegram_user_id != update.effective_user.id:
                await query.edit_message_text("No encontré esa compra.")
                return
            if rule:
                dca_service.pause_rule(session, rule)
                session.commit()
                asset_label = format_asset_label(rule.ticker, rule.asset_name)
                await query.edit_message_text(
                    f"Pausé la compra de <b>{asset_label}</b> (${rule.amount_usd:,.2f} USD).",
                    reply_markup=get_dca_item_keyboard(rule.id, is_active=False),
                    parse_mode="HTML",
                )

    @restricted
    async def handle_dca_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        rule_id = int(query.data.split(":")[1])

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            rule = dca_service.get_rule(session, rule_id)
            if not rule or rule.user_id != user.id:
                await query.edit_message_text("No encontré esa compra.")
                return
            if rule:
                dca_service.reactivate_rule(session, rule, user)
                session.commit()
                next_date = format_date_short(rule.next_execution_at)
                asset_label = format_asset_label(rule.ticker, rule.asset_name)
                await query.edit_message_text(
                    f"Reactivé <b>{asset_label}</b>.\nPróxima compra: {next_date}",
                    reply_markup=get_dca_item_keyboard(rule.id, is_active=True),
                    parse_mode="HTML",
                )

    @restricted
    async def handle_dca_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        rule_id = int(query.data.split(":")[1])

        with get_db_session() as session:
            rule = dca_service.get_rule(session, rule_id)
            if not rule or rule.user.telegram_user_id != update.effective_user.id:
                await query.edit_message_text("No encontré esa compra.")
                return
            if rule:
                asset_label = format_asset_label(rule.ticker, rule.asset_name)
                dca_service.delete_rule(session, rule)
                session.commit()
                await query.edit_message_text(f"Eliminé la compra de <b>{asset_label}</b>.", parse_mode="HTML")

    @restricted
    async def handle_dca_menu_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        text = (
            "<b>Compras periódicas</b>\n\n"
            "Programa una compra semanal o mensual. Ese día te aviso para confirmarla."
        )
        await query.edit_message_text(text, reply_markup=get_dca_menu_keyboard(), parse_mode="HTML")

    @restricted
    async def handle_dca_menu_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Listo.")

    return {
        "active": handle_dca_menu_active,
        "paused": handle_dca_menu_paused,
        "pause": handle_dca_pause,
        "resume": handle_dca_resume,
        "delete": handle_dca_delete,
        "back": handle_dca_menu_back,
        "close": handle_dca_menu_close,
    }
