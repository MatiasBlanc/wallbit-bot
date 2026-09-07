"""El monitor de conexión no envía compras y no bloquea /start."""

from unittest.mock import AsyncMock

from app.core.config import settings
from app.infrastructure.wallbit.health import WallbitHealth
from app.infrastructure.wallbit.jobs import refresh_wallbit_health


async def test_refresh_keeps_last_status_and_never_trades(mock_wallbit_client, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)
    mock_wallbit_client.check_connection = AsyncMock(return_value=True)
    health = WallbitHealth(mock_wallbit_client)
    assert health.label() == "⏳ Comprobando…"
    assert await health.refresh() is True
    assert health.label() == "🟢 Conectado"
    mock_wallbit_client.check_connection = AsyncMock(return_value=False)
    assert await health.refresh() is False
    assert health.label() == "🔴 Desconectado"
    mock_wallbit_client.create_trade.assert_not_called()


async def test_background_job_uses_account_scope(mock_wallbit_client, monkeypatch):
    monkeypatch.setattr(settings, "MULTI_USER_ENABLED", False)
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)
    mock_wallbit_client.check_connection = AsyncMock(return_value=True)
    health = WallbitHealth(mock_wallbit_client)
    await refresh_wallbit_health(health)
    assert health.label() == "🟢 Conectado"
    mock_wallbit_client.create_trade.assert_not_called()
