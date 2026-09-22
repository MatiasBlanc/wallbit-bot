"""El scheduler utiliza los jobs que pertenecen a cada módulo."""

from unittest.mock import Mock

from app.infrastructure.notifications.repository import dispatch_pending_notifications
from app.infrastructure.scheduler.scheduler import BotScheduler
from app.infrastructure.wallbit.jobs import refresh_wallbit_health
from app.modules.alerts.jobs import run_alert_checker
from app.modules.dca.jobs import run_dca_checker
from app.modules.orders.jobs import run_order_expiration_check
from app.modules.reports.jobs import run_daily_report_check


def test_scheduler_registers_domain_jobs(report_service, dca_service, alert_service, order_repo):
    bot = Mock()
    health = Mock()
    notification_repo = Mock()
    scheduler = BotScheduler(
        bot, report_service, dca_service, alert_service, order_repo, notification_repo, health=health
    )
    scheduler.scheduler = Mock()
    scheduler.start()

    jobs = {call.kwargs["id"]: call for call in scheduler.scheduler.add_job.call_args_list}
    expected = {
        "daily_report_check": (run_daily_report_check, [bot, report_service]),
        "dca_checker": (run_dca_checker, [bot, dca_service, notification_repo]),
        "alert_checker": (run_alert_checker, [bot, alert_service, notification_repo]),
        "wallbit_health": (refresh_wallbit_health, [health]),
        "notification_dispatcher": (dispatch_pending_notifications, [bot, notification_repo]),
        "order_expiration": (run_order_expiration_check, [order_repo]),
    }
    assert jobs.keys() == expected.keys()
    for job_id, (job, args) in expected.items():
        assert jobs[job_id].args == (job,)
        assert jobs[job_id].kwargs["args"] == args
        assert jobs[job_id].kwargs["replace_existing"] is True
    scheduler.scheduler.start.assert_called_once_with()
    scheduler.shutdown()
    scheduler.scheduler.shutdown.assert_called_once_with(wait=False)
