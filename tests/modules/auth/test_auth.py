"""Regresiones de vinculación, cifrado y aislamiento; no se usa ninguna API real."""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.identity import AccountIdentity, account_scope, current_identity
from app.core.logging import SecretSanitizingFormatter
from app.core.security import restricted
from app.infrastructure.database import database
from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.exceptions import OrderExecutionError, WallbitAuthenticationError
from app.infrastructure.wallbit.schemas.orders import TradeRequest
from app.modules.auth.commands import login_command, logout_command
from app.modules.auth.jobs import for_each_account, job_telegram_user_id
from app.modules.auth.models import WallbitCredential
from app.modules.auth.service import (
    get_identity,
    issue_login_code,
    logout,
    redeem_login_code,
    validate_multi_user_config,
)
from app.modules.settings.models import UserSettings
from app.shared.exchange.service import ExchangeRateService


@pytest.fixture
def multi_user(monkeypatch, db_session):
    monkeypatch.setattr(settings, "MULTI_USER_ENABLED", True)
    monkeypatch.setattr(settings, "TRADING_ENABLED", False)
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False))
    return db_session


def activate(session, user_id, key=None):
    code = issue_login_code(session, user_id, SecretStr(key or f"test-api-key-{user_id}"))
    assert redeem_login_code(session, user_id, code)
    session.commit()
    return get_identity(session, user_id)


