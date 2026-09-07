"""Pydantic schemas for Wallbit balance API responses."""

from pydantic import BaseModel


class CheckingBalanceItem(BaseModel):
    currency: str
    balance: float


class CheckingBalanceResponse(BaseModel):
    data: list[CheckingBalanceItem]


class StockBalanceItem(BaseModel):
    symbol: str
    shares: float


class StocksBalanceResponse(BaseModel):
    data: list[StockBalanceItem]
