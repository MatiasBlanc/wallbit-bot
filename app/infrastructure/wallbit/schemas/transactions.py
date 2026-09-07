"""Pydantic schemas for Wallbit transaction API responses."""

from pydantic import BaseModel


class TransactionCurrency(BaseModel):
    code: str
    alias: str | None = None


class TransactionItem(BaseModel):
    uuid: str
    type_id: int | None = None
    source_currency: TransactionCurrency | None = None
    dest_currency: TransactionCurrency | None = None
    source_amount: float | None = None
    dest_amount: float | None = None
    status: str
    created_at: str
    comment: str | None = None


class TransactionsData(BaseModel):
    data: list[TransactionItem]
    pages: int | None = 1
    current_page: int | None = 1
    count: int | None = 0


class TransactionsResponse(BaseModel):
    data: TransactionsData
