"""User settings repository."""


from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.modules.settings.models import UserSettings


class UserSettingsRepository:
    def get_by_telegram_id(self, session: Session, telegram_user_id: int) -> UserSettings | None:
        return session.query(UserSettings).filter(UserSettings.telegram_user_id == telegram_user_id).first()

    def get_or_create(self, session: Session, telegram_user_id: int) -> UserSettings:
        user = self.get_by_telegram_id(session, telegram_user_id)
        if not user:
            user = UserSettings(
                telegram_user_id=telegram_user_id,
                default_currency=app_settings.DEFAULT_CURRENCY,
                report_time=app_settings.DEFAULT_REPORT_TIME,
                timezone=app_settings.DEFAULT_TIMEZONE,
                alerts_enabled=True,
            )
            session.add(user)
            session.flush()
        return user

    def update_currency(self, session: Session, user: UserSettings, currency: str) -> UserSettings:
        user.default_currency = currency.upper()
        session.flush()
        return user

    def update_report_time(self, session: Session, user: UserSettings, report_time: str) -> UserSettings:
        user.report_time = report_time
        session.flush()
        return user

    def update_timezone(self, session: Session, user: UserSettings, timezone: str) -> UserSettings:
        user.timezone = timezone
        session.flush()
        return user

    def update_alerts_enabled(self, session: Session, user: UserSettings, enabled: bool) -> UserSettings:
        user.alerts_enabled = enabled
        session.flush()
        return user

    def update_last_daily_report(self, session: Session, user: UserSettings, date_str: str) -> UserSettings:
        user.last_daily_report = date_str
        session.flush()
        return user
