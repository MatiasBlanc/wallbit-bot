"""Tests for PortfolioService."""

import pytest

from app.core.constants import TX_TYPE_BUY
from app.infrastructure.wallbit.exceptions import PositionNotFoundError
from app.modules.history.models import LocalTransaction
from app.modules.portfolio.service import PortfolioService


@pytest.mark.asyncio
async def test_get_portfolio_overview(portfolio_service: PortfolioService, db_session, test_user):
    # Record a local purchase for VOO: $450 USD
    tx = LocalTransaction(
        user_id=test_user.id,
        transaction_type=TX_TYPE_BUY,
        amount_usd=450.0,
        ticker="VOO",
        source="TEST",
    )
    db_session.add(tx)
    db_session.commit()

    summary = await portfolio_service.get_portfolio(session=db_session, user_id=test_user.id)

    # 2 positions: VOO and AAPL
    assert len(summary.positions) == 2
    voo = next(p for p in summary.positions if p.ticker == "VOO")
    aapl = next(p for p in summary.positions if p.ticker == "AAPL")

    assert voo.shares == 1.0
    assert voo.current_price == 495.20
    assert voo.current_value == 495.20
    assert voo.cost_basis == 450.0
    assert abs(voo.gain_abs - 45.20) < 1e-4
    assert abs(voo.roi_pct - ((45.20 / 450.0) * 100)) < 1e-4

    # AAPL has no recorded local purchase -> cost_basis, gain_abs, roi_pct must be None (no invented metrics)
    assert aapl.shares == 2.0
    assert aapl.current_price == 180.0
    assert aapl.current_value == 360.0
    assert aapl.cost_basis is None
    assert aapl.gain_abs is None
    assert aapl.roi_pct is None

    # Total current value: 495.20 + 360.0 = 855.20
    assert abs(summary.total_current_value - 855.20) < 1e-4
    assert summary.cash_usd == 85.20


@pytest.mark.asyncio
async def test_get_position_success(portfolio_service: PortfolioService):
    pos = await portfolio_service.get_position("VOO")
    assert pos.ticker == "VOO"
    assert pos.name == "Vanguard S&P 500 ETF"
    assert pos.shares == 1.0
    assert pos.current_price == 495.20
    assert pos.current_value == 495.20


@pytest.mark.asyncio
async def test_get_position_not_found(portfolio_service: PortfolioService):
    # MSFT is not in user's stocks
    with pytest.raises(PositionNotFoundError):
        await portfolio_service.get_position("MSFT")
