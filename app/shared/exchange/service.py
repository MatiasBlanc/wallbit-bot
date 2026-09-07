"""Exchange rate service with caching and provider fallback support."""

import math
import time
from collections import OrderedDict

from app.core.config import settings
from app.core.identity import current_identity
from app.core.logging import get_logger
from app.infrastructure.wallbit.exceptions import ExchangeRateUnavailableError, WallbitAuthenticationError
from app.shared.exchange.providers import ExchangeRateProvider

logger = get_logger(__name__)


class ExchangeRateService:
    """Service to query exchange rates with caching and provider fallback support."""

    def __init__(
        self,
        primary_provider: ExchangeRateProvider | None = None,
        cache_ttl_seconds: int = 300,
        max_cache_entries: int = 128,
    ):
        self.primary_provider = primary_provider
        self.cache_ttl_seconds = cache_ttl_seconds
        if cache_ttl_seconds < 0 or max_cache_entries < 1:
            raise ValueError("La duración de la caché debe ser no negativa y su capacidad positiva.")
        self.max_cache_entries = max_cache_entries
        self._cache: OrderedDict[tuple[int, str, str], tuple[float, float]] = OrderedDict()

    def set_provider(self, provider: ExchangeRateProvider) -> None:
        self.primary_provider = provider
        self._cache.clear()

    async def get_rate(self, source_currency: str, dest_currency: str) -> float:
        s = source_currency.upper()
        d = dest_currency.upper()
        if s == d:
            return 1.0

        identity = current_identity.get()
        if settings.MULTI_USER_ENABLED and identity is None:
            raise WallbitAuthenticationError("Inicia sesión para consultar cotizaciones.")
        account_id = identity.telegram_user_id if settings.MULTI_USER_ENABLED else 0
        cache_key = (account_id, s, d)
        now = time.monotonic()
        for key, (_, cached_at) in list(self._cache.items()):
            if now - cached_at >= self.cache_ttl_seconds:
                del self._cache[key]
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key][0]

        if not self.primary_provider:
            raise ExchangeRateUnavailableError(f"{s}/{d}")

        try:
            rate = await self.primary_provider.get_rate(s, d)
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError("La cotización debe ser positiva y finita.")
            if self.cache_ttl_seconds:
                cached_at = time.monotonic()
                self._cache[cache_key] = (rate, cached_at)
                self._cache[(account_id, d, s)] = (1.0 / rate, cached_at)
                while len(self._cache) > self.max_cache_entries:
                    self._cache.popitem(last=False)
            return rate
        except Exception as e:
            logger.warning("No se pudo consultar el tipo de cambio %s/%s: %s", s, d, e)
            # Una alerta no debe dispararse usando un dato vencido como si fuera actual.
            raise ExchangeRateUnavailableError(f"{s}/{d}") from e

    async def convert(self, amount: float, source_currency: str, dest_currency: str) -> float:
        """Convert an amount from source to destination currency."""
        rate = await self.get_rate(source_currency, dest_currency)
        return amount * rate
