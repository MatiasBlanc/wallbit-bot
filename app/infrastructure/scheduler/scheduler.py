"""Centralized background job scheduler using APScheduler."""

from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.monitoring.metrics import metrics
from app.infrastructure.notifications.repository import NotificationOutboxRepository, dispatch_pending_notifications
from app.infrastructure.wallbit.health import WallbitHealth
from app.infrastructure.wallbit.jobs import refresh_wallbit_health
from app.modules.alerts.jobs import run_alert_checker
from app.modules.alerts.service import AlertService
from app.modules.dca.jobs import run_dca_checker
from app.modules.dca.service import DCAService
from app.modules.orders.jobs import run_order_expiration_check
from app.modules.orders.repository import PendingOrderRepository
from app.modules.reports.jobs import run_daily_report_check
from app.modules.reports.service import ReportService

logger = get_logger(__name__)


class BotScheduler:
    def __init__(
        self,
        bot: Bot,
        report_service: ReportService,
        dca_service: DCAService,
        alert_service: AlertService,
        order_repo: PendingOrderRepository,
        notification_repo: NotificationOutboxRepository,
        health: WallbitHealth | None = None,
    ):
        self.bot = bot
        self.report_service = report_service
        self.dca_service = dca_service
        self.alert_service = alert_service
        self.order_repo = order_repo
        self.notification_repo = notification_repo
        self.health = health
        # Un único scheduler por bot: no acumular ejecuciones al recuperarse de una pausa.
        self.scheduler = AsyncIOScheduler(job_defaults={"max_instances": 1, "coalesce": True})

    def start(self) -> None:
        """Register all recurring jobs and start scheduler."""
        logger.info("Starting centralized scheduler...")

        def _on_job_event(event: Any) -> None:
            success = getattr(event, "exception", None) is None
            metrics.record_job_run(event.job_id, success=success)

        self.scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

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
            args=[self.bot, self.dca_service, self.notification_repo],
            id="dca_checker",
            name="Check due DCA orders",
            replace_existing=True,
        )

        # 3. Alert checker (runs every ALERT_CHECK_INTERVAL_MINUTES)
        self.scheduler.add_job(
            run_alert_checker,
            trigger=IntervalTrigger(minutes=settings.ALERT_CHECK_INTERVAL_MINUTES),
            args=[self.bot, self.alert_service, self.notification_repo],
            id="alert_checker",
            name="Check price and FX alerts",
            replace_existing=True,
        )

        if self.health is not None:
            self.scheduler.add_job(
                refresh_wallbit_health,
                trigger=IntervalTrigger(minutes=2),
                args=[self.health],
                id="wallbit_health",
                name="Refresh Wallbit connection",
                replace_existing=True,
            )

        # 4. Entrega persistente de alertas y propuestas DCA; los fallos se reintentan.
        self.scheduler.add_job(
            dispatch_pending_notifications,
            trigger=IntervalTrigger(minutes=1),
            args=[self.bot, self.notification_repo],
            id="notification_dispatcher",
            name="Deliver pending Telegram notifications",
            replace_existing=True,
        )

        # 5. Order expiration check (runs every 10 minutes)
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
