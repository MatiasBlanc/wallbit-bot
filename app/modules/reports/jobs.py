"""Daily morning report background job."""

from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot

from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.modules.auth.jobs import for_each_account, job_telegram_user_id
from app.modules.reports.service import ReportService
from app.modules.settings.models import UserSettings

logger = get_logger(__name__)


@for_each_account
async def run_daily_report_check(bot: Bot, report_service: ReportService) -> None:
    """
    Checks if it is time to send the daily report for the authorized user.
    Prevents duplicate reports if application restarts.
    """
    with get_db_session() as session:
        user = (
            session.query(UserSettings)
            .filter(UserSettings.telegram_user_id == job_telegram_user_id())
            .first()
        )
        if not user:
            return

        # Check current time in user's timezone
        try:
            tz = ZoneInfo(user.timezone)
        except Exception:
            tz = ZoneInfo("UTC")

        now_user_tz = datetime.now(tz)
        today_str = now_user_tz.strftime("%Y-%m-%d")
        current_time_str = now_user_tz.strftime("%H:%M")

        # Has report already been sent today?
        if user.last_daily_report == today_str:
            return

        # Is it at or past configured report time?
        if current_time_str >= user.report_time:
            logger.info(f"Triggering daily report for user {user.telegram_user_id} at {current_time_str}")
            try:
                report = await report_service.generate_report(session, user)
                msg_text = report.to_telegram_message()
                await bot.send_message(
                    chat_id=user.telegram_user_id,
                    text=msg_text,
                    parse_mode="HTML",
                )
                user.last_daily_report = today_str
                session.commit()
                logger.info(f"Daily report sent successfully to {user.telegram_user_id}")
            except Exception as e:
                logger.error(f"Failed to send daily report: {e}")
