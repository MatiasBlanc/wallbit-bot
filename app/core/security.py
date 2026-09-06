"""Security and authorization utilities."""

from collections.abc import Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.logging import get_logger

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
