"""Pydantic schemas for Wallbit API requests and responses."""

from pydantic import BaseModel

# --- Balances ---

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


# --- Assets ---

class AssetDetails(BaseModel):
    symbol: str
    name: str
    price: float
    asset_type: str | None = None
    exchange: str | None = None
    sector: str | None = None
    currency: str | None = "USD"
    description: str | None = None
    logo_url: str | None = None


class AssetResponse(BaseModel):
    data: AssetDetails


class AssetsListResponse(BaseModel):
    data: list[AssetDetails]
    pages: int | None = 1
    current_page: int | None = 1
    count: int | None = 0


# --- Exchange Rates ---

class ExchangeRateData(BaseModel):
    source_currency: str
    dest_currency: str
    pair: str
    rate: float
    updated_at: str | None = None


class ExchangeRateResponse(BaseModel):
    data: ExchangeRateData


# --- Trades ---

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


# --- Transactions ---

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
