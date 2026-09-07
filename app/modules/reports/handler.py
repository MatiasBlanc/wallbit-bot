"""/reporte command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.reports.service import ReportService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.presentation.messages import edit_or_reply, format_error, format_loading

logger = get_logger(__name__)


def get_report_handler(report_service: ReportService, user_repo: UserSettingsRepository):
    @restricted
    async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        loading = await update.effective_message.reply_text(format_loading("Armando el resumen"))
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            try:
                report = await report_service.generate_report(session, user)
                msg_text = report.to_telegram_message()
                await edit_or_reply(loading, msg_text, parse_mode="HTML")
            except Exception as error:
                logger.exception("Error generating manual report")
                await edit_or_reply(loading, format_error(error))
                return

    return report_command
