"""Pruebas del colector de métricas y observabilidad."""

from app.infrastructure.monitoring.metrics import MetricsCollector


def test_metrics_collector_api_calls():
    collector = MetricsCollector()
    assert collector.wallbit_requests_total == 0
    assert collector.get_avg_latency_ms() == 0.0

    collector.record_api_call(100.0, success=True)
    collector.record_api_call(200.0, success=False)

    assert collector.wallbit_requests_total == 2
    assert collector.wallbit_requests_failed == 1
    assert collector.get_avg_latency_ms() == 150.0


def test_metrics_collector_job_runs():
    collector = MetricsCollector()
    collector.record_job_run("dca_checker", success=True, duration_s=0.05)
    collector.record_job_run("dca_checker", success=False, duration_s=0.10)

    snap = collector.snapshot()
    assert "dca_checker" in snap["jobs"]
    job_data = snap["jobs"]["dca_checker"]
    assert job_data["runs"] == 2
    assert job_data["errors"] == 1
    assert job_data["last_status"] == "ERROR"


def test_metrics_collector_telegram_report():
    collector = MetricsCollector()
    collector.record_api_call(45.0, success=True)
    collector.record_job_run("alert_checker", success=True, duration_s=0.02)

    report = collector.format_telegram_report()
    assert "Estado del Sistema y Métricas" in report
    assert "API Wallbit:" in report
    assert "alert_checker" in report
