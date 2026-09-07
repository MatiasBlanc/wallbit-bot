"""Formateadores de dominio para la interfaz de Telegram."""

from datetime import datetime, timezone

from app.shared.datetime import format_date_es
from app.shared.formatting.currency import format_currency, format_quantity, format_usd
from app.shared.formatting.percentage import format_percentage


def format_money(amount: float | None, currency: str = "USD") -> str:
    """Formatea dinero con la convención de la moneda indicada."""
    return format_currency(amount, currency)


def format_position(ticker: str, value: float | None, roi_pct: float | None = None) -> str:
    """Formatea una posición sin inventar rentabilidad ausente."""
    result = f"{ticker} · {format_usd(value)}"
    if roi_pct is not None:
        result += f" · {format_percentage(roi_pct)}"
    return result


def format_balance(amount: float | None, currency: str = "USD") -> str:
    """Formatea un saldo para una línea de resumen."""
    return format_money(amount, currency)


def format_date(value: datetime | None) -> str:
    """Formatea una fecha usando el idioma del bot."""
    return format_date_es(value)


def format_relative_date(value: datetime | None) -> str:
    """Muestra una fecha relativa corta para datos recientes."""
    if value is None:
        return "N/D"
    now = datetime.now(timezone.utc)
    current = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    hours = max(0, int((now - current.astimezone(timezone.utc)).total_seconds() // 3600))
    if hours < 1:
        return "hace unos minutos"
    if hours < 24:
        return f"hace {hours} h"
    days = hours // 24
    if days == 1:
        return "ayer"
    if days < 7:
        return f"hace {days} días"
    return format_date(current)


__all__ = [
    "format_balance",
    "format_date",
    "format_money",
    "format_percentage",
    "format_position",
    "format_quantity",
    "format_relative_date",
    "format_usd",
]
