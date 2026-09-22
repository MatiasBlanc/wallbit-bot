"""Narrowing seguro de campos opcionales de Telegram Update."""

from telegram import CallbackQuery, Message, Update, User


def require_callback(update: Update) -> CallbackQuery:
    """Obtiene un callback o aborta el handler si el update no lo contiene.

    Args:
        update: Actualización recibida por Telegram.

    Returns:
        CallbackQuery válido para editar o responder el mensaje.

    Raises:
        ValueError: Si el handler recibió un update sin callback.
    """
    if update.callback_query is None:
        raise ValueError("El handler requiere un callback de Telegram.")
    return update.callback_query


def require_message(update: Update) -> Message:
    """Obtiene el mensaje efectivo o aborta el handler de forma explícita.

    Args:
        update: Actualización recibida por Telegram.

    Returns:
        Mensaje efectivo disponible.

    Raises:
        ValueError: Si el update no contiene mensaje accesible.
    """
    if update.effective_message is None:
        raise ValueError("El handler requiere un mensaje de Telegram.")
    return update.effective_message


def require_user(update: Update) -> User:
    """Obtiene el usuario autenticado por Telegram.

    Args:
        update: Actualización recibida por Telegram.

    Returns:
        Usuario efectivo.

    Raises:
        ValueError: Si el update no está asociado a un usuario.
    """
    if update.effective_user is None:
        raise ValueError("El handler requiere un usuario de Telegram.")
    return update.effective_user
