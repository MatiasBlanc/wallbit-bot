"""Tests for BalanceService."""

import pytest

from app.services.balance_service import BalanceService


@pytest.mark.asyncio
async def test_get_balance_standard(balance_service: BalanceService):
    info = await balance_service.get_balance(target_currency="CLP")

    # Checking: 220.50 USD
    assert info.checking_usd == 220.50
    # Investment cash: 85.20 USD
    assert info.investment_cash_usd == 85.20
    # Available: 220.50 + 85.20 = 305.70 USD
    assert abs(info.available_usd - 305.70) < 1e-4

    # Stocks: 1 VOO @ 495.20 + 2 AAPL @ 180.00 = 495.20 + 360.00 = 855.20 USD
    assert info.portfolio_stocks_usd is not None
    assert abs(info.portfolio_stocks_usd - 855.20) < 1e-4

    # Total wealth: 305.70 + 855.20 = 1160.90 USD
    assert info.total_wealth_usd is not None
    assert abs(info.total_wealth_usd - 1160.90) < 1e-4

    # Converted to CLP @ 950
    assert info.converted_available is not None
    assert abs(info.converted_available - (305.70 * 950.0)) < 1e-2
    assert info.exchange_rate == 950.0


@pytest.mark.asyncio
async def test_get_balance_unsupported_currency(balance_service: BalanceService):
    with pytest.raises(ValueError, match="Moneda no soportada"):
        await balance_service.get_balance(target_currency="XYZ")


@pytest.mark.asyncio
async def test_get_balance_when_checking_fails(balance_service: BalanceService, mock_wallbit_client):
    mock_wallbit_client.get_checking_balance.side_effect = Exception("API connection dropped")
    info = await balance_service.get_balance(target_currency="USD")

    assert info.checking_usd is None
    assert info.investment_cash_usd == 85.20
    assert info.available_usd == 85.20
    # If checking failed, total wealth should be None (never invent data)
    assert info.total_wealth_usd is None
