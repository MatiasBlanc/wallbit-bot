"""Callback query handlers for configuration options."""

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.config import build_config_text
from app.bot.keyboards.config import (
    get_config_main_keyboard,
    get_currency_keyboard,
    get_timezone_keyboard,
)
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.wallbit.client import WallbitClient

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
            "💱 <b>Selecciona tu moneda por defecto</b>\n\n"
            "Se usará para calcular la conversión en /saldo y tus reportes matutinos:"
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

        await query.answer(f"Moneda cambiada a {new_curr}")
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

    @restricted
    async def handle_config_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            current_tz = user.timezone

        text = "🌍 <b>Selecciona tu zona horaria</b>\n\nDetermina a qué hora exacta se envían tus reportes y compras DCA:"
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

        await query.answer(f"Zona horaria: {new_tz}")
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

        alert_msg = "Alertas activadas" if new_status else "Alertas desactivadas"
        await query.answer(alert_msg)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

    @restricted
    async def handle_config_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer("Verificando conexión...")

        connected = await client.check_connection()
        status_text = "🟢 Conectado exitosamente con Wallbit API." if connected else "🔴 No se pudo conectar con Wallbit. Revisa tu WALLBIT_API_KEY."

        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            text = f"{build_config_text(user)}\n\n<b>Estado de Wallbit:</b> {status_text}"
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
        await query.edit_message_text("Menú de configuración cerrado.")

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
