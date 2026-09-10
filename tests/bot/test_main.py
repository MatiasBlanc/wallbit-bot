"""Composición del bot y ciclo de vida sin red ni base de datos real."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from app.core.config import settings


async def test_main_wires_order_service_and_lifecycle(monkeypatch, mock_wallbit_client):
    import main as entrypoint

    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)
    monkeypatch.setattr(settings, "WALLBIT_API_KEY", "test-wallbit-key")
    init_db = Mock()
    application = Mock()
    application.bot_data = {}
    create_application = Mock(return_value=application)
    scheduler = Mock()
    monkeypatch.setattr(entrypoint, "init_db", init_db)
    startup_session = Mock()
    startup_session.execute.return_value.rowcount = 0
    monkeypatch.setattr(entrypoint, "get_db_session", lambda: nullcontext(startup_session))
    monkeypatch.setattr(entrypoint, "WallbitClient", Mock(return_value=mock_wallbit_client))
    monkeypatch.setattr(entrypoint, "create_bot_application", create_application)
    monkeypatch.setattr(entrypoint, "BotScheduler", Mock(return_value=scheduler))

    entrypoint.main()

    init_db.assert_called_once_with()
    dependencies = create_application.call_args.kwargs
    assert dependencies["dca_service"].order_service is dependencies["order_service"]
    application.run_polling.assert_called_once_with(
        drop_pending_updates=True, allowed_updates=["message", "callback_query"],
    )
    scheduler.start.assert_not_called()
    pending = []
    application.create_task.side_effect = pending.append
    await application.post_init(application)
    scheduler.start.assert_called_once_with()
    assert pending
    await pending[0]
    mock_wallbit_client.check_connection.assert_awaited()
    await application.post_shutdown(application)
    scheduler.shutdown.assert_called_once_with()
    mock_wallbit_client.close.assert_awaited_once_with()
    mock_wallbit_client.create_trade.assert_not_called()


def test_main_rejects_missing_wallbit_api_key(monkeypatch):
    import main as entrypoint

    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)
    monkeypatch.setattr(settings, "WALLBIT_API_KEY", "")
    init_db = Mock()
    monkeypatch.setattr(entrypoint, "init_db", init_db)

    with pytest.raises(SystemExit) as error:
        entrypoint.main()

    assert error.value.code == 1
    init_db.assert_not_called()
