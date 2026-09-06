"""DCA rules repository."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import DCARule


class DCARuleRepository:
    def get_by_id(self, session: Session, rule_id: int) -> DCARule | None:
        return session.query(DCARule).filter(DCARule.id == rule_id).first()

    def list_by_user(self, session: Session, user_id: int, enabled: bool | None = None) -> list[DCARule]:
        query = session.query(DCARule).filter(DCARule.user_id == user_id)
        if enabled is not None:
            query = query.filter(DCARule.enabled == enabled)
        return query.order_by(DCARule.id.asc()).all()

    def create(
        self,
        session: Session,
        user_id: int,
        ticker: str,
        amount_usd: float,
        frequency: str,
        next_execution_at: datetime,
        weekday: int | None = None,
        day_of_month: int | None = None,
    ) -> DCARule:
        rule = DCARule(
            user_id=user_id,
            ticker=ticker.upper(),
            amount_usd=amount_usd,
            frequency=frequency,
            weekday=weekday,
            day_of_month=day_of_month,
            enabled=True,
            next_execution_at=next_execution_at,
        )
        session.add(rule)
        session.flush()
        return rule

    def set_enabled(self, session: Session, rule: DCARule, enabled: bool) -> DCARule:
        rule.enabled = enabled
        session.flush()
        return rule

    def update_execution(
        self,
        session: Session,
        rule: DCARule,
        last_triggered_at: datetime,
        next_execution_at: datetime,
    ) -> DCARule:
        rule.last_triggered_at = last_triggered_at
        rule.next_execution_at = next_execution_at
        session.flush()
        return rule

    def delete(self, session: Session, rule: DCARule) -> None:
        session.delete(rule)
        session.flush()

    def get_due_rules(self, session: Session, current_time: datetime) -> list[DCARule]:
        return (
            session.query(DCARule)
            .filter(DCARule.enabled.is_(True), DCARule.next_execution_at <= current_time)
            .all()
        )
