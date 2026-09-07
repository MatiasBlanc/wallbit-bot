"""Refresco periódico de la conexión Wallbit, sin tocar órdenes."""

from app.infrastructure.wallbit.health import WallbitHealth
from app.modules.auth.jobs import for_each_account


@for_each_account
async def refresh_wallbit_health(health: WallbitHealth) -> None:
    """Actualiza el estado de cada cuenta activa y deja el cliente HTTP listo.

    Args:
        health: Monitor compartido por el proceso.

    Returns:
        None. Un fallo de una cuenta no debe impedir el resto.

    Raises:
        asyncio.CancelledError: Si el scheduler se detiene durante la consulta.
    """
    await health.refresh()
