"""Order execution and confirmation service with strict idempotency."""

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ORDER_STATUS_EXECUTED,
    ORDER_STATUS_EXPIRED,
    ORDER_STATUS_FAILED,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_UNKNOWN,
    TX_SOURCE_DCA,
    TX_SOURCE_MANUAL,
    TX_TYPE_BUY,
    TX_TYPE_DCA_BUY,
)
from app.core.logging import get_logger
from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.exceptions import (
    InsufficientFundsError,
    WallbitApiException,
    WallbitUnavailableError,
)
from app.infrastructure.wallbit.schemas.orders import TradeRequest
from app.modules.balance.service import BalanceService
from app.modules.history.repository import LocalTransactionRepository
from app.modules.orders.fees import estimate_trade_fee
from app.modules.orders.models import PendingOrder
from app.modules.orders.repository import PendingOrderRepository
from app.modules.settings.models import UserSettings
from app.shared.datetime import ensure_utc

logger = get_logger(__name__)


@dataclass(slots=True)
class OrderExecutionResult:
    success: bool
    is_simulation: bool
    order_id: str | None = None
    ticker: str = ""
    amount_usd: float = 0.0
    estimated_fee_usd: float = 0.0
    estimated_total_usd: float = 0.0
    error_message: str | None = None
    already_processed: bool = False


