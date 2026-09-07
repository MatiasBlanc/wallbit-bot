"""Estado de conexión Wallbit, actualizado en segundo plano y nunca usado para comprar."""

import time
from dataclasses import dataclass

from app.core.config import settings
from app.core.identity import current_identity
from app.core.logging import get_logger
from app.infrastructure.wallbit.client import WallbitClient

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ConnectionSnapshot:
    """Última comprobación de una cuenta; is_connected None significa que aún no hay dato."""

    is_connected: bool | None
    checked_at: float | None


class WallbitHealth:
    """Mantiene el cliente HTTP caliente y un estado de conexión por cuenta."""

    def __init__(self, client: WallbitClient) -> None:
        self.client = client
        self._snapshots: dict[int, ConnectionSnapshot] = {}

    def _account_id(self) -> int:
        if settings.MULTI_USER_ENABLED:
            identity = current_identity.get()
            return identity.telegram_user_id if identity is not None else 0
        return settings.TELEGRAM_ALLOWED_USER_ID

    def snapshot(self) -> ConnectionSnapshot:
        """Devuelve el último estado conocido de la cuenta del contexto.

        Returns:
            Instantánea en memoria; no consulta la red.
        """
        return self._snapshots.get(self._account_id(), ConnectionSnapshot(None, None))

    def label(self) -> str:
        """Texto corto para /start y /config, sin bloquear.

        Returns:
            Etiqueta de conexión lista para Telegram.
        """
        current = self.snapshot()
        if current.is_connected is None:
            return "⏳ Comprobando…"
        return "🟢 Conectado" if current.is_connected else "🔴 Desconectado"

    async def refresh(self) -> bool:
        """Consulta Wallbit y actualiza solo si el resultado cambió.

        Returns:
            True si la API respondió autenticada.

        Raises:
            asyncio.CancelledError: Si se cancela el refresco en segundo plano.
        """
        account_id = self._account_id()
        previous = self._snapshots.get(account_id)
        is_connected = await self.client.check_connection()
        self._snapshots[account_id] = ConnectionSnapshot(is_connected, time.monotonic())
        if previous is None or previous.is_connected != is_connected:
            logger.info(
                "Estado Wallbit %s para la cuenta %s",
                "conectado" if is_connected else "desconectado",
                account_id,
            )
        return is_connected
