"""Pending orders repository with idempotency support."""

from datetime import datetime, timezone

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.core.constants import (
    ORDER_STATUS_CONFIRMED,
    ORDER_STATUS_EXECUTED,
    ORDER_STATUS_EXPIRED,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_UNKNOWN,
)
from app.modules.orders.models import PendingOrder


class PendingOrderRepository:
    def get_by_id(self, session: Session, order_id: int) -> PendingOrder | None:
        return session.query(PendingOrder).populate_existing().filter(PendingOrder.id == order_id).first()

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

    def claim_pending(self, session: Session, order_id: int, user_id: int, now: datetime) -> bool:
        """Reclama una orden con un UPDATE condicional, sin enviar la compra.

        Args:
            session: Sesión de escritura; el llamador confirma la transacción.
            order_id: Orden que se desea reclamar.
            user_id: Propietario autorizado.
            now: Hora UTC para volver a comprobar el vencimiento tras consultar fondos.

        Returns:
            True solo si la orden seguía pendiente, vigente y con su regla activa.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: Si falla la escritura.
        """
        result = session.connection().execute(
            update(PendingOrder)
            .where(
                PendingOrder.id == order_id,
                PendingOrder.user_id == user_id,
                PendingOrder.status == ORDER_STATUS_PENDING,
                PendingOrder.expires_at > now,
                or_(PendingOrder.dca_rule_id.is_(None), PendingOrder.dca_rule.has(enabled=True)),
            )
            .values(status=ORDER_STATUS_CONFIRMED)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def expire_pending(self, session: Session, current_time: datetime) -> int:
        """Expira pendientes en una sola sentencia, sin cargar objetos ORM.

        Args:
            session: Sesión de escritura; el llamador controla el commit.
            current_time: Límite UTC de vencimiento.

        Returns:
            Número de órdenes expiradas.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: Si falla la actualización.
        """
        result = session.connection().execute(
            update(PendingOrder)
            .where(PendingOrder.status == ORDER_STATUS_PENDING, PendingOrder.expires_at <= current_time)
            .values(status=ORDER_STATUS_EXPIRED)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount

    def get_expired_pending_orders(self, session: Session, current_time: datetime) -> list[PendingOrder]:
        return (
            session.query(PendingOrder)
            .filter(
                PendingOrder.status == ORDER_STATUS_PENDING,
                PendingOrder.expires_at <= current_time,
            )
            .all()
        )

    def recover_interrupted_orders(self, session: Session) -> int:
        """Mueve a verificación las órdenes interrumpidas durante un envío.

        Args:
            session: Sesión de arranque; el llamador confirma la transacción.

        Returns:
            Cantidad de órdenes que estaban en proceso cuando terminó la instancia anterior.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: Si falla la actualización.
        """
        result = session.connection().execute(
            update(PendingOrder)
            .where(PendingOrder.status == ORDER_STATUS_CONFIRMED)
            .values(status=ORDER_STATUS_UNKNOWN)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount

    def list_unverified_orders(self, session: Session, user_id: int) -> list[PendingOrder]:
        """Obtiene órdenes que quedaron en verificación requerida por timeouts o fallas de red."""
        return (
            session.query(PendingOrder)
            .filter(
                PendingOrder.user_id == user_id,
                PendingOrder.status == ORDER_STATUS_UNKNOWN,
            )
            .order_by(PendingOrder.created_at.desc())
            .all()
        )

    def list_pending_orders(self, session: Session, user_id: int) -> list[PendingOrder]:
        """Obtiene intenciones vigentes que aún requieren una decisión explícita.

        Args:
            session: Sesión de lectura.
            user_id: Propietario local de las órdenes.

        Returns:
            Órdenes pendientes ordenadas desde la más reciente.
        """
        return (
            session.query(PendingOrder)
            .filter(PendingOrder.user_id == user_id, PendingOrder.status == ORDER_STATUS_PENDING)
            .order_by(PendingOrder.created_at.desc())
            .all()
        )

    def resolve_unverified(
        self,
        session: Session,
        order_id: int,
        user_id: int,
        resolved_status: str,
        external_order_id: str | None = None,
    ) -> bool:
        """Resuelve manualmente una orden que requería verificación tras consultar Wallbit."""
        order = (
            session.query(PendingOrder)
            .filter(
                PendingOrder.id == order_id,
                PendingOrder.user_id == user_id,
                PendingOrder.status == ORDER_STATUS_UNKNOWN,
            )
            .first()
        )
        if not order:
            return False
        order.status = resolved_status
        if external_order_id:
            order.external_order_id = external_order_id
        if resolved_status == ORDER_STATUS_EXECUTED:
            order.executed_at = datetime.now(timezone.utc)
        session.flush()
        return True

