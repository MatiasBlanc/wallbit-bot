"""Pydantic schemas for Wallbit trade and exchange rate API."""

from pydantic import BaseModel


class ExchangeRateData(BaseModel):
    source_currency: str
    dest_currency: str
    pair: str
    rate: float
    updated_at: str | None = None


class ExchangeRateResponse(BaseModel):
    data: ExchangeRateData


class TradeRequest(BaseModel):
    symbol: str
    direction: str = "BUY"
    currency: str = "USD"
    order_type: str = "MARKET"
    amount: float | None = None
    shares: float | None = None


class TradeResult(BaseModel):
    id: str | None = None
    symbol: str
    direction: str
    amount: float | None = None
    shares: float | None = None
    status: str
    order_type: str | None = "MARKET"
    created_at: str | None = None
    updated_at: str | None = None


class TradeResponse(BaseModel):
    data: TradeResult
