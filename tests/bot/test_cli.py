"""Diagnóstico local usado antes del despliegue."""

from unittest.mock import AsyncMock

from app import __main__ as cli
from app.core.config import settings


def test_doctor_fails_when_wallbit_cannot_authenticate(monkeypatch, capsys):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)
    monkeypatch.setattr(settings, "WALLBIT_API_KEY", "test-wallbit-key")
    monkeypatch.setattr(settings, "WALLBIT_BASE_URL", "https://api.wallbit.io")
    monkeypatch.setattr(cli, "_check_database", lambda: True)
    monkeypatch.setattr(cli, "_check_telegram", AsyncMock(return_value=True))
    monkeypatch.setattr(cli, "_check_wallbit", AsyncMock(return_value=False))
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda _: object())

    assert cli.doctor() == 1
    assert "Wallbit         ERROR" in capsys.readouterr().out
