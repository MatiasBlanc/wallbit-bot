"""Transaction history service."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.constants import (
    TX_TYPE_BUY,
    TX_TYPE_DCA_BUY,
    TX_TYPE_DEPOSIT,
    TX_TYPE_SELL,
)
from app.core.logging import get_logger
from app.db.repositories.transaction_repo import LocalTransactionRepository
from app.utils.datetime_utils import format_date_es
from app.wallbit.client import WallbitClient

logger = get_logger(__name__)


@dataclass
class HistoryItem:
    icon: str
    title: str
    amount_usd: float
    date_str: str
    status: str


class HistoryService:
    def __init__(self, client: WallbitClient, tx_repo: LocalTransactionRepository):
        self.client = client
        self.tx_repo = tx_repo

    async def get_history(
        self,
        session: Session,
        user_id: int,
        page: int = 1,
        limit: int = 5,
    ) -> tuple[list[HistoryItem], int, int]:
        """
        Retrieve paginated transaction history from Wallbit API,
        or fall back / complement with local transactions.
        Returns (items, current_page, total_pages).
        """
        wallbit_items: list[HistoryItem] = []
        total_pages = 1

        try:
            tx_data = await self.client.get_transactions(page=page, limit=limit)
            total_pages = max(tx_data.pages, 1)

            for tx in tx_data.data:
                # Determine title & icon
                amount = tx.dest_amount or tx.source_amount or 0.0

                # Parse created_at
                try:
                    dt = datetime.fromisoformat(tx.created_at.replace("Z", "+00:00"))
                    date_formatted = format_date_es(dt)
                except Exception:
                    date_formatted = tx.created_at[:10]

                comment = tx.comment or ""
                if "buy" in comment.lower() or tx.type_id == 1:
                    icon = "🟢"
                    title = f"Compra {comment.upper()}".strip()
                elif "sell" in comment.lower():
                    icon = "🔴"
                    title = f"Venta {comment.upper()}".strip()
                elif "deposit" in comment.lower():
                    icon = "💵"
                    title = "Depósito"
                elif "withdraw" in comment.lower():
                    icon = "📤"
                    title = "Retiro"
                else:
                    icon = "🧾"
                    title = comment.capitalize() if comment else "Movimiento"

                wallbit_items.append(
                    HistoryItem(
                        icon=icon,
                        title=title,
                        amount_usd=amount,
                        date_str=date_formatted,
                        status=tx.status,
                    )
                )

            if wallbit_items:
                return wallbit_items, page, total_pages

        except Exception as e:
            logger.warning(f"Failed to fetch transactions from Wallbit API, using local fallback: {e}")

        # Fallback to local transactions
        total_local = self.tx_repo.count_by_user(session, user_id)
        total_pages = max(1, (total_local + limit - 1) // limit)
        offset = (page - 1) * limit
        local_txs = self.tx_repo.list_by_user(session, user_id=user_id, limit=limit, offset=offset)

        items: list[HistoryItem] = []
        for ltx in local_txs:
            if ltx.transaction_type in [TX_TYPE_BUY, TX_TYPE_DCA_BUY]:
                icon = "🟢"
                title = f"Compra {ltx.ticker or ''}".strip()
            elif ltx.transaction_type == TX_TYPE_SELL:
                icon = "🔴"
                title = f"Venta {ltx.ticker or ''}".strip()
            elif ltx.transaction_type == TX_TYPE_DEPOSIT:
                icon = "💵"
                title = "Depósito"
            else:
                icon = "🧾"
                title = ltx.transaction_type

            date_str = format_date_es(ltx.created_at)
            items.append(
                HistoryItem(
                    icon=icon,
                    title=title,
                    amount_usd=ltx.amount_usd,
                    date_str=date_str,
                    status="COMPLETED",
                )
            )

        return items, page, total_pages
