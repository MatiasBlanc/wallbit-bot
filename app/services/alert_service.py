"""Alert service for price and exchange rate threshold notifications."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.constants import (
    ALERT_TYPE_FX,
    ALERT_TYPE_PRICE,
    OPERATOR_GTE,
    OPERATOR_LTE,
)
from app.core.logging import get_logger
from app.db.models import Alert, UserSettings
from app.db.repositories.alert_repo import AlertRepository
from app.services.exchange_service import ExchangeRateService
from app.wallbit.client import WallbitClient

logger = get_logger(__name__)


@dataclass
class TriggeredAlert:
    alert: Alert
    current_value: float
    message: str


class AlertService:
    def __init__(
        self,
        alert_repo: AlertRepository,
        client: WallbitClient,
        exchange_service: ExchangeRateService,
    ):
        self.alert_repo = alert_repo
        self.client = client
        self.exchange_service = exchange_service

    def create_alert(
        self,
        session: Session,
        user: UserSettings,
        alert_type: str,
        symbol: str,
        operator: str,
        target_value: float,
    ) -> Alert:
        if operator not in [OPERATOR_GTE, OPERATOR_LTE]:
            raise ValueError(f"Operador no válido: {operator}. Usa '>=' o '<='.")
        if target_value <= 0:
            raise ValueError("El valor objetivo debe ser mayor a 0.")

        clean_symbol = symbol.upper().strip()
        alert = self.alert_repo.create(
            session=session,
            user_id=user.id,
            alert_type=alert_type,
            symbol=clean_symbol,
            operator=operator,
            target_value=target_value,
        )
        logger.info(
            f"alert_created alert_id={alert.id} type={alert.alert_type} "
            f"symbol={alert.symbol} op={alert.operator} target={alert.target_value}"
        )
        return alert

    def list_user_alerts(self, session: Session, user_id: int) -> list[Alert]:
        return self.alert_repo.list_by_user(session, user_id=user_id)

    def delete_alert(self, session: Session, alert: Alert) -> None:
        alert_id = alert.id
        self.alert_repo.delete(session, alert)
        logger.info(f"alert_deleted alert_id={alert_id}")

    async def check_active_alerts(self, session: Session) -> list[TriggeredAlert]:
        """
        Check all active, un-triggered alerts against current market prices or FX rates.
        Marks triggered alerts in DB and returns the triggered alerts list.
        """
        active_alerts = self.alert_repo.get_active_alerts(session)
        if not active_alerts:
            return []

        triggered_list: list[TriggeredAlert] = []
        now_utc = datetime.now(timezone.utc)

        # Cache values during this check cycle to avoid repeated API calls
        price_cache = {}
        fx_cache = {}

        for alert in active_alerts:
            current_val: float | None = None

            if alert.alert_type == ALERT_TYPE_PRICE:
                symbol = alert.symbol
                if symbol not in price_cache:
                    try:
                        asset = await self.client.get_asset(symbol)
                        price_cache[symbol] = asset.price
                    except Exception as e:
                        logger.warning(f"Could not fetch price for alert {symbol}: {e}")
                        price_cache[symbol] = None
                current_val = price_cache.get(symbol)

            elif alert.alert_type == ALERT_TYPE_FX:
                # Expect format e.g. "USD/CLP" or "USDCLP"
                raw = alert.symbol.replace("/", "").strip()
                if len(raw) == 6:
                    source, dest = raw[:3], raw[3:]
                else:
                    source, dest = "USD", "CLP"

                fx_key = (source, dest)
                if fx_key not in fx_cache:
                    try:
                        rate = await self.exchange_service.get_rate(source, dest)
                        fx_cache[fx_key] = rate
                    except Exception as e:
                        logger.warning(f"Could not fetch FX rate for alert {alert.symbol}: {e}")
                        fx_cache[fx_key] = None
                current_val = fx_cache.get(fx_key)

            if current_val is None:
                continue

            # Evaluate condition
            is_triggered = False
            if alert.operator == OPERATOR_GTE and current_val >= alert.target_value or alert.operator == OPERATOR_LTE and current_val <= alert.target_value:
                is_triggered = True

            if is_triggered:
                self.alert_repo.mark_triggered(session, alert, triggered_at=now_utc)
                msg = (
                    f"🔔 <b>Alerta alcanzada</b>\n\n"
                    f"{alert.symbol} llegó a <b>${current_val:,.2f}</b>\n\n"
                    f"Tu objetivo era:\n"
                    f"{alert.symbol} {alert.operator} ${alert.target_value:,.2f}"
                )
                triggered_list.append(
                    TriggeredAlert(alert=alert, current_value=current_val, message=msg)
                )
                logger.info(
                    f"alert_triggered alert_id={alert.id} symbol={alert.symbol} "
                    f"current={current_val} target={alert.target_value}"
                )

        if triggered_list:
            session.commit()

        return triggered_list
