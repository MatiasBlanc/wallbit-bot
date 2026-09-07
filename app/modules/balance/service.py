"""Lectura de saldos y valoración sin cachear fondos entre operaciones."""

import asyncio
from dataclasses import dataclass

from app.core.config import settings
from app.core.constants import SUPPORTED_CURRENCIES
from app.core.logging import get_logger
from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.schemas.balance import StockBalanceItem
from app.shared.concurrency import map_limited
from app.shared.exchange.service import ExchangeRateService

logger = get_logger(__name__)


@dataclass(slots=True)
class AccountBalances:
    """Lecturas de una única consulta; None indica que falló ese endpoint."""

    checking_usd: float | None
    stocks: list[StockBalanceItem] | None


@dataclass(slots=True)
class BalanceInfo:
    checking_usd: float | None
    investment_cash_usd: float | None
    available_usd: float
    portfolio_stocks_usd: float | None
    total_wealth_usd: float | None
    target_currency: str
    converted_available: float | None
    converted_total_wealth: float | None
    exchange_rate: float | None


class BalanceService:
    def __init__(self, client: WallbitClient, exchange_service: ExchangeRateService):
        self.client = client
        self.exchange_service = exchange_service

    async def get_account_balances(self) -> AccountBalances:
        """Consulta checking y stocks simultáneamente, sin caché de saldos.

        Returns:
            Lecturas reutilizables dentro del mismo reporte; los fallos se registran.
        """
        checking, stocks = await asyncio.gather(
            self.client.get_checking_balance(), self.client.get_stocks_balance(), return_exceptions=True,
        )
        if isinstance(checking, BaseException):
            if not isinstance(checking, Exception):
                raise checking
            logger.warning("No se pudo consultar checking: %s", checking)
            checking_usd = None
        else:
            checking_usd = sum(item.balance for item in checking if item.currency.upper() == "USD")
        if isinstance(stocks, BaseException):
            if not isinstance(stocks, Exception):
                raise stocks
            logger.warning("No se pudo consultar stocks: %s", stocks)
            stocks = None
        return AccountBalances(checking_usd=checking_usd, stocks=stocks)

    async def get_balance(
        self,
        target_currency: str = "CLP",
        *,
        include_portfolio: bool = True,
        account_balances: AccountBalances | None = None,
    ) -> BalanceInfo:
        """Calcula saldos y, opcionalmente, la valoración de las inversiones.

        Args:
            target_currency: Divisa soportada para mostrar la conversión.
            include_portfolio: False evita cotizar posiciones cuando solo se necesitan fondos.
            account_balances: Lecturas del mismo reporte para evitar repetir los endpoints.
                La confirmación de órdenes no debe suministrar este argumento.

        Returns:
            Saldo consultado y métricas disponibles; nunca una valoración parcial del portafolio.

        Raises:
            ValueError: Si la moneda no está soportada.
        """
        target_currency = target_currency.upper().strip()
        if target_currency not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Moneda no soportada '{target_currency}'. Monedas disponibles: {', '.join(SUPPORTED_CURRENCIES)}"
            )
        accounts = account_balances if account_balances is not None else await self.get_account_balances()
        checking_usd = accounts.checking_usd
        investment_cash_usd = None
        portfolio_stocks_usd = None
        if accounts.stocks is not None:
            investment_cash_usd = sum(item.shares for item in accounts.stocks if item.symbol.upper() == "USD")
            if include_portfolio:
                positions = [item for item in accounts.stocks if item.symbol.upper() != "USD" and item.shares > 0]
                symbols = list(dict.fromkeys(item.symbol.upper() for item in positions))
                results = await map_limited(symbols, self.client.get_asset, settings.WALLBIT_MAX_CONCURRENT_REQUESTS)
                prices = {}
                for symbol, result in zip(symbols, results, strict=True):
                    if isinstance(result, Exception):
                        logger.warning("No se pudo cotizar %s: %s", symbol, result)
                    else:
                        prices[symbol] = result.price
                if len(prices) == len(symbols):
                    portfolio_stocks_usd = sum(item.shares * prices[item.symbol.upper()] for item in positions)

        available_usd = sum(value for value in (checking_usd, investment_cash_usd) if value is not None)
        total_wealth_usd = None
        if checking_usd is not None and investment_cash_usd is not None and portfolio_stocks_usd is not None:
            total_wealth_usd = available_usd + portfolio_stocks_usd

        converted_available = converted_total_wealth = rate = None
        if target_currency != "USD":
            try:
                rate = await self.exchange_service.get_rate("USD", target_currency)
                converted_available = available_usd * rate
                if total_wealth_usd is not None:
                    converted_total_wealth = total_wealth_usd * rate
            except Exception as error:
                logger.warning("No se pudo convertir a %s: %s", target_currency, error)

        return BalanceInfo(
            checking_usd=checking_usd,
            investment_cash_usd=investment_cash_usd,
            available_usd=available_usd,
            portfolio_stocks_usd=portfolio_stocks_usd,
            total_wealth_usd=total_wealth_usd,
            target_currency=target_currency,
            converted_available=converted_available,
            converted_total_wealth=converted_total_wealth,
            exchange_rate=rate,
        )
