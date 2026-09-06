"""Job to expire old unconfirmed pending orders."""

from datetime import datetime, timezone

from app.core.constants import ORDER_STATUS_EXPIRED
from app.core.logging import get_logger
from app.db.database import get_db_session
from app.db.repositories.pending_order_repo import PendingOrderRepository

logger = get_logger(__name__)


async def run_order_expiration_check(order_repo: PendingOrderRepository) -> None:
    """Find and mark expired pending orders."""
    with get_db_session() as session:
        now_utc = datetime.now(timezone.utc)
        expired = order_repo.get_expired_pending_orders(session, now_utc)
        for order in expired:
            order_repo.update_status(session, order, ORDER_STATUS_EXPIRED)
            logger.info(f"Order {order.id} ({order.ticker}) expired at {now_utc}")
        if expired:
            session.commit()
