"""Concurrencia acotada para lecturas independientes, sin compartir sesiones ORM."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

Input = TypeVar("Input")
Output = TypeVar("Output")


async def map_limited(
    items: Sequence[Input],
    operation: Callable[[Input], Awaitable[Output]],
    limit: int,
) -> list[Output | Exception]:
    """Ejecuta lecturas con un número fijo de workers y conserva su orden.

    Args:
        items: Entradas de las lecturas; nunca se crea una tarea por entrada.
        operation: Lectura asíncrona independiente, sin acceso a una sesión compartida.
        limit: Máximo de workers simultáneos.

    Returns:
        Resultados o excepciones por entrada. El llamador debe tratar los errores.

    Raises:
        ValueError: Si limit no es positivo.
        asyncio.CancelledError: Si se cancela el trabajo, incluidos sus workers.
    """
    if limit < 1:
        raise ValueError("El límite de concurrencia debe ser positivo.")
    pending = iter(enumerate(items))
    results: dict[int, Output | Exception] = {}

    async def worker() -> None:
        for index, item in pending:
            try:
                results[index] = await operation(item)
            except Exception as error:
                results[index] = error

    async with asyncio.TaskGroup() as group:
        for _ in range(min(limit, len(items))):
            group.create_task(worker())
    return [results[index] for index in range(len(items))]
