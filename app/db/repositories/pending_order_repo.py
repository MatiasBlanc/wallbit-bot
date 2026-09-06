"""Pending orders repository with idempotency support."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.constants import (
    ORDER_STATUS_PENDING,
)
from app.db.models import PendingOrder


class PendingOrderRepository:
    def get_by_id(self, session: Session, order_id: int) -> PendingOrder | None:
        return session.query(PendingOrder).filter(PendingOrder.id == order_id).first()

    def get_by_idempotency_key(self, session: Session, idempotency_key: str) -> PendingOrder | None:
        return session.query(PendingOrder).filter(PendingOrder.idempotency_key == idempotency_key).first()

    def create(
        self,
        session: Session,
        user_id: int,
        ticker: str,
        amount_usd: float,
        expires_at: datetime,
        idempotency_key: str,
        dca_rule_id: int | None = None,
    ) -> PendingOrder:
        order = PendingOrder(
            user_id=user_id,
            dca_rule_id=dca_rule_id,
            ticker=ticker.upper(),
            amount_usd=amount_usd,
            status=ORDER_STATUS_PENDING,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
        )
        session.add(order)
        session.flush()
        return order

    def update_status(
        self,
        session: Session,
        order: PendingOrder,
        new_status: str,
        external_order_id: str | None = None,
        executed_at: datetime | None = None,
    ) -> PendingOrder:
        order.status = new_status
        if external_order_id is not None:
            order.external_order_id = external_order_id
        if executed_at is not None:
            order.executed_at = executed_at
        session.flush()
        return order

    def get_expired_pending_orders(self, session: Session, current_time: datetime) -> list[PendingOrder]:
        return (
            session.query(PendingOrder)
            .filter(
                PendingOrder.status == ORDER_STATUS_PENDING,
                PendingOrder.expires_at <= current_time,
            )
            .all()
        )
