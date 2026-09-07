"""Colector de métricas en memoria para observabilidad y salud del bot."""

import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from app.core.config import settings


@dataclass
class JobMetric:
    runs_count: int = 0
    errors_count: int = 0
    last_run_at: datetime | None = None
    last_status: str = "never_run"
    last_duration_s: float = 0.0


class MetricsCollector:
    """Registra eventos y latencias del sistema sin impacto en rendimiento."""

    def __init__(self) -> None:
        self.started_at: datetime = datetime.now(timezone.utc)
        self.wallbit_requests_total: int = 0
        self.wallbit_requests_failed: int = 0
        self._latencies_ms: deque[float] = deque(maxlen=100)
        self._jobs: dict[str, JobMetric] = {}

    def record_api_call(self, latency_ms: float, success: bool = True) -> None:
        """Registra una llamada a la API de Wallbit."""
        self.wallbit_requests_total += 1
        if not success:
            self.wallbit_requests_failed += 1
        self._latencies_ms.append(round(latency_ms, 2))

    def record_job_run(self, job_name: str, success: bool, duration_s: float = 0.0) -> None:
        """Registra la ejecución de una tarea del planificador."""
        if job_name not in self._jobs:
            self._jobs[job_name] = JobMetric()
        m = self._jobs[job_name]
        m.runs_count += 1
        m.last_run_at = datetime.now(timezone.utc)
        m.last_duration_s = round(duration_s, 3)
        if success:
            m.last_status = "OK"
        else:
            m.errors_count += 1
            m.last_status = "ERROR"

    def get_avg_latency_ms(self) -> float:
        if not self._latencies_ms:
            return 0.0
        return round(sum(self._latencies_ms) / len(self._latencies_ms), 1)

    def get_uptime_str(self) -> str:
        delta = datetime.now(timezone.utc) - self.started_at
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        mins, secs = divmod(rem, 60)
        if days > 0:
            return f"{days}d {hours}h {mins}m"
        if hours > 0:
            return f"{hours}h {mins}m {secs}s"
        return f"{mins}m {secs}s"

    def get_db_size_mb(self) -> float:
        """Calcula el tamaño del archivo SQLite si la URL es local."""
        try:
            parsed = urlsplit(settings.DATABASE_URL)
            path = parsed.path
            if path and os.path.exists(path):
                return round(os.path.getsize(path) / (1024 * 1024), 2)
            # Handle sqlite:///wallbit.db format
            clean_path = settings.DATABASE_URL.replace("sqlite:///", "")
            if os.path.exists(clean_path):
                return round(os.path.getsize(clean_path) / (1024 * 1024), 2)
        except Exception:
            pass
        return 0.0

    def snapshot(self) -> dict[str, Any]:
        """Devuelve un diccionario estructurado de métricas."""
        return {
            "uptime": self.get_uptime_str(),
            "started_at": self.started_at.isoformat(),
            "wallbit": {
                "total_requests": self.wallbit_requests_total,
                "failed_requests": self.wallbit_requests_failed,
                "avg_latency_ms": self.get_avg_latency_ms(),
            },
            "jobs": {
                name: {
                    "runs": j.runs_count,
                    "errors": j.errors_count,
                    "last_run": j.last_run_at.isoformat() if j.last_run_at else None,
                    "last_status": j.last_status,
                }
                for name, j in self._jobs.items()
            },
            "db_size_mb": self.get_db_size_mb(),
        }

    def format_telegram_report(self) -> str:
        """Formatea las métricas para el comando /estado en Telegram."""
        uptime = self.get_uptime_str()
        avg_lat = self.get_avg_latency_ms()
        db_size = self.get_db_size_mb()
        trading_mode = "🟢 Real" if settings.TRADING_ENABLED else "🟡 Simulación"
        ai_mode = f"🟢 {settings.AI_PROVIDER}" if settings.AI_ENABLED else "🔴 Desactivada"

        lines = [
            "📈 <b>Estado del Sistema y Métricas</b>",
            "",
            f"⏱ <b>Uptime:</b> <code>{uptime}</code>",
            f"💱 <b>Trading:</b> {trading_mode}",
            f"🤖 <b>IA Advisor:</b> {ai_mode}",
            f"💾 <b>Base de datos:</b> <code>{db_size} MB</code>",
            "",
            "🌐 <b>API Wallbit:</b>",
            f"  • Peticiones: <code>{self.wallbit_requests_total}</code> (fallos: <code>{self.wallbit_requests_failed}</code>)",
            f"  • Latencia media: <code>{avg_lat} ms</code>",
            "",
            "⚙️ <b>Tareas en segundo plano:</b>",
        ]

        if not self._jobs:
            lines.append("  <i>Sin ejecuciones registradas aún</i>")
        else:
            for name, j in sorted(self._jobs.items()):
                icon = "✅" if j.last_status == "OK" else "❌"
                last_time = j.last_run_at.strftime("%H:%M:%S UTC") if j.last_run_at else "nunca"
                lines.append(
                    f"  {icon} <b>{name}</b>: {j.runs_count} runs "
                    f"({j.errors_count} errs) · Últ: <code>{last_time}</code>"
                )

        return "\n".join(lines)


# Instancia singleton global
metrics = MetricsCollector()
