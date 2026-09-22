"""Security and authorization utilities."""

from collections.abc import Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.identity import account_scope
from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.modules.auth.service import get_identity

logger = get_logger(__name__)


def is_user_authorized(user_id: int) -> bool:
    """Check if the given Telegram user ID matches the allowed user ID."""
    if not settings.TELEGRAM_ALLOWED_USER_ID:
        logger.warning("TELEGRAM_ALLOWED_USER_ID is not configured. Denying all access.")
        return False
    return user_id == settings.TELEGRAM_ALLOWED_USER_ID


def restricted(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to restrict handler or callback execution to authorized user only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        user = update.effective_user
        if not update.effective_chat or update.effective_chat.type != ChatType.PRIVATE:
            if update.callback_query:
                await update.callback_query.answer("Usa el bot en un chat privado.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text("Usa el bot en un chat privado.")
            return None
        if settings.MULTI_USER_ENABLED:
            if not user:
                return None
            with get_db_session() as session:
                identity = get_identity(session, user.id)
            if identity is None:
                if update.callback_query:
                    await update.callback_query.answer("Inicia sesión con /login.", show_alert=True)
                elif update.effective_message:
                    await update.effective_message.reply_text("Vincula tu cuenta con /login. No envíes tu API key por Telegram.")
                return None
            with account_scope(identity):
                return await func(update, context, *args, **kwargs)
        if not user or not is_user_authorized(user.id):
            user_id = user.id if user else "Unknown"
            logger.warning(f"Unauthorized access attempt from user_id={user_id}")
            if update.effective_message:
                await update.effective_message.reply_text("Este bot es privado.")
            elif update.callback_query:
                await update.callback_query.answer("Este bot es privado.", show_alert=True)
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper
