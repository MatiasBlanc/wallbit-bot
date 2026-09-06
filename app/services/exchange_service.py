"""Exchange rate service with abstraction for multiple providers."""

import time
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.wallbit.client import WallbitClient
from app.wallbit.exceptions import ExchangeRateUnavailableError

logger = get_logger(__name__)


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


class ExchangeRateService:
    """Service to query exchange rates with caching and provider fallback support."""

    def __init__(
        self,
        primary_provider: ExchangeRateProvider | None = None,
        cache_ttl_seconds: int = 300,
    ):
        self.primary_provider = primary_provider
        self.cache_ttl_seconds = cache_ttl_seconds
        # Cache key: (source, dest) -> (rate, timestamp)
        self._cache: dict[tuple[str, str], tuple[float, float]] = {}

    def set_provider(self, provider: ExchangeRateProvider) -> None:
        self.primary_provider = provider

    async def get_rate(self, source_currency: str, dest_currency: str) -> float:
        s = source_currency.upper()
        d = dest_currency.upper()
        if s == d:
            return 1.0

        cache_key = (s, d)
        now = time.time()
        if cache_key in self._cache:
            rate, cached_at = self._cache[cache_key]
            if now - cached_at < self.cache_ttl_seconds:
                return rate

        if not self.primary_provider:
            raise ExchangeRateUnavailableError(f"{s}/{d}")

        try:
            rate = await self.primary_provider.get_rate(s, d)
            self._cache[cache_key] = (rate, now)
            # Also store inverse if applicable and non-zero
            if rate > 0:
                self._cache[(d, s)] = (1.0 / rate, now)
            return rate
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rate for {s}/{d}: {e}")
            # If we have stale cache, we could return it as fallback or raise
            if cache_key in self._cache:
                return self._cache[cache_key][0]
            raise ExchangeRateUnavailableError(f"{s}/{d}")

    async def convert(self, amount: float, source_currency: str, dest_currency: str) -> float:
        """Convert an amount from source to destination currency."""
        rate = await self.get_rate(source_currency, dest_currency)
        return amount * rate
