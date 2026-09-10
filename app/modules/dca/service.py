"""DCA Service for managing periodic investment rules and executions."""

import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.constants import DCA_FREQ_MONTHLY, DCA_FREQ_WEEKLY
from app.core.logging import get_logger
from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.exceptions import InvalidTickerError, WallbitApiException
from app.modules.balance.service import AccountBalances, BalanceService
from app.modules.dca.models import DCARule
from app.modules.dca.repository import DCARuleRepository
from app.modules.orders.fees import estimate_trade_fee
from app.modules.orders.models import PendingOrder
from app.modules.orders.service import OrderService
from app.modules.settings.models import UserSettings
from app.shared.datetime import calculate_next_dca_execution, ensure_utc, get_now

logger = get_logger(__name__)


class DCAService:
    def __init__(
        self,
        dca_repo: DCARuleRepository,
        order_service: OrderService,
        client: WallbitClient,
        balance_service: BalanceService,
    ):
        self.dca_repo = dca_repo
        self.order_service = order_service
        self.client = client
        self.balance_service = balance_service

    async def resolve_ticker(self, ticker: str) -> tuple[str, str] | None:
        """Confirma el símbolo en Wallbit y devuelve su nombre para mostrarlo al usuario.

        Args:
            ticker: Símbolo ingresado, sin normalizar.

        Returns:
            Tupla (símbolo, nombre) si el activo existe; None si no está en Wallbit.
            Si la red falla, acepta un símbolo alfanumérico corto y usa el ticker como nombre.
        """
        symbol = ticker.upper().strip()
        try:
            asset = await self.client.get_asset(symbol)
            return asset.symbol.upper(), asset.name
        except (InvalidTickerError, WallbitApiException):
            return None
        except Exception as e:
            logger.warning("Error validating ticker %s: %s", symbol, e)
            if symbol.isalnum() and len(symbol) <= 10:
                return symbol, symbol
            return None

    def create_rule(
        self,
        session: Session,
        user: UserSettings,
        ticker: str,
        amount_usd: float,
        frequency: str,
        weekday: int | None = None,
        day_of_month: int | None = None,
        asset_name: str | None = None,
    ) -> DCARule:
        """Crea una regla DCA y calcula su próxima ejecución.

        Args:
            session: Sesión que persistirá la regla.
            user: Propietario y fuente de zona horaria y hora de ejecución.
            ticker: Símbolo del activo.
            amount_usd: Importe positivo de cada compra propuesta.
            frequency: Frecuencia semanal o mensual soportada.
            weekday: Día semanal entre 0 y 6 cuando corresponda.
            day_of_month: Día mensual cuando corresponda.
            asset_name: Nombre opcional del activo para mostrar en Telegram.

        Returns:
            Regla DCA persistida con su próxima fecha de ejecución.

        Raises:
            ValueError: Si el importe o la frecuencia no son válidos.
            sqlalchemy.exc.SQLAlchemyError: Si falla la persistencia.
        """
        if not math.isfinite(amount_usd) or amount_usd <= 0:
            raise ValueError("El monto debe ser positivo y finito.")
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
            asset_name=asset_name,
        )
        logger.info(f"dca_created rule_id={rule.id} ticker={rule.ticker} amount={rule.amount_usd} next={next_exec}")
        return rule

    def list_active_rules(
        self, session: Session, user_id: int, *, limit: int | None = None, offset: int = 0,
    ) -> list[DCARule]:
        return self.dca_repo.list_by_user(session, user_id=user_id, enabled=True, limit=limit, offset=offset)

    def list_paused_rules(
        self, session: Session, user_id: int, *, limit: int | None = None, offset: int = 0,
    ) -> list[DCARule]:
        return self.dca_repo.list_by_user(session, user_id=user_id, enabled=False, limit=limit, offset=offset)

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
        self, session: Session, rule: DCARule, user: UserSettings,
        *, account_balances: AccountBalances | None = None, market_prices: dict[str, float | None] | None = None,
    ) -> tuple[bool, PendingOrder | None, float, float | None]:
        """Propone una compra sin ejecutarla, reutilizando lecturas del mismo ciclo y cuenta.

        Args:
            session: Sesión del llamador que persiste regla y orden conjuntamente.
            rule: Regla vencida del usuario.
            user: Propietario de la regla y de las credenciales del contexto.
            account_balances: Lecturas opcionales del ciclo actual; nunca se usan para confirmar compras.
            market_prices: Cotizaciones por ticker del mismo ciclo, sin caché global.

        Returns:
            Tupla de fondos suficientes, orden pendiente, saldo y precio orientativo.

        Raises:
            WallbitApiException: Si no se pueden comprobar ambos saldos.
            ValueError: Si el monto o la frecuencia no son válidos.
            sqlalchemy.exc.SQLAlchemyError: Si falla la persistencia.
        """
        balance_info = await self.balance_service.get_balance(
            target_currency="USD", include_portfolio=False, account_balances=account_balances,
        )
        if balance_info.checking_usd is None or balance_info.investment_cash_usd is None:
            raise WallbitApiException("No se pudieron verificar los fondos; se volverá a comprobar el DCA.")
        available_usd = balance_info.available_usd

        # Fetch current asset price if possible
        current_price: float | None = None
        if market_prices is not None:
            current_price = market_prices.get(rule.ticker)
        else:
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

        # El saldo debe cubrir el monto y la comisión estimada mostrada al usuario.
        fee_estimate = estimate_trade_fee(session, user, rule.amount_usd)
        if available_usd < float(fee_estimate.total_usd):
            logger.warning(
                f"dca_insufficient_funds rule_id={rule.id} ticker={rule.ticker} "
                f"needed={fee_estimate.total_usd} available={available_usd}"
            )
            return False, None, available_usd, current_price

        # Orders administra la intención; la compra requiere confirmación manual.
        order = self.order_service.create_pending_order(
            session=session,
            user=user,
            ticker=rule.ticker,
            amount_usd=rule.amount_usd,
            dca_rule_id=rule.id,
        )

        logger.info(
            f"dca_triggered rule_id={rule.id} ticker={rule.ticker} "
            f"amount={rule.amount_usd} order_id={order.id} idempotency_key={order.idempotency_key}"
        )
        return True, order, available_usd, current_price