def make_update(user_id=101, chat_type="private"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.type = chat_type
    update.effective_message.reply_text = AsyncMock()
    update.effective_message.delete = AsyncMock()
    update.callback_query = None
    return update


def test_encrypted_code_bound_to_owner_single_use(multi_user):
    session = multi_user
    code = issue_login_code(session, 101, SecretStr("test-secret-api-key"))
    session.commit()
    credential = session.get(WallbitCredential, 101)
    assert "test-secret-api-key" not in credential.encrypted_api_key
    assert code != credential.login_code_hash
    assert credential.login_code_hash == hashlib.sha256(code.encode()).hexdigest()
    assert get_identity(session, 101) is None
    assert not redeem_login_code(session, 202, code)
    assert redeem_login_code(session, 101, code)
    session.commit()
    assert not redeem_login_code(session, 101, code)
    session.expire_all()
    identity = get_identity(session, 101)
    assert identity.api_key.get_secret_value() == "test-secret-api-key"
    assert "test-secret-api-key" not in repr(identity)
    assert session.query(UserSettings).count() == 1


def test_expiry_renewal_and_account_replacement_rejected(multi_user):
    session = multi_user
    code = issue_login_code(session, 101, SecretStr("test-key"))
    credential = session.get(WallbitCredential, 101)
    credential.login_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()
    assert not redeem_login_code(session, 101, code)
    with pytest.raises(ValueError, match="ya existe"):
        issue_login_code(session, 101, SecretStr("different-account-key"))
    new_code = issue_login_code(session, 101)
    session.commit()
    assert not redeem_login_code(session, 101, code)
    assert redeem_login_code(session, 101, new_code)


def test_legacy_account_cannot_be_implicitly_rebound(multi_user, user_repo):
    user_repo.get_or_create(multi_user, 101)
    multi_user.commit()
    with pytest.raises(ValueError, match="base nueva"):
        issue_login_code(multi_user, 101, SecretStr("test-key"))


def test_logout_isolated_and_invalidates_codes(multi_user):
    session = multi_user
    activate(session, 101)
    activate(session, 202)
    code = issue_login_code(session, 101)
    logout(session, 101)
    session.commit()
    session.expire_all()
    assert get_identity(session, 101) is None
    assert get_identity(session, 202) is not None
    assert not redeem_login_code(session, 101, code)


def test_wrong_encryption_key_fails_closed(multi_user, monkeypatch):
    activate(multi_user, 101)
    monkeypatch.setattr(settings, "CREDENTIAL_ENCRYPTION_KEY", SecretStr(Fernet.generate_key().decode()))
    with pytest.raises(ValueError, match="descifrar"):
        get_identity(multi_user, 101)


@pytest.mark.parametrize("setting,value", [
    ("CREDENTIAL_ENCRYPTION_KEY", SecretStr("")),
    ("WALLBIT_BASE_URL", "http://api.wallbit.io"),
    ("TRADING_ENABLED", True),
])
def test_unsafe_configuration_rejected(multi_user, monkeypatch, setting, value):
    monkeypatch.setattr(settings, setting, value)
    with pytest.raises(ValueError):
        validate_multi_user_config()


async def test_restricted_requires_login_and_private_chat(multi_user):
    called = AsyncMock()
    handler = restricted(called)
    update = make_update()
    await handler(update, MagicMock())
    called.assert_not_awaited()
    activate(multi_user, 101)
    update.effective_chat.type = "supergroup"
    await handler(update, MagicMock())
    called.assert_not_awaited()
    update.effective_chat.type = "private"
    called.side_effect = lambda *args: current_identity.get().telegram_user_id
    assert await handler(update, MagicMock()) == 101
    assert current_identity.get() is None


async def test_identity_restored_on_failure(multi_user):
    activate(multi_user, 101)

    @restricted
    async def fail(update, context):
        assert current_identity.get().telegram_user_id == 101
        raise RuntimeError("test")

    with pytest.raises(RuntimeError):
        await fail(make_update(), MagicMock())
    assert current_identity.get() is None


async def test_login_command_and_logout_without_api_keys_in_chat(multi_user):
    code = issue_login_code(multi_user, 101, SecretStr("test-secret-key"))
    multi_user.commit()
    update = make_update()
    context = MagicMock(args=[code], user_data={})
    await login_command(update, context)
    update.effective_message.delete.assert_awaited_once()
    assert context.args == []
    assert "Cuenta vinculada" in update.effective_message.reply_text.call_args.args[0]
    multi_user.expire_all()
    assert get_identity(multi_user, 101)
    await logout_command(update, context)
    multi_user.expire_all()
    assert get_identity(multi_user, 101) is None


async def test_http_pool_isolates_headers_under_concurrency(multi_user):
    seen = []
    async def respond(request):
        await asyncio.sleep(0)
        seen.append((request.headers["X-API-Key"], request.headers.get("Cookie")))
        return httpx.Response(200, headers={"Set-Cookie": "account=unsafe; Path=/"}, json={"data": []})

    async with WallbitClient(api_key="GLOBAL-MUST-NOT-LEAK") as client:
        client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(respond))
        async def call(user_id):
            with account_scope(AccountIdentity(user_id, SecretStr(f"key-{user_id}"))):
                await client.get_checking_balance()
                await client.get_checking_balance()
        await asyncio.gather(call(101), call(202))
        with pytest.raises(WallbitAuthenticationError):
            await client.get_checking_balance()
        assert "X-API-Key" not in client._client.headers
    assert sorted(key for key, _ in seen) == ["key-101", "key-101", "key-202", "key-202"]
    assert all(not cookie for _, cookie in seen)


async def test_multi_user_never_sends_real_trades(multi_user):
    async with WallbitClient() as client:
        with pytest.raises(OrderExecutionError):
            await client.create_trade(TradeRequest(symbol="VOO", amount=1))
        assert client._client is None


async def test_exchange_cache_partitioned_and_bounded(multi_user):
    provider = AsyncMock()
    provider.get_rate.side_effect = [950.0, 960.0]
    service = ExchangeRateService(provider, max_cache_entries=4)
    for user_id, expected in [(101, 950.0), (202, 960.0), (101, 950.0)]:
        with account_scope(AccountIdentity(user_id, SecretStr("key"))):
            assert await service.get_rate("USD", "CLP") == expected
    assert provider.get_rate.await_count == 2
    assert len(service._cache) <= 4
    with pytest.raises(WallbitAuthenticationError):
        await service.get_rate("USD", "CLP")


