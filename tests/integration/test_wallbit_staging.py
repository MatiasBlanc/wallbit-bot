"""Contrato de lectura contra Wallbit; nunca crea órdenes."""

import os

import pytest

from app.core.config import settings
from app.infrastructure.wallbit.client import WallbitClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_wallbit_read_only_contract() -> None:
    """Valida credenciales y esquemas de lectura sin ejecutar transacciones.

    La prueba requiere una key exclusiva de staging o de solo lectura y se ejecuta
    únicamente con ``RUN_WALLBIT_INTEGRATION=1``.
    """
    if os.getenv("RUN_WALLBIT_INTEGRATION") != "1":
        pytest.skip("Define RUN_WALLBIT_INTEGRATION=1 para probar Wallbit en staging.")
    if not settings.WALLBIT_API_KEY:
        pytest.fail("WALLBIT_API_KEY es obligatoria para la prueba de integración.")

    client = WallbitClient()
    try:
        assert await client.check_connection()
        checking = await client.get_checking_balance()
        stocks = await client.get_stocks_balance()
        assert isinstance(checking, list)
        assert isinstance(stocks, list)
    finally:
        await client.close()
