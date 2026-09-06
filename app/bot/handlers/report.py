"""/reporte command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.report_service import ReportService

logger = get_logger(__name__)


def get_report_handler(report_service: ReportService, user_repo: UserSettingsRepository):
    @restricted
    async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            try:
                report = await report_service.generate_report(session, user)
                msg_text = report.to_telegram_message()
                await update.effective_message.reply_text(msg_text, parse_mode="HTML")
            except Exception:
                logger.exception("Error generating manual report")
                await update.effective_message.reply_text(
                    "No se pudo generar el reporte en este momento. Inténtalo nuevamente más tarde."
                )

    return report_command
