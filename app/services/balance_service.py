"""Balance service to retrieve and compute user funds and total wealth."""

from dataclasses import dataclass

from app.core.constants import SUPPORTED_CURRENCIES
from app.core.logging import get_logger
from app.services.exchange_service import ExchangeRateService
from app.wallbit.client import WallbitClient

logger = get_logger(__name__)


@dataclass
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

    async def get_balance(self, target_currency: str = "CLP") -> BalanceInfo:
        target_currency = target_currency.upper().strip()
        if target_currency not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Moneda no soportada '{target_currency}'. Monedas disponibles: {', '.join(SUPPORTED_CURRENCIES)}"
            )

        # 1. Fetch checking balances
        checking_usd: float | None = None
        try:
            checking_items = await self.client.get_checking_balance()
            # Find USD checking balance
            usd_checking = [item.balance for item in checking_items if item.currency.upper() == "USD"]
            if usd_checking:
                checking_usd = sum(usd_checking)
            else:
                checking_usd = 0.0
        except Exception as e:
            logger.warning(f"Error fetching checking balance: {e}")
            checking_usd = None

        # 2. Fetch stocks balances
        investment_cash_usd: float | None = None
        portfolio_stocks_usd: float | None = 0.0
        stocks_fetch_success = True

        try:
            stock_items = await self.client.get_stocks_balance()
            for item in stock_items:
                if item.symbol.upper() == "USD":
                    investment_cash_usd = (investment_cash_usd or 0.0) + item.shares
                elif item.shares > 0:
                    try:
                        asset = await self.client.get_asset(item.symbol)
                        portfolio_stocks_usd += item.shares * asset.price
                    except Exception as asset_err:
                        logger.warning(f"Failed to fetch price for {item.symbol}: {asset_err}")
                        stocks_fetch_success = False

            if investment_cash_usd is None:
                investment_cash_usd = 0.0

        except Exception as e:
            logger.warning(f"Error fetching stocks balance: {e}")
            investment_cash_usd = None
            stocks_fetch_success = False

        # 3. Compute available USD
        avail_components = [c for c in [checking_usd, investment_cash_usd] if c is not None]
        available_usd = sum(avail_components) if avail_components else 0.0

        # 4. Compute total wealth
        total_wealth_usd: float | None = None
        if stocks_fetch_success and checking_usd is not None and investment_cash_usd is not None:
            total_wealth_usd = available_usd + (portfolio_stocks_usd or 0.0)

        # 5. Currency conversion
        converted_available: float | None = None
        converted_total_wealth: float | None = None
        rate: float | None = None

        if target_currency != "USD":
            try:
                rate = await self.exchange_service.get_rate("USD", target_currency)
                if rate:
                    converted_available = available_usd * rate
                    if total_wealth_usd is not None:
                        converted_total_wealth = total_wealth_usd * rate
            except Exception as e:
                logger.warning(f"Error converting to {target_currency}: {e}")

        return BalanceInfo(
            checking_usd=checking_usd,
            investment_cash_usd=investment_cash_usd,
            available_usd=available_usd,
            portfolio_stocks_usd=portfolio_stocks_usd if stocks_fetch_success else None,
            total_wealth_usd=total_wealth_usd,
            target_currency=target_currency,
            converted_available=converted_available,
            converted_total_wealth=converted_total_wealth,
            exchange_rate=rate,
        )
