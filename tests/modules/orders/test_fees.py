"""Estimación de comisión publicada por Wallbit, sin enviar compras."""

from decimal import Decimal
from unittest.mock import AsyncMock

from app.core.config import settings
from app.modules.balance.service import BalanceInfo
from app.modules.orders.fees import estimate_trade_fee, format_fee_summary


def test_classic_fifty_dollars_matches_published_rate(db_session, test_user):
    estimate = estimate_trade_fee(db_session, test_user, 50)
    assert estimate.plan == "classic"
    assert estimate.fee_usd == Decimal("0.20")
    assert estimate.total_usd == Decimal("50.20")
    summary = format_fee_summary(estimate)
    assert "Monto: <b>$50.00 USD</b>" in summary
    assert "Comisión estimada: <b>$0.20 USD</b>" in summary
    assert "Total aproximado: <b>$50.20 USD</b>" in summary


def test_pro_rounds_half_up_and_max_caps_at_ten(db_session, test_user, monkeypatch):
    monkeypatch.setattr(settings, "WALLBIT_PLAN", "pro")
    assert estimate_trade_fee(db_session, test_user, 50).fee_usd == Decimal("0.18")
    monkeypatch.setattr(settings, "WALLBIT_PLAN", "max")
    assert estimate_trade_fee(db_session, test_user, 50).fee_usd == Decimal("0.15")
    assert estimate_trade_fee(db_session, test_user, 4000).fee_usd == Decimal("10.00")
    assert estimate_trade_fee(db_session, test_user, 4000).total_usd == Decimal("4010.00")


async def test_dca_requires_funds_for_amount_plus_estimated_fee(dca_service, db_session, test_user, monkeypatch):
    dca_service.balance_service.get_balance = AsyncMock(return_value=BalanceInfo(
        checking_usd=50.10, investment_cash_usd=0.0, available_usd=50.10, portfolio_stocks_usd=None,
        total_wealth_usd=None, target_currency="USD", converted_available=None, converted_total_wealth=None,
        exchange_rate=None,
    ))
    rule = dca_service.create_rule(db_session, test_user, "VOO", 50.0, "weekly", weekday=0)
    db_session.commit()
    has_funds, order, available, _price = await dca_service.trigger_dca_rule(db_session, rule, test_user)
    assert has_funds is False
    assert order is None
    assert available == 50.10


async def test_confirm_requires_funds_for_amount_plus_estimated_fee(
    order_service, db_session, test_user, monkeypatch,
):
    monkeypatch.setattr(settings, "TRADING_ENABLED", False)
    order_service.balance_service.get_balance = AsyncMock(return_value=BalanceInfo(
        checking_usd=50.10, investment_cash_usd=0.0, available_usd=50.10, portfolio_stocks_usd=None,
        total_wealth_usd=None, target_currency="USD", converted_available=None, converted_total_wealth=None,
        exchange_rate=None,
    ))
    order = order_service.create_pending_order(db_session, test_user, "VOO", 50.0)
    db_session.commit()
    result = await order_service.confirm_order(db_session, order.id, test_user)
    assert result.success is False
    assert result.estimated_fee_usd == 0.20
    assert result.estimated_total_usd == 50.20
    assert "50.20" in result.error_message
