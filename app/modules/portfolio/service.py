"""Portfolio and investment service."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.exceptions import PositionNotFoundError
from app.infrastructure.wallbit.schemas.balance import StockBalanceItem
from app.modules.history.repository import LocalTransactionRepository
from app.shared.concurrency import map_limited

logger = get_logger(__name__)


@dataclass(slots=True)
class PositionDetail:
    ticker: str
    name: str
    shares: float
    current_price: float | None
    current_value: float | None
    avg_price: float | None = None
    cost_basis: float | None = None
    gain_abs: float | None = None
    roi_pct: float | None = None


@dataclass(slots=True)
class PortfolioSummary:
    positions: list[PositionDetail]
    total_current_value: float | None
    total_invested: float | None
    total_gain_abs: float | None
    total_roi_pct: float | None
    cash_usd: float


class PortfolioService:
    def __init__(self, client: WallbitClient, tx_repo: LocalTransactionRepository | None = None):
        self.client = client
        self.tx_repo = tx_repo or LocalTransactionRepository()

    def _get_local_cost_basis(
        self, session: Session | None, user_id: int | None, ticker: str
    ) -> float | None:
        """Calculates historical cost basis for a ticker from local transactions if available."""
        if not session or not user_id:
            return None
        return self.tx_repo.get_cost_basis_by_ticker(session, user_id, [ticker.upper()]).get(ticker.upper())

    async def get_portfolio(
        self, session: Session | None = None, user_id: int | None = None,
        *, stock_items: list[StockBalanceItem] | None = None,
    ) -> PortfolioSummary:
        """Consulta posiciones con cotizaciones acotadas y una agregación SQL.

        Args:
            session: Sesión opcional para consultar el costo local.
            user_id: Propietario de los movimientos locales.
            stock_items: Stocks leídos en el mismo reporte, para no repetir la consulta.

        Returns:
            Resumen; las valoraciones desconocidas son None, nunca cero inventado.

        Raises:
            WallbitApiException: Si falla la consulta de las posiciones.
            sqlalchemy.exc.SQLAlchemyError: Si falla la agregación de costos.
        """
        items = stock_items if stock_items is not None else await self.client.get_stocks_balance()
        symbols = list(dict.fromkeys(item.symbol.upper() for item in items if item.symbol.upper() != "USD" and item.shares > 0))
        costs = self.tx_repo.get_cost_basis_by_ticker(session, user_id, symbols) if session and user_id else {}
        assets = dict(zip(symbols, await map_limited(symbols, self.client.get_asset, settings.WALLBIT_MAX_CONCURRENT_REQUESTS), strict=True))
        positions: list[PositionDetail] = []
        cash_usd = 0.0

        for item in items:
            if item.symbol.upper() == "USD":
                cash_usd += item.shares
                continue

            if item.shares <= 0:
                continue

            asset = assets[item.symbol.upper()]
            if isinstance(asset, Exception):
                logger.warning("No se pudo cotizar %s: %s", item.symbol, asset)
                current_price = None
                name = item.symbol
            else:
                current_price = asset.price
                name = asset.name

            current_value = item.shares * current_price if current_price is not None else None
            cost_basis = costs.get(item.symbol.upper())
            avg_price: float | None = None
            gain_abs: float | None = None
            roi_pct: float | None = None

            if cost_basis is not None and cost_basis > 0 and item.shares > 0:
                avg_price = cost_basis / item.shares
                if current_value is not None:
                    gain_abs = current_value - cost_basis
                    roi_pct = (gain_abs / cost_basis) * 100.0

            positions.append(
                PositionDetail(
                    ticker=item.symbol.upper(),
                    name=name,
                    shares=item.shares,
                    current_price=current_price,
                    current_value=current_value,
                    avg_price=avg_price,
                    cost_basis=cost_basis,
                    gain_abs=gain_abs,
                    roi_pct=roi_pct,
                )
            )

        total_current_value = (
            sum(p.current_value for p in positions if p.current_value is not None)
            if all(p.current_value is not None for p in positions) else None
        )

        # Check if all positions have known cost basis
        has_all_cost_basis = len(positions) > 0 and all(p.cost_basis is not None for p in positions)
        if has_all_cost_basis:
            total_invested = sum(p.cost_basis for p in positions if p.cost_basis is not None)
            total_gain_abs = total_current_value - total_invested if total_current_value is not None else None
            total_roi_pct = (total_gain_abs / total_invested * 100.0) if total_gain_abs is not None and total_invested > 0 else None
        else:
            total_invested = None
            total_gain_abs = None
            total_roi_pct = None

        return PortfolioSummary(
            positions=positions,
            total_current_value=total_current_value,
            total_invested=total_invested,
            total_gain_abs=total_gain_abs,
            total_roi_pct=total_roi_pct,
            cash_usd=cash_usd,
        )

    async def get_position(
        self, ticker: str, session: Session | None = None, user_id: int | None = None
    ) -> PositionDetail:
        """Fetch details for a specific position."""
        ticker = ticker.upper().strip()
        items = await self.client.get_stocks_balance()
        target_item = next((item for item in items if item.symbol.upper() == ticker), None)

        if not target_item or target_item.shares <= 0:
            raise PositionNotFoundError(ticker)

        asset = await self.client.get_asset(ticker)
        current_value = target_item.shares * asset.price

        cost_basis = self._get_local_cost_basis(session, user_id, ticker)
        avg_price: float | None = None
        gain_abs: float | None = None
        roi_pct: float | None = None

        if cost_basis is not None and cost_basis > 0 and target_item.shares > 0:
            avg_price = cost_basis / target_item.shares
            gain_abs = current_value - cost_basis
            roi_pct = (gain_abs / cost_basis) * 100.0

        return PositionDetail(
            ticker=ticker,
            name=asset.name,
            shares=target_item.shares,
            current_price=asset.price,
            current_value=current_value,
            avg_price=avg_price,
            cost_basis=cost_basis,
            gain_abs=gain_abs,
            roi_pct=roi_pct,
        )
