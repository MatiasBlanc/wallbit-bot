"""Daily and on-demand financial report service."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import UserSettings
from app.services.balance_service import BalanceService
from app.services.exchange_service import ExchangeRateService
from app.services.portfolio_service import PortfolioService
from app.utils.formatting import format_percentage, format_usd

logger = get_logger(__name__)


@dataclass
class FinancialReport:
    available_balance_usd: float
    total_investments_usd: float
    total_gain_usd: float | None
    total_roi_pct: float | None
    fx_pair: str
    fx_rate: float | None
    best_position_ticker: str | None
    best_position_roi: float | None
    worst_position_ticker: str | None
    worst_position_roi: float | None

    def to_telegram_message(self) -> str:
        lines = ["☀️ <b>Resumen financiero</b>\n"]
        lines.append(f"Saldo disponible\n{format_usd(self.available_balance_usd)}\n")
        lines.append(f"Inversiones\n{format_usd(self.total_investments_usd)}\n")

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
        # 1. Fetch balance
        balance_info = await self.balance_service.get_balance(target_currency=user.default_currency)

        # 2. Fetch portfolio
        portfolio_info = await self.portfolio_service.get_portfolio(session=session, user_id=user.id)

        # 3. Exchange rate
        fx_pair = f"USD/{user.default_currency}"
        fx_rate = balance_info.exchange_rate
        if user.default_currency != "USD" and fx_rate is None:
            try:
                fx_rate = await self.exchange_service.get_rate("USD", user.default_currency)
            except Exception:
                fx_rate = None

        # 4. Best & worst positions (only among those with known ROI)
        best_ticker: str | None = None
        best_roi: float | None = None
        worst_ticker: str | None = None
        worst_roi: float | None = None

        positions_with_roi = [p for p in portfolio_info.positions if p.roi_pct is not None]
        if positions_with_roi:
            positions_sorted = sorted(positions_with_roi, key=lambda p: p.roi_pct or 0.0, reverse=True)
            best = positions_sorted[0]
            best_ticker = best.ticker
            best_roi = best.roi_pct

            if len(positions_sorted) > 1:
                worst = positions_sorted[-1]
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
