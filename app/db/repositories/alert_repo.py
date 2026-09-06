"""Alert repository."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Alert


class AlertRepository:
    def get_by_id(self, session: Session, alert_id: int) -> Alert | None:
        return session.query(Alert).filter(Alert.id == alert_id).first()

    def list_by_user(self, session: Session, user_id: int, enabled: bool | None = None) -> list[Alert]:
        query = session.query(Alert).filter(Alert.user_id == user_id)
        if enabled is not None:
            query = query.filter(Alert.enabled == enabled)
        return query.order_by(Alert.id.desc()).all()

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
        alert.enabled = False  # Disable once triggered so it doesn't fire again
        session.flush()
        return alert

    def set_enabled(self, session: Session, alert: Alert, enabled: bool) -> Alert:
        alert.enabled = enabled
        session.flush()
        return alert

    def delete(self, session: Session, alert: Alert) -> None:
        session.delete(alert)
        session.flush()

    def get_active_alerts(self, session: Session) -> list[Alert]:
        return (
            session.query(Alert)
            .filter(Alert.enabled.is_(True), Alert.triggered.is_(False))
            .all()
        )