async def test_jobs_process_only_active_accounts_and_continue_after_failure(multi_user):
    for user_id in [101, 202, 303]:
        activate(multi_user, user_id)
    logout(multi_user, 303)
    multi_user.commit()
    seen = []

    @for_each_account
    async def job():
        seen.append(job_telegram_user_id())
        if job_telegram_user_id() == 101:
            raise RuntimeError("Una cuenta no debe detener las demás")

    await job()
    assert seen == [101, 202]
    assert current_identity.get() is None


def test_formatter_scrubs_nested_objects_and_tracebacks():
    secret = "sensitive-test-credential"
    formatter = SecretSanitizingFormatter(logging.Formatter(), [])
    try:
        raise RuntimeError(secret)
    except RuntimeError:
        import sys
        record = logging.LogRecord("test", logging.ERROR, "", 0, "payload=%s", ({"key": secret},), sys.exc_info())
    with account_scope(AccountIdentity(101, SecretStr(secret))):
        text = formatter.format(record)
    assert secret not in text
    assert "REDACTED" in text


@pytest.mark.parametrize("action", ["pause", "resume", "delete"])
async def test_dca_callbacks_cannot_mutate_another_account(multi_user, dca_service, user_repo, action):
    from app.modules.dca.callbacks import get_dca_callbacks
    activate(multi_user, 101)
    activate(multi_user, 202)
    owner = user_repo.get_by_telegram_id(multi_user, 202)
    rule = dca_service.create_rule(multi_user, owner, "VOO", 10, "weekly", weekday=0)
    multi_user.commit()
    rule_id = rule.id
    update = make_update(101)
    update.callback_query = MagicMock(data=f"dca_{action}:{rule_id}")
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    await get_dca_callbacks(dca_service, user_repo)[action](update, MagicMock())
    multi_user.expire_all()
    persisted = dca_service.get_rule(multi_user, rule_id)
    assert persisted is not None and persisted.enabled
    update.callback_query.edit_message_text.assert_awaited_once_with("No encontré esa compra.")


async def test_alert_delete_cannot_mutate_another_account(multi_user, alert_service, user_repo):
    from app.modules.alerts.callbacks import get_alert_callbacks
    activate(multi_user, 101)
    activate(multi_user, 202)
    owner = user_repo.get_by_telegram_id(multi_user, 202)
    alert = alert_service.create_alert(multi_user, owner, "price", "VOO", ">=", 100)
    multi_user.commit()
    alert_id = alert.id
    update = make_update(101)
    update.callback_query = MagicMock(data=f"alert_delete:{alert_id}")
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    await get_alert_callbacks(alert_service, user_repo)["delete"](update, MagicMock())
    multi_user.expire_all()
    assert alert_service.alert_repo.get_by_id(multi_user, alert_id) is not None


async def test_skip_order_checks_owner_and_persists(multi_user, order_service, user_repo):
    from app.modules.orders.callbacks import get_order_callbacks
    activate(multi_user, 101)
    activate(multi_user, 202)
    owner = user_repo.get_by_telegram_id(multi_user, 202)
    order = order_service.create_pending_order(multi_user, owner, "VOO", 10)
    multi_user.commit()
    order_id = order.id
    update = make_update(101)
    update.callback_query = MagicMock(data=f"order_skip:{order_id}")
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    skip = get_order_callbacks(order_service, user_repo)[1]
    await skip(update, MagicMock())
    multi_user.expire_all()
    assert order_service.order_repo.get_by_id(multi_user, order_id).status == "pending"
    update.effective_user.id = 202
    await skip(update, MagicMock())
    multi_user.expire_all()
    assert order_service.order_repo.get_by_id(multi_user, order_id).status == "skipped"


