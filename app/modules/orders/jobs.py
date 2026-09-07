"""Job to expire old unconfirmed pending orders."""

from datetime import datetime, timezone

from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.modules.orders.repository import PendingOrderRepository

logger = get_logger(__name__)


async def run_order_expiration_check(order_repo: PendingOrderRepository) -> None:
    """Find and mark expired pending orders."""
    with get_db_session() as session:
        now_utc = datetime.now(timezone.utc)
        expired_count = order_repo.expire_pending(session, now_utc)
    if expired_count:
        logger.info("Órdenes pendientes expiradas: %s", expired_count)
