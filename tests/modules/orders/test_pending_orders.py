"""Creación de intenciones sin ejecutar operaciones financieras."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.constants import ORDER_STATUS_PENDING
from app.shared.datetime import ensure_utc


def test_manual_intent_is_pending_and_unique(order_service, db_session, test_user, mock_wallbit_client):
    before = datetime.now(timezone.utc)
    first = order_service.create_pending_order(db_session, test_user, "voo", 50.0)
    second = order_service.create_pending_order(db_session, test_user, "voo", 50.0)
    after = datetime.now(timezone.utc)

    assert first.ticker == "VOO"
    assert first.status == ORDER_STATUS_PENDING
    assert first.user_id == test_user.id
    assert first.dca_rule_id is None
    assert first.idempotency_key.startswith("manual-")
    assert first.idempotency_key != second.idempotency_key
    assert first.external_order_id is None
    assert before + timedelta(hours=settings.ORDER_EXPIRY_HOURS) <= ensure_utc(first.expires_at)
    assert ensure_utc(first.expires_at) <= after + timedelta(hours=settings.ORDER_EXPIRY_HOURS)
    mock_wallbit_client.create_trade.assert_not_called()


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_invalid_intent_amount_is_rejected(order_service, db_session, test_user, amount):
    with pytest.raises(ValueError, match="positivo y finito"):
        order_service.create_pending_order(db_session, test_user, "VOO", amount)


async def test_manual_intent_can_be_confirmed(
    order_service, db_session, test_user, mock_wallbit_client, monkeypatch,
):
    monkeypatch.setattr(settings, "TRADING_ENABLED", False)
    order = order_service.create_pending_order(db_session, test_user, "VOO", 50.0)
    db_session.commit()
    result = await order_service.confirm_order(db_session, order.id, test_user)
    assert result.success
    assert result.is_simulation
    mock_wallbit_client.create_trade.assert_not_called()


def test_reconcile_unverified_order(order_service, db_session, test_user):
    from app.core.constants import ORDER_STATUS_EXECUTED, ORDER_STATUS_UNKNOWN
    order = order_service.create_pending_order(db_session, test_user, "AAPL", 100.0)
    order_service.order_repo.update_status(db_session, order, ORDER_STATUS_UNKNOWN)
    db_session.commit()

    unverified = order_service.list_orders_needing_verification(db_session, test_user.id)
    assert len(unverified) == 1
    assert unverified[0].id == order.id

    # Reconcile as executed on Wallbit
    success = order_service.reconcile_order(
        db_session, test_user.id, order.id, was_executed_on_wallbit=True, external_order_id="WB-EXT-123"
    )
    assert success is True

    db_session.refresh(order)
    assert order.status == ORDER_STATUS_EXECUTED
    assert order.external_order_id == "WB-EXT-123"

    # Verify transaction was created
    txs = order_service.tx_repo.list_by_user(db_session, test_user.id)
    assert any(tx.external_order_id == "WB-EXT-123" for tx in txs)

