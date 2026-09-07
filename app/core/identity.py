"""Identidad aislada por tarea asíncrona; nunca se modifica el cliente compartido."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from pydantic import SecretStr


@dataclass(frozen=True, slots=True)
class AccountIdentity:
    """Cuenta autenticada para una actualización o un trabajo programado."""

    telegram_user_id: int
    api_key: SecretStr = field(repr=False)


current_identity: ContextVar[AccountIdentity | None] = ContextVar("wallbit_identity", default=None)


@contextmanager
def account_scope(identity: AccountIdentity) -> Iterator[None]:
    """Establece la cuenta de esta tarea y restaura el contexto incluso al cancelarla.

    Args:
        identity: Cuenta que autoriza las solicitudes Wallbit de esta tarea.

    Yields:
        None. El contexto se hereda en subtareas, no entre tareas independientes.
    """
    token = current_identity.set(identity)
    try:
        yield
    finally:
        current_identity.reset(token)
