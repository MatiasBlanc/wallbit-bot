"""Registro de comandos, conversaciones y callbacks sin conectar Telegram."""

import pytest
from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler
from telegram.warnings import PTBUserWarning

from app.bot.application import create_bot_application
from app.bot.error_handler import error_handler
from app.core.config import settings


@pytest.mark.parametrize("is_multi_user", [False, True])
def test_application_registers_all_routes(
    monkeypatch, mock_wallbit_client, user_repo, balance_service, portfolio_service,
    dca_service, order_service, alert_service, history_service, report_service, is_multi_user,
):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setattr(settings, "MULTI_USER_ENABLED", is_multi_user)
    # Las conversaciones mezclan texto y botones: conservan per_message=False.
    with pytest.warns(PTBUserWarning, match="per_message=False"):
        application = create_bot_application(
            client=mock_wallbit_client, user_repo=user_repo, balance_service=balance_service,
            portfolio_service=portfolio_service, dca_service=dca_service, order_service=order_service,
            alert_service=alert_service, history_service=history_service, report_service=report_service,
        )
    handlers = application.handlers[0]
    assert all(isinstance(handler, ConversationHandler) for handler in handlers[:3])
    assert not any(isinstance(handler, ConversationHandler) for handler in handlers[3:])
    assert application.concurrent_updates == (8 if is_multi_user else 1)
    if is_multi_user:
        assert {command for handler in application.handlers[-1] for command in handler.commands} == {"login", "logout"}
    else:
        assert -1 not in application.handlers
    assert application.update_queue.maxsize == 100

    commands = [command for handler in handlers if isinstance(handler, CommandHandler) for command in handler.commands]
    expected_commands = ["start", "saldo", "inv", "reporte", "historial", "dca", "alerta", "config", "estado", "status", "ordenes"]
    assert sorted(commands) == sorted(expected_commands)
    patterns = [handler.pattern.pattern for handler in handlers if isinstance(handler, CallbackQueryHandler)]
    assert set(patterns) == {
        r"^order_confirm:", r"^order_skip:",
        r"^dca_menu:active(?::[1-9]\d*)?$", r"^dca_menu:paused(?::[1-9]\d*)?$", r"^dca_menu:back$", r"^dca_menu:close$",
        r"^dca_pause:", r"^dca_resume:", r"^dca_delete:",
        r"^alert_menu:list(?::[1-9]\d*)?$", r"^alert_menu:back$", r"^alert_menu:close$", r"^alert_delete:",
        r"^history_page:",
        r"^config:currency$", r"^set_currency:", r"^config:timezone$", r"^set_tz:",
        r"^config:toggle_alerts$", r"^config:status$", r"^config:back$", r"^config:close$",
    }
    assert len(patterns) == len(set(patterns))
    assert error_handler in application.error_handlers
    mock_wallbit_client.check_connection.assert_not_called()
    mock_wallbit_client.create_trade.assert_not_called()
