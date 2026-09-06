"""Order execution and confirmation service with strict idempotency."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ORDER_STATUS_CONFIRMED,
    ORDER_STATUS_EXECUTED,
    ORDER_STATUS_EXPIRED,
    ORDER_STATUS_FAILED,
    ORDER_STATUS_PENDING,
    TX_SOURCE_DCA,
    TX_SOURCE_MANUAL,
    TX_TYPE_BUY,
    TX_TYPE_DCA_BUY,
)
from app.core.logging import get_logger
from app.db.models import DCARule, UserSettings
from app.db.repositories.pending_order_repo import PendingOrderRepository
from app.db.repositories.transaction_repo import LocalTransactionRepository
from app.services.balance_service import BalanceService
from app.utils.datetime_utils import ensure_utc
from app.wallbit.client import WallbitClient
from app.wallbit.exceptions import (
    InsufficientFundsError,
    WallbitApiException,
)
from app.wallbit.schemas import TradeRequest

logger = get_logger(__name__)


@dataclass
class OrderExecutionResult:
    success: bool
    is_simulation: bool
    order_id: str | None = None
    ticker: str = ""
    amount_usd: float = 0.0
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
            rule = session.query(DCARule).filter(DCARule.id == order.dca_rule_id).first()
            if rule and not rule.enabled:
                return OrderExecutionResult(
                    success=False,
                    is_simulation=False,
                    ticker=order.ticker,
                    amount_usd=order.amount_usd,
                    error_message="La regla DCA asociada a esta orden se encuentra pausada o desactivada.",
                )

        # 6. Re-check funds
        balance_info = await self.balance_service.get_balance(target_currency="USD")
        if balance_info.available_usd < order.amount_usd:
            return OrderExecutionResult(
                success=False,
                is_simulation=False,
                ticker=order.ticker,
                amount_usd=order.amount_usd,
                error_message=(
                    f"Saldo insuficiente. Requieres ${order.amount_usd:.2f} USD "
                    f"y tienes ${balance_info.available_usd:.2f} USD disponibles."
                ),
            )

        # 7. Atomically set status to confirmed to prevent double-entry race condition
        self.order_repo.update_status(session, order, ORDER_STATUS_CONFIRMED)
        session.commit()

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
