"""Tests for WallbitClient HTTP handling and exception mapping."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.exceptions import (
    InsufficientFundsError,
    InvalidTickerError,
    WallbitAuthenticationError,
    WallbitRateLimitError,
    WallbitUnexpectedResponseError,
)
from app.infrastructure.wallbit.schemas.orders import TradeRequest


@pytest.mark.asyncio
async def test_wallbit_client_get_checking_balance():
    client = WallbitClient(base_url="https://api.wallbit.io", api_key="dummy_key")
    mock_resp = httpx.Response(
        status_code=200,
        json={"data": [{"currency": "USD", "balance": 150.75}]},
        request=httpx.Request("GET", "https://api.wallbit.io/api/public/v1/balance/checking"),
    )
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        items = await client.get_checking_balance()
        assert len(items) == 1
        assert items[0].currency == "USD"
        assert items[0].balance == 150.75
    await client.close()


@pytest.mark.asyncio
async def test_wallbit_client_get_asset_not_found():
    client = WallbitClient(base_url="https://api.wallbit.io", api_key="dummy_key")
    mock_resp = httpx.Response(
        status_code=404,
        json={"message": "Asset not found"},
        request=httpx.Request("GET", "https://api.wallbit.io/api/public/v1/assets/NONEXISTENT"),
    )
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(InvalidTickerError):
            await client.get_asset("NONEXISTENT")
    await client.close()


@pytest.mark.asyncio
async def test_wallbit_client_401_auth_error():
    client = WallbitClient(base_url="https://api.wallbit.io", api_key="bad_key")
    mock_resp = httpx.Response(
        status_code=401,
        json={"message": "Invalid or expired API Key."},
        request=httpx.Request("GET", "https://api.wallbit.io/api/public/v1/balance/checking"),
    )
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(WallbitAuthenticationError):
            await client.get_checking_balance()
    await client.close()


@pytest.mark.asyncio
async def test_wallbit_client_429_rate_limit():
    client = WallbitClient(base_url="https://api.wallbit.io", api_key="dummy_key")
    mock_resp = httpx.Response(
        status_code=429,
        headers={"Retry-After": "10"},
        json={"message": "Too many requests. Please try again later."},
        request=httpx.Request("POST", "https://api.wallbit.io/api/public/v1/trades"),
    )
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(WallbitRateLimitError) as exc_info:
            await client.create_trade(TradeRequest(symbol="VOO", amount=50.0))
        assert exc_info.value.retry_after == 10
    await client.close()


@pytest.mark.asyncio
async def test_wallbit_client_rejects_malformed_json():
    client = WallbitClient(base_url="https://api.wallbit.io", api_key="dummy_key")
    mock_resp = httpx.Response(
        status_code=200,
        content=b"not-json",
        request=httpx.Request("GET", "https://api.wallbit.io/api/public/v1/balance/checking"),
    )
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(WallbitUnexpectedResponseError):
            await client.get_checking_balance()
    await client.close()


@pytest.mark.asyncio
async def test_wallbit_client_400_insufficient_funds():
    client = WallbitClient(base_url="https://api.wallbit.io", api_key="dummy_key")
    mock_resp = httpx.Response(
        status_code=400,
        json={"message": "Insufficient funds to execute trade"},
        request=httpx.Request("POST", "https://api.wallbit.io/api/public/v1/trades"),
    )
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(InsufficientFundsError):
            await client.create_trade(TradeRequest(symbol="VOO", amount=50.0))
    await client.close()
