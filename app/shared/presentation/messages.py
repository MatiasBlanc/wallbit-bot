"""Mensajes transversales de la interfaz de Telegram."""

from collections.abc import Awaitable, Callable
from typing import Any

from telegram.error import TelegramError

from app.infrastructure.wallbit.exceptions import (
    WallbitApiException,
    WallbitAuthenticationError,
    WallbitRateLimitError,
    WallbitUnavailableError,
)


def format_loading(action: str) -> str:
    """Genera feedback breve mientras una consulta externa está en curso."""
    return f"⏳ {action}..."


def format_error(error: Exception) -> str:
    """Convierte errores de dominio en un mensaje seguro y accionable."""
    if isinstance(error, WallbitRateLimitError):
        return "Wallbit está limitando temporalmente las consultas. Inténtalo en unos segundos."
    if isinstance(error, WallbitAuthenticationError):
        return "No pude autenticarme con Wallbit. Revisa la configuración de tu API key."
    if isinstance(error, WallbitUnavailableError):
        return "No pude consultar Wallbit en este momento. Inténtalo nuevamente más tarde."
    if isinstance(error, WallbitApiException):
        return error.user_message
    return "No pude completar la consulta. Inténtalo nuevamente más tarde."


async def edit_or_reply(
    message: Any,
    text: str,
    *,
    parse_mode: str | None = None,
    reply_markup: Any = None,
) -> None:
    """Edita el feedback inicial y usa una respuesta nueva si Telegram lo impide."""
    try:
        await message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except TelegramError:
        await message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)


async def run_with_feedback(
    message: Any,
    action: str,
    operation: Callable[[], Awaitable[str]],
    *,
    parse_mode: str | None = None,
    reply_markup: Any = None,
) -> None:
    """Muestra loading, ejecuta una lectura y reemplaza el mismo mensaje."""
    loading = await message.reply_text(format_loading(action))
    try:
        result = await operation()
    except Exception as error:
        await edit_or_reply(loading, format_error(error), parse_mode=parse_mode)
        return
    await edit_or_reply(loading, result, parse_mode=parse_mode, reply_markup=reply_markup)
