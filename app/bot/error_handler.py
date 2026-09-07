"""Manejo transversal de errores de Telegram."""

from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra el error usando el logger con sanitización de secretos.

    Args:
        update: Actualización que produjo el error; no se registra su contenido.
        context: Contexto de Telegram que contiene la excepción.

    Returns:
        None. No envía detalles internos al usuario.
    """
    if settings.MULTI_USER_ENABLED:
        # El decorador ya restauró la identidad; no registrar un traceback que pueda contener claves.
        logger.error("Falló una actualización de Telegram: %s", type(context.error).__name__)
    else:
        logger.error("Excepción al procesar una actualización:", exc_info=context.error)
