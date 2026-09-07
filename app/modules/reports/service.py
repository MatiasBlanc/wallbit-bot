"""Daily and on-demand financial report service."""

import asyncio
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.infrastructure.wallbit.exceptions import WallbitUnavailableError
from app.modules.balance.service import BalanceService
from app.modules.portfolio.service import PortfolioService
from app.modules.settings.models import UserSettings
from app.shared.exchange.service import ExchangeRateService
from app.shared.formatting.currency import format_usd
from app.shared.formatting.percentage import format_percentage

logger = get_logger(__name__)


@dataclass(slots=True)
class FinancialReport:
    available_balance_usd: float
    total_investments_usd: float | None
    total_gain_usd: float | None
    total_roi_pct: float | None
    fx_pair: str
    fx_rate: float | None
    best_position_ticker: str | None
    best_position_roi: float | None
    worst_position_ticker: str | None
    worst_position_roi: float | None

    def to_telegram_message(self) -> str:
        lines = ["<b>Resumen</b>\n"]
        lines.append(f"Disponible\n{format_usd(self.available_balance_usd)}\n")
        investments = format_usd(self.total_investments_usd) if self.total_investments_usd is not None else "Sin dato"
        lines.append(f"Inversiones\n{investments}\n")

        if self.total_gain_usd is not None and self.total_roi_pct is not None:
            sign = "+" if self.total_gain_usd > 0 else ""
            lines.append(
                f"Rentabilidad\n{sign}${self.total_gain_usd:,.2f} ({format_percentage(self.total_roi_pct)})\n"
            )

        if self.fx_rate is not None:
            lines.append(f"{self.fx_pair}\n${self.fx_rate:,.2f}\n")

        if self.best_position_ticker and self.best_position_roi is not None:
            lines.append(
                f"Mejor posición\n{self.best_position_ticker} {format_percentage(self.best_position_roi)}\n"
            )

        if self.worst_position_ticker and self.worst_position_roi is not None:
            lines.append(
                f"Peor posición\n{self.worst_position_ticker} {format_percentage(self.worst_position_roi)}"
            )

        return "\n".join(lines).strip()


class ReportService:
    def __init__(
        self,
        balance_service: BalanceService,
        portfolio_service: PortfolioService,
        exchange_service: ExchangeRateService,
    ):
        self.balance_service = balance_service
        self.portfolio_service = portfolio_service
        self.exchange_service = exchange_service

    async def generate_report(self, session: Session, user: UserSettings) -> FinancialReport:
        # Se comparte una lectura por reporte, nunca una caché global de fondos.
        accounts = await self.balance_service.get_account_balances()
        if accounts.stocks is None:
            raise WallbitUnavailableError("No se pudo consultar el portafolio para generar el reporte.")
        currency, user_id = user.default_currency, user.id
        balance_info, portfolio_info = await asyncio.gather(
            self.balance_service.get_balance(currency, include_portfolio=False, account_balances=accounts),
            self.portfolio_service.get_portfolio(session=session, user_id=user_id, stock_items=accounts.stocks),
        )

        fx_pair = f"USD/{currency}"
        fx_rate = balance_info.exchange_rate

        # 4. Best & worst positions (only among those with known ROI)
        best_ticker: str | None = None
        best_roi: float | None = None
        worst_ticker: str | None = None
        worst_roi: float | None = None

        positions_with_roi = [p for p in portfolio_info.positions if p.roi_pct is not None]
        if positions_with_roi:
            best = max(positions_with_roi, key=lambda p: p.roi_pct)
            best_ticker = best.ticker
            best_roi = best.roi_pct

            if len(positions_with_roi) > 1:
                worst = min(positions_with_roi, key=lambda p: p.roi_pct)
                worst_ticker = worst.ticker
                worst_roi = worst.roi_pct

        return FinancialReport(
            available_balance_usd=balance_info.available_usd,
            total_investments_usd=portfolio_info.total_current_value,
            total_gain_usd=portfolio_info.total_gain_abs,
            total_roi_pct=portfolio_info.total_roi_pct,
            fx_pair=fx_pair,
            fx_rate=fx_rate,
            best_position_ticker=best_ticker,
            best_position_roi=best_roi,
            worst_position_ticker=worst_ticker,
            worst_position_roi=worst_roi,
        )
