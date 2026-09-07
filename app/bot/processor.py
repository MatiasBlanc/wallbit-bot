"""Concurrencia entre usuarios sin intercalar las conversaciones de una misma persona."""

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import BaseUpdateProcessor


@dataclass(slots=True)
class UserQueue:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    waiters: int = 0


class PerUserUpdateProcessor(BaseUpdateProcessor):
    """Limita tareas globales y serializa por identidad Telegram, también entre chats."""

    def __init__(self, max_concurrent_updates: int = 8) -> None:
        super().__init__(max_concurrent_updates)
        self._queues: dict[int, UserQueue] = {}

    async def initialize(self) -> None:
        """Inicializa el procesador sin recursos externos.

        Returns:
            None.
        """

    async def shutdown(self) -> None:
        """Libera el registro una vez que Telegram termina sus tareas.

        Returns:
            None.
        """
        self._queues.clear()

    async def do_process_update(self, update: object, coroutine: Awaitable[object]) -> None:
        """Ejecuta una actualización conservando exclusión mutua por usuario.

        Args:
            update: Actualización Telegram; las que no tienen usuario comparten la clave 0.
            coroutine: Procesamiento suministrado por Application.

        Returns:
            None. Los locks se retiran cuando no tienen tareas en curso o esperando.

        Raises:
            Exception: Propaga errores del procesamiento; siempre libera su registro.
            asyncio.CancelledError: Propaga la cancelación y libera recursos.
        """
        user_id = update.effective_user.id if isinstance(update, Update) and update.effective_user else 0
        queue = self._queues.setdefault(user_id, UserQueue())
        queue.waiters += 1
        has_started = False
        try:
            async with queue.lock:
                has_started = True
                await coroutine
        finally:
            if not has_started and asyncio.iscoroutine(coroutine):
                coroutine.close()
            queue.waiters -= 1
            if not queue.waiters:
                del self._queues[user_id]
