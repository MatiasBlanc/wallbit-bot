"""Tests for DCAService."""

import pytest

from app.core.constants import DCA_FREQ_MONTHLY, DCA_FREQ_WEEKLY, ORDER_STATUS_PENDING
from app.services.dca_service import DCAService


@pytest.mark.asyncio
async def test_create_dca_rule_weekly(dca_service: DCAService, db_session, test_user):
    rule = dca_service.create_rule(
        session=db_session,
        user=test_user,
        ticker="VOO",
        amount_usd=50.0,
        frequency=DCA_FREQ_WEEKLY,
        weekday=0,  # Monday
    )
    db_session.commit()

    assert rule.id is not None
    assert rule.ticker == "VOO"
    assert rule.amount_usd == 50.0
    assert rule.frequency == DCA_FREQ_WEEKLY
    assert rule.weekday == 0
    assert rule.enabled is True
    assert rule.next_execution_at is not None


@pytest.mark.asyncio
async def test_create_dca_rule_monthly(dca_service: DCAService, db_session, test_user):
    rule = dca_service.create_rule(
        session=db_session,
        user=test_user,
        ticker="SPY",
        amount_usd=100.0,
        frequency=DCA_FREQ_MONTHLY,
        day_of_month=1,
    )
    db_session.commit()

    assert rule.id is not None
    assert rule.ticker == "SPY"
    assert rule.amount_usd == 100.0
    assert rule.frequency == DCA_FREQ_MONTHLY
    assert rule.day_of_month == 1


@pytest.mark.asyncio
async def test_trigger_dca_sufficient_funds(dca_service: DCAService, db_session, test_user):
    rule = dca_service.create_rule(
        session=db_session,
        user=test_user,
        ticker="VOO",
        amount_usd=50.0,
        frequency=DCA_FREQ_WEEKLY,
        weekday=0,
    )
    db_session.commit()

    # User has 305.70 available > 50
    has_funds, pending_order, avail, price = await dca_service.trigger_dca_rule(
        session=db_session, rule=rule, user=test_user
    )
    db_session.commit()

    assert has_funds is True
    assert pending_order is not None
    assert pending_order.ticker == "VOO"
    assert pending_order.amount_usd == 50.0
    assert pending_order.status == ORDER_STATUS_PENDING
    assert pending_order.idempotency_key.startswith("dca-")
    assert abs(avail - 305.70) < 1e-4
    assert price == 495.20


@pytest.mark.asyncio
async def test_trigger_dca_insufficient_funds(dca_service: DCAService, db_session, test_user):
    # Rule for 1000 USD (user only has 305.70)
    rule = dca_service.create_rule(
        session=db_session,
        user=test_user,
        ticker="VOO",
        amount_usd=1000.0,
        frequency=DCA_FREQ_WEEKLY,
        weekday=0,
    )
    db_session.commit()

    has_funds, pending_order, avail, price = await dca_service.trigger_dca_rule(
        session=db_session, rule=rule, user=test_user
    )
    db_session.commit()

    assert has_funds is False
    assert pending_order is None
    assert abs(avail - 305.70) < 1e-4


@pytest.mark.asyncio
async def test_pause_resume_delete_dca(dca_service: DCAService, db_session, test_user):
    rule = dca_service.create_rule(
        session=db_session,
        user=test_user,
        ticker="VOO",
        amount_usd=50.0,
        frequency=DCA_FREQ_WEEKLY,
        weekday=0,
    )
    db_session.commit()

    # Pause
    dca_service.pause_rule(db_session, rule)
    db_session.commit()
    assert rule.enabled is False
    assert len(dca_service.list_active_rules(db_session, test_user.id)) == 0
    assert len(dca_service.list_paused_rules(db_session, test_user.id)) == 1

    # Resume
    dca_service.reactivate_rule(db_session, rule, test_user)
    db_session.commit()
    assert rule.enabled is True
    assert len(dca_service.list_active_rules(db_session, test_user.id)) == 1

    # Delete
    dca_service.delete_rule(db_session, rule)
    db_session.commit()
    assert dca_service.get_rule(db_session, rule.id) is None
