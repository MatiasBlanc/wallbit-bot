"""Datetime and DCA scheduling calculation utilities."""

import calendar
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.constants import DCA_FREQ_MONTHLY, DCA_FREQ_WEEKLY


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


MONTH_NAMES_ES_SHORT = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
}


def get_now(timezone_str: str = "UTC") -> datetime:
    """Get current datetime in the specified timezone."""
    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def format_date_es(dt: datetime | None) -> str:
    """Format datetime as e.g. '03 Sep 2026'."""
    if not dt:
        return "N/D"
    month_name = MONTH_NAMES_ES_SHORT.get(dt.month, str(dt.month))
    return f"{dt.day:02d} {month_name} {dt.year}"


def format_date_short(dt: datetime | None) -> str:
    """Format datetime as e.g. '7 Sep' or '1 Oct'."""
    if not dt:
        return "N/D"
    month_name = MONTH_NAMES_ES_SHORT.get(dt.month, str(dt.month))
    return f"{dt.day} {month_name}"


def get_next_weekly_execution(weekday: int, target_time: time, tz_name: str, after: datetime | None = None) -> datetime:
    """
    Calculate the next occurrence of a weekly execution on given weekday (0=Monday...6=Sunday)
    at target_time in tz_name timezone, strictly after `after` (defaults to now).
    """
    tz = ZoneInfo(tz_name)
    now_tz = (after or datetime.now(tz)).astimezone(tz)

    # Start checking from today's target time
    candidate = datetime.combine(now_tz.date(), target_time, tzinfo=tz)

    days_ahead = (weekday - now_tz.weekday()) % 7
    if days_ahead == 0 and candidate <= now_tz:
        days_ahead = 7

    candidate = candidate + timedelta(days=days_ahead)
    return candidate


def get_next_monthly_execution(day_of_month: int, target_time: time, tz_name: str, after: datetime | None = None) -> datetime:
    """
    Calculate the next occurrence of a monthly execution on given day_of_month (1..31)
    at target_time in tz_name timezone, strictly after `after` (defaults to now).
    Clamps day_of_month to the maximum days in that month (e.g. Feb 28/29).
    """
    tz = ZoneInfo(tz_name)
    now_tz = (after or datetime.now(tz)).astimezone(tz)

    year = now_tz.year
    month = now_tz.month

    # Clamp day for current month
    _, max_days = calendar.monthrange(year, month)
    clamped_day = min(day_of_month, max_days)
    candidate = datetime.combine(date(year, month, clamped_day), target_time, tzinfo=tz)

    if candidate <= now_tz:
        # Move to next month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        _, max_days = calendar.monthrange(year, month)
        clamped_day = min(day_of_month, max_days)
        candidate = datetime.combine(date(year, month, clamped_day), target_time, tzinfo=tz)

    return candidate


def calculate_next_dca_execution(
    frequency: str,
    weekday: int | None,
    day_of_month: int | None,
    tz_name: str,
    report_time_str: str = "09:00",
    after: datetime | None = None
) -> datetime:
    """
    Calculate next execution datetime for a DCA rule.
    Executions are scheduled at the user's configured morning time (default 09:00).
    """
    try:
        parts = report_time_str.split(":")
        target_time = time(int(parts[0]), int(parts[1]))
    except Exception:
        target_time = time(9, 0)

    if frequency == DCA_FREQ_WEEKLY:
        wd = weekday if weekday is not None else 0
        return get_next_weekly_execution(wd, target_time, tz_name, after=after)
    elif frequency == DCA_FREQ_MONTHLY:
        dom = day_of_month if day_of_month is not None else 1
        return get_next_monthly_execution(dom, target_time, tz_name, after=after)
    else:
        raise ValueError(f"Unsupported frequency: {frequency}")
