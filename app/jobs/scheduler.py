"""Centralized background job scheduler using APScheduler."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

from app.core.config import settings
from app.core.logging import get_logger
from app.db.repositories.pending_order_repo import PendingOrderRepository
from app.jobs.alert_checker import run_alert_checker
from app.jobs.daily_report import run_daily_report_check
from app.jobs.dca_checker import run_dca_checker
from app.jobs.order_expiration import run_order_expiration_check
from app.services.alert_service import AlertService
from app.services.dca_service import DCAService
from app.services.report_service import ReportService

logger = get_logger(__name__)


class BotScheduler:
    def __init__(
        self,
        bot: Bot,
        report_service: ReportService,
        dca_service: DCAService,
        alert_service: AlertService,
        order_repo: PendingOrderRepository,
    ):
        self.bot = bot
        self.report_service = report_service
        self.dca_service = dca_service
        self.alert_service = alert_service
        self.order_repo = order_repo
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """Register all recurring jobs and start scheduler."""
        logger.info("Starting centralized scheduler...")

        # 1. Daily report check (runs every minute to check if configured morning time matches)
        self.scheduler.add_job(
            run_daily_report_check,
            trigger=IntervalTrigger(minutes=1),
            args=[self.bot, self.report_service],
            id="daily_report_check",
            name="Check daily report time",
            replace_existing=True,
        )

        # 2. DCA checker (runs every minute to check if scheduled DCA time has arrived)
        self.scheduler.add_job(
            run_dca_checker,
            trigger=IntervalTrigger(minutes=settings.DCA_CHECK_INTERVAL_MINUTES),
            args=[self.bot, self.dca_service],
            id="dca_checker",
            name="Check due DCA orders",
            replace_existing=True,
        )

        # 3. Alert checker (runs every ALERT_CHECK_INTERVAL_MINUTES)
        self.scheduler.add_job(
            run_alert_checker,
            trigger=IntervalTrigger(minutes=settings.ALERT_CHECK_INTERVAL_MINUTES),
            args=[self.bot, self.alert_service],
            id="alert_checker",
            name="Check price and FX alerts",
            replace_existing=True,
        )

        # 4. Order expiration check (runs every 10 minutes)
        self.scheduler.add_job(
            run_order_expiration_check,
            trigger=IntervalTrigger(minutes=10),
            args=[self.order_repo],
            id="order_expiration",
            name="Expire unconfirmed orders",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Centralized scheduler started successfully with all jobs registered.")

    def shutdown(self) -> None:
        """Gracefully stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Centralized scheduler shut down.")
