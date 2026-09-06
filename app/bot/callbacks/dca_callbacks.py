"""Callback query handlers for DCA management actions."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.keyboards.dca import get_dca_item_keyboard, get_dca_menu_keyboard
from app.core.constants import DCA_FREQ_WEEKLY, WEEKDAY_NAMES_ES
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.dca_service import DCAService
from app.utils.datetime_utils import format_date_short

logger = get_logger(__name__)


def get_dca_callbacks(dca_service: DCAService, user_repo: UserSettingsRepository):
    @restricted
    async def handle_dca_menu_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            rules = dca_service.list_active_rules(session, user.id)

            if not rules:
                await query.edit_message_text(
                    "📈 <b>No tienes estrategias DCA activas actualmente.</b>",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("➕ Crear DCA", callback_data="dca_menu:create")],
                         [InlineKeyboardButton("⬅️ Volver", callback_data="dca_menu:back")]]
                    ),
                    parse_mode="HTML",
                )
                return

            for i, rule in enumerate(rules, 1):
                next_date = format_date_short(rule.next_execution_at)
                if rule.frequency == DCA_FREQ_WEEKLY:
                    day_str = f"Cada {WEEKDAY_NAMES_ES.get(rule.weekday, 'semana')}"
                else:
                    day_str = f"Día {rule.day_of_month:02d} de cada mes"

                text = (
                    f"📈 <b>DCA Activo #{i}</b>\n\n"
                    f"<b>{rule.ticker}</b>\n"
                    f"${rule.amount_usd:,.2f} USD\n"
                    f"{day_str}\n"
                    f"Próxima: {next_date}"
                )
                keyboard = get_dca_item_keyboard(rule.id, is_active=True)
                await query.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

            # Clean up the original menu message or provide return button
            await query.edit_message_text(
                "Mostrando estrategias activas arriba.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Menú DCA", callback_data="dca_menu:back")]]
                ),
            )

    @restricted
    async def handle_dca_menu_paused(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            rules = dca_service.list_paused_rules(session, user.id)

            if not rules:
                await query.edit_message_text(
                    "⏸ <b>No tienes estrategias DCA pausadas.</b>",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Volver", callback_data="dca_menu:back")]]
                    ),
                    parse_mode="HTML",
                )
                return

            for i, rule in enumerate(rules, 1):
                if rule.frequency == DCA_FREQ_WEEKLY:
                    day_str = f"Cada {WEEKDAY_NAMES_ES.get(rule.weekday, 'semana')}"
                else:
                    day_str = f"Día {rule.day_of_month:02d} de cada mes"

                text = (
                    f"⏸ <b>DCA Pausado #{i}</b>\n\n"
                    f"<b>{rule.ticker}</b>\n"
                    f"${rule.amount_usd:,.2f} USD\n"
                    f"{day_str}"
                )
                keyboard = get_dca_item_keyboard(rule.id, is_active=False)
                await query.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

            await query.edit_message_text(
                "Mostrando estrategias pausadas arriba.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Menú DCA", callback_data="dca_menu:back")]]
                ),
            )

    @restricted
    async def handle_dca_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        rule_id = int(query.data.split(":")[1])

        with get_db_session() as session:
            rule = dca_service.get_rule(session, rule_id)
            if rule:
                dca_service.pause_rule(session, rule)
                session.commit()
                await query.edit_message_text(
                    f"⏸ Estrategia para <b>{rule.ticker}</b> (${rule.amount_usd:,.2f} USD) pausada.",
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
            if rule:
                dca_service.reactivate_rule(session, rule, user)
                session.commit()
                next_date = format_date_short(rule.next_execution_at)
                await query.edit_message_text(
                    f"▶️ Estrategia para <b>{rule.ticker}</b> reactivada.\nPróxima ejecución: {next_date}",
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
            if rule:
                ticker = rule.ticker
                dca_service.delete_rule(session, rule)
                session.commit()
                await query.edit_message_text(f"🗑 Estrategia DCA de <b>{ticker}</b> eliminada.", parse_mode="HTML")

    @restricted
    async def handle_dca_menu_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        text = "📈 <b>Gestión de DCA (Dollar-Cost Averaging)</b>\n\nElige una opción:"
        await query.edit_message_text(text, reply_markup=get_dca_menu_keyboard(), parse_mode="HTML")

    @restricted
    async def handle_dca_menu_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Menú DCA cerrado.")

    return {
        "active": handle_dca_menu_active,
        "paused": handle_dca_menu_paused,
        "pause": handle_dca_pause,
        "resume": handle_dca_resume,
        "delete": handle_dca_delete,
        "back": handle_dca_menu_back,
        "close": handle_dca_menu_close,
    }
