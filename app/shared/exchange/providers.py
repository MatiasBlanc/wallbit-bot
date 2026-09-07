"""Exchange rate provider abstractions."""

from abc import ABC, abstractmethod

from app.infrastructure.wallbit.client import WallbitClient


class ExchangeRateProvider(ABC):
    """Abstract provider for exchange rates."""

    @abstractmethod
    async def get_rate(self, source_currency: str, dest_currency: str) -> float:
        """Fetch the exchange rate from source to destination currency."""


class WallbitExchangeRateProvider(ExchangeRateProvider):
    """Wallbit public API rate provider."""

    def __init__(self, client: WallbitClient):
        self.client = client

    async def get_rate(self, source_currency: str, dest_currency: str) -> float:
        s = source_currency.upper()
        d = dest_currency.upper()
        if s == d:
            return 1.0
        data = await self.client.get_exchange_rate(s, d)
        return data.rate
