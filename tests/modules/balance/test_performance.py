"""Lectura mínima de fondos y ausencia de caché al validar operaciones."""

import asyncio

from app.infrastructure.wallbit.schemas.balance import CheckingBalanceItem, StockBalanceItem


async def test_cash_only_does_not_fetch_asset_prices(balance_service, mock_wallbit_client):
    info = await balance_service.get_balance("USD", include_portfolio=False)
    assert round(info.available_usd, 2) == 305.70
    assert info.total_wealth_usd is None
    assert info.portfolio_stocks_usd is None
    mock_wallbit_client.get_asset.assert_not_awaited()
    mock_wallbit_client.get_exchange_rate.assert_not_awaited()
    mock_wallbit_client.get_checking_balance.assert_awaited_once()
    mock_wallbit_client.get_stocks_balance.assert_awaited_once()


async def test_balances_are_independent_and_concurrent(balance_service, mock_wallbit_client):
    checking_started, stocks_started = asyncio.Event(), asyncio.Event()

    async def checking():
        checking_started.set()
        await asyncio.wait_for(stocks_started.wait(), timeout=1)
        return [CheckingBalanceItem(currency="USD", balance=5)]

    async def stocks():
        stocks_started.set()
        await asyncio.wait_for(checking_started.wait(), timeout=1)
        return [StockBalanceItem(symbol="USD", shares=10)]

    mock_wallbit_client.get_checking_balance.side_effect = checking
    mock_wallbit_client.get_stocks_balance.side_effect = stocks
    info = await balance_service.get_balance("USD", include_portfolio=False)
    assert info.available_usd == 15


async def test_cash_is_fetched_again_for_each_call(balance_service, mock_wallbit_client):
    await balance_service.get_balance("USD", include_portfolio=False)
    mock_wallbit_client.get_checking_balance.return_value = [CheckingBalanceItem(currency="USD", balance=1)]
    mock_wallbit_client.get_stocks_balance.return_value = [StockBalanceItem(symbol="USD", shares=2)]
    info = await balance_service.get_balance("USD", include_portfolio=False)
    assert info.available_usd == 3
    assert mock_wallbit_client.get_checking_balance.await_count == 2
    assert mock_wallbit_client.get_stocks_balance.await_count == 2


async def test_price_failure_never_produces_partial_wealth(balance_service, mock_wallbit_client):
    mock_wallbit_client.get_asset.side_effect = RuntimeError("cotizaciones no disponibles")
    info = await balance_service.get_balance("USD")
    assert info.total_wealth_usd is None
    assert info.portfolio_stocks_usd is None
    assert round(info.available_usd, 2) == 305.70
