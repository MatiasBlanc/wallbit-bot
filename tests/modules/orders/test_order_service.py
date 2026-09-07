"""Tests for OrderService including idempotency, simulation mode, and expirations."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.constants import (
    DCA_FREQ_WEEKLY,
    ORDER_STATUS_EXECUTED,
    ORDER_STATUS_EXPIRED,
    ORDER_STATUS_UNKNOWN,
)
from app.infrastructure.wallbit.exceptions import WallbitUnavailableError
from app.modules.dca.repository import DCARuleRepository
from app.modules.orders.repository import PendingOrderRepository
from app.modules.orders.service import OrderService


@pytest.mark.asyncio
async def test_confirm_order_simulation_mode(
    order_service: OrderService,
    order_repo: PendingOrderRepository,
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "TRADING_ENABLED", False)

    # Create a pending order
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    order = order_repo.create(
        session=db_session,
        user_id=test_user.id,
        ticker="VOO",
        amount_usd=50.0,
        expires_at=expires_at,
        idempotency_key="test-key-sim-1",
    )
    db_session.commit()

    result = await order_service.confirm_order(
        session=db_session, order_id=order.id, user=test_user
    )

    assert result.success is True
    assert result.is_simulation is True
    assert result.order_id.startswith("SIM-")
    assert result.ticker == "VOO"
    assert result.amount_usd == 50.0

    # Verify DB state
    refreshed_order = order_repo.get_by_id(db_session, order.id)
    assert refreshed_order.status == ORDER_STATUS_EXECUTED
    assert refreshed_order.external_order_id == result.order_id


@pytest.mark.asyncio
async def test_confirm_order_real_mode(
    order_service: OrderService,
    order_repo: PendingOrderRepository,
    mock_wallbit_client,
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "TRADING_ENABLED", True)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    order = order_repo.create(
        session=db_session,
        user_id=test_user.id,
        ticker="VOO",
        amount_usd=50.0,
        expires_at=expires_at,
        idempotency_key="test-key-real-1",
    )
    db_session.commit()

    result = await order_service.confirm_order(
        session=db_session, order_id=order.id, user=test_user
    )

    assert result.success is True
    assert result.is_simulation is False
    assert result.order_id == "ORD-12345678"
    mock_wallbit_client.create_trade.assert_called_once()

    refreshed_order = order_repo.get_by_id(db_session, order.id)
    assert refreshed_order.status == ORDER_STATUS_EXECUTED


@pytest.mark.asyncio
async def test_confirm_order_idempotency_duplicate_callback(
    order_service: OrderService,
    order_repo: PendingOrderRepository,
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "TRADING_ENABLED", False)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    order = order_repo.create(
        session=db_session,
        user_id=test_user.id,
        ticker="VOO",
        amount_usd=50.0,
        expires_at=expires_at,
        idempotency_key="test-key-idempotent",
    )
    db_session.commit()

    # First click: success
    res1 = await order_service.confirm_order(
        session=db_session, order_id=order.id, user=test_user
    )
    assert res1.success is True

    # Second click: must be rejected with already_processed
    res2 = await order_service.confirm_order(
        session=db_session, order_id=order.id, user=test_user
    )
    assert res2.success is False
    assert res2.already_processed is True
    assert "ya fue procesada" in res2.error_message


@pytest.mark.asyncio
async def test_confirm_order_expired(
    order_service: OrderService,
    order_repo: PendingOrderRepository,
    db_session,
    test_user,
):
    # Expired 1 hour ago
    past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
    order = order_repo.create(
        session=db_session,
        user_id=test_user.id,
        ticker="VOO",
        amount_usd=50.0,
        expires_at=past_expiry,
        idempotency_key="test-key-expired",
    )
    db_session.commit()

    result = await order_service.confirm_order(
        session=db_session, order_id=order.id, user=test_user
    )
    assert result.success is False
    assert "ha expirado" in result.error_message

    refreshed = order_repo.get_by_id(db_session, order.id)
    assert refreshed.status == ORDER_STATUS_EXPIRED


@pytest.mark.asyncio
async def test_trade_timeout_requires_verification_without_retry(
    order_service: OrderService,
    order_repo: PendingOrderRepository,
    mock_wallbit_client,
    db_session,
    test_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "TRADING_ENABLED", True)
    mock_wallbit_client.create_trade.side_effect = WallbitUnavailableError()
    order = order_repo.create(
        session=db_session,
        user_id=test_user.id,
        ticker="VOO",
        amount_usd=50.0,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        idempotency_key="test-key-timeout",
    )
    db_session.commit()

    result = await order_service.confirm_order(db_session, order.id, test_user)

    assert result.success is False
    assert "no la reintentes" in result.error_message
    assert order_repo.get_by_id(db_session, order.id).status == ORDER_STATUS_UNKNOWN
    mock_wallbit_client.create_trade.assert_awaited_once()


async def test_confirm_order_with_paused_dca_rule(
    order_service: OrderService,
    order_repo: PendingOrderRepository,
    dca_repo: DCARuleRepository,
    db_session,
    test_user,
):
    rule = dca_repo.create(
        session=db_session,
        user_id=test_user.id,
        ticker="VOO",
        amount_usd=50.0,
        frequency=DCA_FREQ_WEEKLY,
        next_execution_at=datetime.now(timezone.utc),
    )
    rule.enabled = False  # Paused
    db_session.commit()

    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    order = order_repo.create(
        session=db_session,
        user_id=test_user.id,
        ticker="VOO",
        amount_usd=50.0,
        expires_at=expires_at,
        idempotency_key="test-key-paused-rule",
        dca_rule_id=rule.id,
    )
    db_session.commit()

    result = await order_service.confirm_order(
        session=db_session, order_id=order.id, user=test_user
    )
    assert result.success is False
    assert "pausada o desactivada" in result.error_message
