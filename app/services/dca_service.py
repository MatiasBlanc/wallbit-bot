"""DCA Service for managing periodic investment rules and executions."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import DCA_FREQ_MONTHLY, DCA_FREQ_WEEKLY
from app.core.logging import get_logger
from app.db.models import DCARule, PendingOrder, UserSettings
from app.db.repositories.dca_repo import DCARuleRepository
from app.db.repositories.pending_order_repo import PendingOrderRepository
from app.services.balance_service import BalanceService
from app.utils.datetime_utils import calculate_next_dca_execution, ensure_utc, get_now
from app.wallbit.client import WallbitClient
from app.wallbit.exceptions import InvalidTickerError, WallbitApiException

logger = get_logger(__name__)


class DCAService:
    def __init__(
        self,
        dca_repo: DCARuleRepository,
        order_repo: PendingOrderRepository,
        client: WallbitClient,
        balance_service: BalanceService,
    ):
        self.dca_repo = dca_repo
        self.order_repo = order_repo
        self.client = client
        self.balance_service = balance_service

    async def validate_ticker(self, ticker: str) -> bool:
        """Validate if ticker exists in Wallbit."""
        try:
            await self.client.get_asset(ticker)
            return True
        except (InvalidTickerError, WallbitApiException):
            return False
        except Exception as e:
            logger.warning(f"Error validating ticker {ticker}: {e}")
            # If network error, basic uppercase alphanumeric validation
            return ticker.isalnum() and len(ticker) <= 10

    def create_rule(
        self,
        session: Session,
        user: UserSettings,
        ticker: str,
        amount_usd: float,
        frequency: str,
        weekday: int | None = None,
        day_of_month: int | None = None,
    ) -> DCARule:
        """Create a new DCA rule with next execution scheduled."""
        if amount_usd <= 0:
            raise ValueError("El monto debe ser mayor a 0.")
        if frequency not in [DCA_FREQ_WEEKLY, DCA_FREQ_MONTHLY]:
            raise ValueError(f"Frecuencia '{frequency}' no válida.")

        next_exec = calculate_next_dca_execution(
            frequency=frequency,
            weekday=weekday,
            day_of_month=day_of_month,
            tz_name=user.timezone,
            report_time_str=user.report_time,
        )

        rule = self.dca_repo.create(
            session=session,
            user_id=user.id,
            ticker=ticker.upper(),
            amount_usd=amount_usd,
            frequency=frequency,
            next_execution_at=next_exec,
            weekday=weekday,
            day_of_month=day_of_month,
        )
        logger.info(f"dca_created rule_id={rule.id} ticker={rule.ticker} amount={rule.amount_usd} next={next_exec}")
        return rule

    def list_active_rules(self, session: Session, user_id: int) -> list[DCARule]:
        return self.dca_repo.list_by_user(session, user_id=user_id, enabled=True)

    def list_paused_rules(self, session: Session, user_id: int) -> list[DCARule]:
        return self.dca_repo.list_by_user(session, user_id=user_id, enabled=False)

    def get_rule(self, session: Session, rule_id: int) -> DCARule | None:
        return self.dca_repo.get_by_id(session, rule_id=rule_id)

    def pause_rule(self, session: Session, rule: DCARule) -> DCARule:
        rule = self.dca_repo.set_enabled(session, rule, enabled=False)
        logger.info(f"dca_paused rule_id={rule.id}")
        return rule

    def reactivate_rule(self, session: Session, rule: DCARule, user: UserSettings) -> DCARule:
        now = get_now(user.timezone)
        # If next execution was in the past, recalculate
        next_exec_utc = ensure_utc(rule.next_execution_at)
        now_utc = ensure_utc(now)
        if next_exec_utc and now_utc and next_exec_utc <= now_utc:
            rule.next_execution_at = calculate_next_dca_execution(
                frequency=rule.frequency,
                weekday=rule.weekday,
                day_of_month=rule.day_of_month,
                tz_name=user.timezone,
                report_time_str=user.report_time,
                after=now,
            )
        rule = self.dca_repo.set_enabled(session, rule, enabled=True)
        logger.info(f"dca_reactivated rule_id={rule.id} next={rule.next_execution_at}")
        return rule

    def delete_rule(self, session: Session, rule: DCARule) -> None:
        rule_id = rule.id
        self.dca_repo.delete(session, rule)
        logger.info(f"dca_deleted rule_id={rule_id}")

    async def trigger_dca_rule(
        self, session: Session, rule: DCARule, user: UserSettings
    ) -> tuple[bool, PendingOrder | None, float, float | None]:
        """
        Evaluate due DCA rule.
        Returns:
            (has_funds: bool, pending_order: Optional[PendingOrder], available_usd: float, current_price: Optional[float])
        """
        balance_info = await self.balance_service.get_balance(target_currency="USD")
        available_usd = balance_info.available_usd

        # Fetch current asset price if possible
        current_price: float | None = None
        try:
            asset = await self.client.get_asset(rule.ticker)
            current_price = asset.price
        except Exception as e:
            logger.warning(f"Could not fetch market price for {rule.ticker} during DCA check: {e}")

        # Advance next execution date regardless of whether funds were sufficient
        now_utc = datetime.now(timezone.utc)
        next_exec = calculate_next_dca_execution(
            frequency=rule.frequency,
            weekday=rule.weekday,
            day_of_month=rule.day_of_month,
            tz_name=user.timezone,
            report_time_str=user.report_time,
            after=get_now(user.timezone),
        )
        self.dca_repo.update_execution(
            session=session,
            rule=rule,
            last_triggered_at=now_utc,
            next_execution_at=next_exec,
        )

        # Check funds
        if available_usd < rule.amount_usd:
            logger.warning(
                f"dca_insufficient_funds rule_id={rule.id} ticker={rule.ticker} "
                f"needed={rule.amount_usd} available={available_usd}"
            )
            return False, None, available_usd, current_price

        # Create PendingOrder with idempotency key
        idempotency_key = f"dca-{rule.id}-{int(now_utc.timestamp())}-{uuid.uuid4().hex[:6]}"
        expires_at = now_utc + timedelta(hours=settings.ORDER_EXPIRY_HOURS)

        order = self.order_repo.create(
            session=session,
            user_id=user.id,
            ticker=rule.ticker,
            amount_usd=rule.amount_usd,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            dca_rule_id=rule.id,
        )

        logger.info(
            f"dca_triggered rule_id={rule.id} ticker={rule.ticker} "
            f"amount={rule.amount_usd} order_id={order.id} idempotency_key={idempotency_key}"
        )
        return True, order, available_usd, current_price
