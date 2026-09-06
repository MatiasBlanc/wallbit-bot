"""Tests for datetime and scheduling utilities."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.core.constants import DCA_FREQ_MONTHLY, DCA_FREQ_WEEKLY
from app.utils.datetime_utils import (
    calculate_next_dca_execution,
    format_date_es,
    format_date_short,
    get_next_monthly_execution,
    get_next_weekly_execution,
)


def test_format_date_es():
    dt = datetime(2026, 9, 3, 10, 30)
    assert format_date_es(dt) == "03 Sep 2026"
    assert format_date_es(None) == "N/D"


def test_format_date_short():
    dt = datetime(2026, 9, 7, 9, 0)
    assert format_date_short(dt) == "7 Sep"
    dt2 = datetime(2026, 10, 1, 9, 0)
    assert format_date_short(dt2) == "1 Oct"


def test_get_next_weekly_execution():
    tz_name = "America/Santiago"
    tz = ZoneInfo(tz_name)
    # Sunday 2026-09-06 at 12:00
    base_time = datetime(2026, 9, 6, 12, 0, tzinfo=tz)

    # Next Monday (weekday=0) at 09:00
    target_time = time(9, 0)
    next_exec = get_next_weekly_execution(0, target_time, tz_name, after=base_time)
    assert next_exec.weekday() == 0  # Monday
    assert next_exec.day == 7
    assert next_exec.month == 9
    assert next_exec.year == 2026
    assert next_exec.hour == 9
    assert next_exec.minute == 0


def test_get_next_monthly_execution():
    tz_name = "America/Santiago"
    tz = ZoneInfo(tz_name)
    # 2026-09-06 at 12:00
    base_time = datetime(2026, 9, 6, 12, 0, tzinfo=tz)

    # Day 15 of current month
    target_time = time(9, 0)
    next_exec = get_next_monthly_execution(15, target_time, tz_name, after=base_time)
    assert next_exec.day == 15
    assert next_exec.month == 9

    # Day 1 of next month (since day 1 of Sep is already past)
    next_exec_1 = get_next_monthly_execution(1, target_time, tz_name, after=base_time)
    assert next_exec_1.day == 1
    assert next_exec_1.month == 10


def test_calculate_next_dca_execution_weekly_and_monthly():
    tz_name = "America/Santiago"
    tz = ZoneInfo(tz_name)
    base_time = datetime(2026, 9, 6, 12, 0, tzinfo=tz)

    # Weekly Monday
    next_w = calculate_next_dca_execution(
        frequency=DCA_FREQ_WEEKLY,
        weekday=0,
        day_of_month=None,
        tz_name=tz_name,
        report_time_str="09:00",
        after=base_time,
    )
    assert next_w.weekday() == 0
    assert next_w.day == 7

    # Monthly 1st
    next_m = calculate_next_dca_execution(
        frequency=DCA_FREQ_MONTHLY,
        weekday=None,
        day_of_month=1,
        tz_name=tz_name,
        report_time_str="09:00",
        after=base_time,
    )
    assert next_m.day == 1
    assert next_m.month == 10
