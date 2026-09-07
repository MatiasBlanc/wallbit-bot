"""Callback query handlers for configuration options."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.infrastructure.wallbit.client import WallbitClient
from app.modules.settings.handler import build_config_text
from app.modules.settings.keyboards import (
    get_config_main_keyboard,
    get_currency_keyboard,
    get_timezone_keyboard,
)
from app.modules.settings.repository import UserSettingsRepository

logger = get_logger(__name__)


def get_config_callbacks(client: WallbitClient, user_repo: UserSettingsRepository):
    @restricted
    async def handle_config_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            current_curr = user.default_currency

        text = (
            "<b>Moneda</b>\n\n"
            "Así se muestra tu saldo y el reporte de cada mañana."
        )
        await query.edit_message_text(
            text, reply_markup=get_currency_keyboard(current_curr), parse_mode="HTML"
        )

    @restricted
    async def handle_set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        new_curr = query.data.split(":")[1]

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            user_repo.update_currency(session, user, new_curr)
            session.commit()
            text = build_config_text(user)
            keyboard = get_config_main_keyboard(user.alerts_enabled)

        await query.answer(f"Moneda: {new_curr}")
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

    @restricted
    async def handle_config_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            current_tz = user.timezone

        text = "<b>Zona horaria</b>\n\nSirve para el reporte diario y las compras programadas."
        await query.edit_message_text(
            text, reply_markup=get_timezone_keyboard(current_tz), parse_mode="HTML"
        )

    @restricted
    async def handle_set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        new_tz = query.data.split(":", 1)[1]

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            user_repo.update_timezone(session, user, new_tz)
            session.commit()
            text = build_config_text(user)
            keyboard = get_config_main_keyboard(user.alerts_enabled)

        await query.answer("Zona actualizada")
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

    @restricted
    async def handle_toggle_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            new_status = not user.alerts_enabled
            user_repo.update_alerts_enabled(session, user, new_status)
            session.commit()
            text = build_config_text(user)
            keyboard = get_config_main_keyboard(user.alerts_enabled)

        alert_msg = "Alertas activadas" if new_status else "Alertas pausadas"
        await query.answer(alert_msg)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

    @restricted
    async def handle_config_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        health = context.application.bot_data.get("wallbit_health")
        if health is not None:
            connected = await health.refresh()
        else:
            connected = await client.check_connection()
        status_text = (
            "🟢 Conectado a Wallbit."
            if connected else "🔴 Sin conexión. Revisa tu API key de Wallbit."
        )

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            text = f"{build_config_text(user)}\n{status_text}"
            keyboard = get_config_main_keyboard(user.alerts_enabled)

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

    @restricted
    async def handle_config_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            text = build_config_text(user)
            keyboard = get_config_main_keyboard(user.alerts_enabled)

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

    @restricted
    async def handle_config_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Ajustes listos.")

    return {
        "currency": handle_config_currency,
        "set_currency": handle_set_currency,
        "timezone": handle_config_timezone,
        "set_timezone": handle_set_timezone,
        "toggle_alerts": handle_toggle_alerts,
        "status": handle_config_status,
        "back": handle_config_back,
        "close": handle_config_close,
    }
