"""Ejecución de jobs por cuenta, con paginación y aislamiento de credenciales."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec

from sqlalchemy import select

from app.core.config import settings
from app.core.identity import account_scope, current_identity
from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.modules.auth.models import WallbitCredential
from app.modules.auth.service import get_identity

logger = get_logger(__name__)
Parameters = ParamSpec("Parameters")


def job_telegram_user_id() -> int:
    """Obtiene el único propietario permitido para el ciclo actual.

    Returns:
        ID Telegram de la cuenta del contexto o del propietario en modo privado.

    Raises:
        RuntimeError: Si un job multiusuario se ejecuta sin identidad.
    """
    if not settings.MULTI_USER_ENABLED:
        return settings.TELEGRAM_ALLOWED_USER_ID
    identity = current_identity.get()
    if identity is None:
        raise RuntimeError("Un job multiusuario necesita una cuenta autenticada.")
    return identity.telegram_user_id


def for_each_account(operation: Callable[Parameters, Awaitable[None]]) -> Callable[Parameters, Awaitable[None]]:
    """Ejecuta un job secuencialmente por cuenta sin cargar todos los secretos en memoria.

    Args:
        operation: Job que filtra sus consultas mediante job_telegram_user_id().

    Returns:
        Job compatible con APScheduler. Los errores de una cuenta no detienen las demás.
    """
    @wraps(operation)
    async def wrapper(*args: Parameters.args, **kwargs: Parameters.kwargs) -> None:
        if not settings.MULTI_USER_ENABLED:
            if settings.TELEGRAM_ALLOWED_USER_ID:
                await operation(*args, **kwargs)
            return
        last_id = 0
        while True:
            with get_db_session() as session:
                ids = list(session.scalars(select(WallbitCredential.telegram_user_id).where(
                    WallbitCredential.is_active.is_(True), WallbitCredential.telegram_user_id > last_id,
                ).order_by(WallbitCredential.telegram_user_id).limit(100)))
            if not ids:
                return
            for telegram_user_id in ids:
                last_id = telegram_user_id
                try:
                    with get_db_session() as session:
                        identity = get_identity(session, telegram_user_id)
                    if identity is None:
                        continue
                    with account_scope(identity):
                        await operation(*args, **kwargs)
                except Exception:
                    logger.exception("Falló el job %s para Telegram ID %s", operation.__name__, telegram_user_id)
    return wrapper
