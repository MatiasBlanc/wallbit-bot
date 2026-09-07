"""Pydantic schemas for Wallbit asset/portfolio API responses."""

from pydantic import BaseModel


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