class OrderService:
    def __init__(
        self,
        order_repo: PendingOrderRepository,
        tx_repo: LocalTransactionRepository,
        client: WallbitClient,
        balance_service: BalanceService,
    ):
        self.order_repo = order_repo
        self.tx_repo = tx_repo
        self.client = client
        self.balance_service = balance_service

    def create_pending_order(
        self,
        session: Session,
        user: UserSettings,
        ticker: str,
        amount_usd: float,
        dca_rule_id: int | None = None,
    ) -> PendingOrder:
        """Crea una intención de compra sin ejecutarla ni confirmar la transacción.

        Args:
            session: Sesión que persiste la orden; el llamador controla el commit.
            user: Usuario propietario de la orden.
            ticker: Símbolo del activo que se desea comprar.
            amount_usd: Importe positivo de la compra en USD.
            dca_rule_id: Regla de origen, o None para una compra manual.

        Returns:
            Orden pendiente con vencimiento y clave de idempotencia únicos.

        Raises:
            ValueError: Si el importe no es positivo o finito.
            sqlalchemy.exc.SQLAlchemyError: Si no se puede persistir la orden.
        """
        if not math.isfinite(amount_usd) or amount_usd <= 0:
            raise ValueError("El monto debe ser positivo y finito.")

        now_utc = datetime.now(timezone.utc)
        prefix = f"dca-{dca_rule_id}" if dca_rule_id is not None else "manual"
        idempotency_key = f"{prefix}-{int(now_utc.timestamp())}-{uuid.uuid4().hex[:6]}"
        return self.order_repo.create(
            session=session,
            user_id=user.id,
            ticker=ticker,
            amount_usd=amount_usd,
            expires_at=now_utc + timedelta(hours=settings.ORDER_EXPIRY_HOURS),
            idempotency_key=idempotency_key,
            dca_rule_id=dca_rule_id,
        )

    async def confirm_order(
        self,
        session: Session,
        order_id: int,
        user: UserSettings,
    ) -> OrderExecutionResult:
        """
        Confirm and execute a pending order with strict idempotency checks.
        """
        # 1. Fetch order
        order = self.order_repo.get_by_id(session, order_id)
        if not order:
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                error_message="Orden no encontrada.",
            )

        # 2. Check ownership
        if order.user_id != user.id:
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                error_message="No tienes permiso para operar esta orden.",
            )

        # 3. Check idempotency / already processed
        if order.status != ORDER_STATUS_PENDING:
            logger.info(f"order_already_processed order_id={order.id} status={order.status}")
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                already_processed=True,
                error_message="Esta operación ya fue procesada.",
            )

        # 4. Check expiration
        now_utc = datetime.now(timezone.utc)
        expires_at_utc = ensure_utc(order.expires_at)
        if expires_at_utc and expires_at_utc <= now_utc:
            self.order_repo.update_status(session, order, ORDER_STATUS_EXPIRED)
            logger.info(f"order_expired order_id={order.id}")
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                error_message="Esta solicitud ha expirado. Por favor espera la próxima ejecución.",
            )

        # 5. Check if linked DCA rule is still active
        if order.dca_rule_id:
            rule = order.dca_rule
            if rule and not rule.enabled:
                return OrderExecutionResult(
                    success=False,
                    is_simulation=False,
                    ticker=order.ticker,
                    amount_usd=order.amount_usd,
                    error_message="La regla DCA asociada a esta orden se encuentra pausada o desactivada.",
                )

        # 6. Re-check funds
        balance_info = await self.balance_service.get_balance(target_currency="USD", include_portfolio=False)
        if balance_info.checking_usd is None or balance_info.investment_cash_usd is None:
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                error_message="No se pudieron verificar los fondos. No se envió ninguna compra.",
            )
        fee_estimate = estimate_trade_fee(session, user, order.amount_usd)
        estimated_fee_usd = float(fee_estimate.fee_usd)
        estimated_total_usd = float(fee_estimate.total_usd)
        if balance_info.available_usd < estimated_total_usd:
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                estimated_fee_usd=estimated_fee_usd,
                estimated_total_usd=estimated_total_usd,
                error_message=(
                    f"Saldo insuficiente. El total aproximado es ${estimated_total_usd:.2f} USD "
                    f"y tienes ${balance_info.available_usd:.2f} USD disponibles."
                ),
            )

        # La condición se valida en SQL: dos sesiones no pueden reclamar la misma orden.
        if not self.order_repo.claim_pending(session, order.id, user.id, datetime.now(timezone.utc)):
            session.rollback()
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                already_processed=True,
                error_message="Esta orden ya fue procesada, expiró o su regla fue desactivada.",
            )
        session.commit()
        session.refresh(order)

        # 8. Check TRADING_ENABLED
        is_simulation = not settings.TRADING_ENABLED

        if is_simulation:
            # DRY-RUN / SIMULATION MODE
            sim_order_id = f"SIM-{uuid.uuid4().hex[:8].upper()}"
            self.order_repo.update_status(
                session,
                order,
                new_status=ORDER_STATUS_EXECUTED,
                external_order_id=sim_order_id,
                executed_at=datetime.now(timezone.utc),
            )
            # Record local transaction
            tx_type = TX_TYPE_DCA_BUY if order.dca_rule_id else TX_TYPE_BUY
            tx_source = TX_SOURCE_DCA if order.dca_rule_id else TX_SOURCE_MANUAL
            self.tx_repo.create(
                session=session,
                user_id=user.id,
                transaction_type=tx_type,
                amount_usd=order.amount_usd,
                ticker=order.ticker,
                external_order_id=sim_order_id,
                source=f"{tx_source}_SIMULATION",
            )
            session.commit()

            logger.info(
                f"order_simulated order_id={order.id} sim_id={sim_order_id} "
                f"ticker={order.ticker} amount={order.amount_usd}"
            )
            return OrderExecutionResult(
                success=True,
                is_simulation=True,
                order_id=sim_order_id,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                estimated_fee_usd=estimated_fee_usd,
                estimated_total_usd=estimated_total_usd,
            )

        # 9. REAL TRADING MODE
        try:
            trade_req = TradeRequest(
                symbol=order.ticker,
                direction="BUY",
                currency="USD",
                order_type="MARKET",
                amount=order.amount_usd,
            )
            result = await self.client.create_trade(trade_req)
            external_id = result.id or f"ORD-{uuid.uuid4().hex[:8].upper()}"

            self.order_repo.update_status(
                session,
                order,
                new_status=ORDER_STATUS_EXECUTED,
                external_order_id=external_id,
                executed_at=datetime.now(timezone.utc),
            )

            tx_type = TX_TYPE_DCA_BUY if order.dca_rule_id else TX_TYPE_BUY
            tx_source = TX_SOURCE_DCA if order.dca_rule_id else TX_SOURCE_MANUAL
            self.tx_repo.create(
                session=session,
                user_id=user.id,
                transaction_type=tx_type,
                amount_usd=order.amount_usd,
                ticker=order.ticker,
                external_order_id=external_id,
                source=tx_source,
            )
            session.commit()

            logger.info(
                f"order_executed order_id={order.id} ext_id={external_id} "
                f"ticker={order.ticker} amount={order.amount_usd}"
            )
            return OrderExecutionResult(
                success=True,
                is_simulation=False,
                order_id=external_id,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                estimated_fee_usd=estimated_fee_usd,
                estimated_total_usd=estimated_total_usd,
            )

        except InsufficientFundsError:
            self.order_repo.update_status(session, order, ORDER_STATUS_FAILED)
            session.commit()
            logger.error(f"order_failed insufficient funds order_id={order.id}")
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                error_message="Wallbit rechazó la orden por saldo insuficiente.",
            )
        except WallbitUnavailableError:
            # Un timeout o un 5xx no demuestra que Wallbit no haya aceptado la orden.
            # Nunca se reintenta a ciegas: la orden queda pendiente de verificación.
            self.order_repo.update_status(session, order, ORDER_STATUS_UNKNOWN)
            session.commit()
            logger.error("order_verification_required order_id=%s", order.id)
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                error_message=(
                    "Wallbit no confirmó el resultado de la compra. "
                    "La operación quedó pendiente de verificación; no la reintentes."
                ),
            )
        except WallbitApiException as e:
            self.order_repo.update_status(session, order, ORDER_STATUS_FAILED)
            session.commit()
            logger.error(f"order_failed order_id={order.id} error={e}")
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                error_message=e.user_message,
            )
        except Exception:
            self.order_repo.update_status(session, order, ORDER_STATUS_FAILED)
            session.commit()
            logger.exception(f"order_failed_unexpected order_id={order.id}")
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                error_message="Ocurrió un error inesperado al procesar la compra.",
            )

    def list_orders_needing_verification(self, session: Session, user_id: int) -> list[PendingOrder]:
        """Devuelve órdenes marcadas como verification_required para revisión manual."""
        return self.order_repo.list_unverified_orders(session, user_id)

    def list_pending_orders(self, session: Session, user_id: int) -> list[PendingOrder]:
        """Devuelve compras propuestas que todavía esperan confirmación Telegram.

        Args:
            session: Sesión de lectura.
            user_id: Propietario local de las órdenes.

        Returns:
            Intenciones pendientes y vigentes según la base local.
        """
        return self.order_repo.list_pending_orders(session, user_id)

    def reconcile_order(
        self,
        session: Session,
        user_id: int,
        order_id: int,
        was_executed_on_wallbit: bool,
        external_order_id: str | None = None,
    ) -> bool:
        """Reconcilia una orden cuyo estado de red era indeterminado."""
        new_status = ORDER_STATUS_EXECUTED if was_executed_on_wallbit else ORDER_STATUS_FAILED
        success = self.order_repo.resolve_unverified(
            session=session,
            order_id=order_id,
            user_id=user_id,
            resolved_status=new_status,
            external_order_id=external_order_id,
        )
        if success and was_executed_on_wallbit:
            order = self.order_repo.get_by_id(session, order_id)
            if order:
                tx_type = TX_TYPE_DCA_BUY if order.dca_rule_id else TX_TYPE_BUY
                tx_source = TX_SOURCE_DCA if order.dca_rule_id else TX_SOURCE_MANUAL
                self.tx_repo.create(
                    session=session,
                    user_id=user_id,
                    transaction_type=tx_type,
                    amount_usd=order.amount_usd,
                    ticker=order.ticker,
                    external_order_id=external_order_id or order.external_order_id or f"REC-{order_id}",
                    source=f"{tx_source}_RECONCILED",
                )
        session.commit()
        return success

