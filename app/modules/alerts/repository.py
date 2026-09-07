"""Alert repository."""

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.modules.alerts.models import Alert
from app.modules.settings.models import UserSettings


class AlertRepository:
    def get_by_id(self, session: Session, alert_id: int) -> Alert | None:
        return session.query(Alert).filter(Alert.id == alert_id).first()

    def list_by_user(
        self, session: Session, user_id: int, enabled: bool | None = None,
        *, limit: int | None = None, offset: int = 0,
    ) -> list[Alert]:
        query = session.query(Alert).filter(Alert.user_id == user_id)
        if enabled is not None:
            query = query.filter(Alert.enabled == enabled)
        query = query.order_by(Alert.id.desc()).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(
        self,
        session: Session,
        user_id: int,
        alert_type: str,
        symbol: str,
        operator: str,
        target_value: float,
    ) -> Alert:
        alert = Alert(
            user_id=user_id,
            alert_type=alert_type,
            symbol=symbol.upper(),
            operator=operator,
            target_value=target_value,
            enabled=True,
            triggered=False,
        )
        session.add(alert)
        session.flush()
        return alert

    def mark_triggered(self, session: Session, alert: Alert, triggered_at: datetime) -> Alert:
        alert.triggered = True
        alert.triggered_at = triggered_at
        alert.enabled = False
        # El servicio confirma todas las alertas del lote en un único flush.
        return alert

    def set_enabled(self, session: Session, alert: Alert, enabled: bool) -> Alert:
        alert.enabled = enabled
        session.flush()
        return alert

    def delete(self, session: Session, alert: Alert) -> None:
        session.delete(alert)
        session.flush()

    def get_active_alerts(self, session: Session, *, telegram_user_id: int | None = None) -> list[Alert]:
        query = (
            session.query(Alert)
            .join(Alert.user)
            .options(joinedload(Alert.user))
            .filter(Alert.enabled.is_(True), Alert.triggered.is_(False), UserSettings.alerts_enabled.is_(True))
        )
        if telegram_user_id is not None:
            query = query.filter(UserSettings.telegram_user_id == telegram_user_id)
        return query.all()
