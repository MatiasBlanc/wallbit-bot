"""Portfolio and investment service."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.constants import TX_TYPE_BUY, TX_TYPE_DCA_BUY
from app.core.logging import get_logger
from app.db.models import LocalTransaction
from app.wallbit.client import WallbitClient
from app.wallbit.exceptions import PositionNotFoundError

logger = get_logger(__name__)


@dataclass
class PositionDetail:
    ticker: str
    name: str
    shares: float
    current_price: float
    current_value: float
    avg_price: float | None = None
    cost_basis: float | None = None
    gain_abs: float | None = None
    roi_pct: float | None = None


@dataclass
class PortfolioSummary:
    positions: list[PositionDetail]
    total_current_value: float
    total_invested: float | None
    total_gain_abs: float | None
    total_roi_pct: float | None
    cash_usd: float


class PortfolioService:
    def __init__(self, client: WallbitClient):
        self.client = client

    def _get_local_cost_basis(
        self, session: Session | None, user_id: int | None, ticker: str
    ) -> float | None:
        """Calculates historical cost basis for a ticker from local transactions if available."""
        if not session or not user_id:
            return None
        txs = (
            session.query(LocalTransaction)
            .filter(
                LocalTransaction.user_id == user_id,
                LocalTransaction.ticker == ticker.upper(),
                LocalTransaction.transaction_type.in_([TX_TYPE_BUY, TX_TYPE_DCA_BUY]),
            )
            .all()
        )
        if not txs:
            return None
        total_bought = sum(tx.amount_usd for tx in txs)
        return total_bought if total_bought > 0 else None

    async def get_portfolio(
        self, session: Session | None = None, user_id: int | None = None
    ) -> PortfolioSummary:
        """Fetch all investment positions and build portfolio summary."""
        items = await self.client.get_stocks_balance()
        positions: list[PositionDetail] = []
        cash_usd = 0.0

        for item in items:
            if item.symbol.upper() == "USD":
                cash_usd += item.shares
                continue

            if item.shares <= 0:
                continue

            try:
                asset = await self.client.get_asset(item.symbol)
                current_price = asset.price
                name = asset.name
            except Exception as e:
                logger.warning(f"Could not fetch asset details for {item.symbol}: {e}")
                current_price = 0.0
                name = item.symbol

            current_value = item.shares * current_price

            # Cost basis calculation (if recorded locally)
            cost_basis = self._get_local_cost_basis(session, user_id, item.symbol)
            avg_price: float | None = None
            gain_abs: float | None = None
            roi_pct: float | None = None

            if cost_basis is not None and cost_basis > 0 and item.shares > 0:
                avg_price = cost_basis / item.shares
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

        total_current_value = sum(p.current_value for p in positions)

        # Check if all positions have known cost basis
        has_all_cost_basis = len(positions) > 0 and all(p.cost_basis is not None for p in positions)
        if has_all_cost_basis:
            total_invested = sum(p.cost_basis for p in positions if p.cost_basis is not None)
            total_gain_abs = total_current_value - total_invested
            total_roi_pct = (total_gain_abs / total_invested * 100.0) if total_invested > 0 else 0.0
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