async def test_dca_job_reuses_reads_and_isolates_accounts(multi_user, dca_service, user_repo, mock_wallbit_client):
    from app.modules.dca.jobs import run_dca_checker
    from app.modules.orders.models import PendingOrder
    for user_id in [101, 202]:
        activate(multi_user, user_id)
        user = user_repo.get_by_telegram_id(multi_user, user_id)
        for _ in range(5):
            rule = dca_service.create_rule(multi_user, user, "VOO", 10, "weekly", weekday=0)
            rule.next_execution_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    multi_user.commit()
    seen = []
    async def checking():
        seen.append(current_identity.get().telegram_user_id)
        from app.infrastructure.wallbit.schemas.balance import CheckingBalanceItem
        return [CheckingBalanceItem(currency="USD", balance=100)]
    mock_wallbit_client.get_checking_balance.side_effect = checking
    bot = AsyncMock()
    await run_dca_checker(bot, dca_service)
    assert seen == [101, 202]
    assert mock_wallbit_client.get_checking_balance.await_count == 2
    assert mock_wallbit_client.get_stocks_balance.await_count == 2
    assert mock_wallbit_client.get_asset.await_count == 2
    assert bot.send_message.await_count == 10
    first_message = bot.send_message.call_args_list[0].kwargs["text"]
    assert "<b>Hoy toca comprar</b>" in first_message
    assert "Comisión estimada: <b>$0.04 USD</b>" in first_message
    assert "Total aproximado: <b>$10.04 USD</b>" in first_message
    assert bot.send_message.call_args_list[0].kwargs["reply_markup"].inline_keyboard[0][0].text == "Comprar"
    assert bot.send_message.call_args_list[0].kwargs["reply_markup"].inline_keyboard[0][1].text == "Ahora no"
    assert [call.kwargs["chat_id"] for call in bot.send_message.call_args_list] == [101] * 5 + [202] * 5
    multi_user.expire_all()
    assert multi_user.query(PendingOrder).count() == 10
    mock_wallbit_client.create_trade.assert_not_awaited()


async def test_alert_job_uses_each_accounts_quotes(multi_user, alert_service, user_repo, mock_wallbit_client):
    from app.infrastructure.wallbit.schemas.portfolio import AssetDetails
    from app.modules.alerts.jobs import run_alert_checker
    for user_id in [101, 202]:
        activate(multi_user, user_id)
        user = user_repo.get_by_telegram_id(multi_user, user_id)
        alert_service.create_alert(multi_user, user, "price", "VOO", ">=", 100)
    multi_user.commit()
    async def quote(symbol):
        price = 200 if current_identity.get().telegram_user_id == 101 else 50
        return AssetDetails(symbol=symbol, name=symbol, price=price)
    mock_wallbit_client.get_asset.side_effect = quote
    bot = AsyncMock()
    await run_alert_checker(bot, alert_service)
    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args.kwargs["chat_id"] == 101
    multi_user.expire_all()
    owner = user_repo.get_by_telegram_id(multi_user, 202)
    assert alert_service.list_user_alerts(multi_user, owner.id)[0].triggered is False


async def test_daily_reports_scope_account_and_survive_restart(multi_user, user_repo):
    from app.modules.reports.jobs import run_daily_report_check
    for user_id in [101, 202]:
        activate(multi_user, user_id)
        user = user_repo.get_by_telegram_id(multi_user, user_id)
        user.timezone = "UTC"
        user.report_time = "00:00"
    multi_user.commit()
    service = MagicMock()
    service.generate_report = AsyncMock()
    async def generate(session, user):
        assert user.telegram_user_id == current_identity.get().telegram_user_id
        return MagicMock(to_telegram_message=lambda: "Reporte de prueba")
    service.generate_report.side_effect = generate
    bot = AsyncMock()
    await run_daily_report_check(bot, service)
    await run_daily_report_check(bot, service)
    assert [call.kwargs["chat_id"] for call in bot.send_message.call_args_list] == [101, 202]
