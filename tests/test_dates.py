from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from flight_scraper.dates import next_saturday_on_or_after, resolve_dates, run_local_date


@pytest.mark.parametrize(
    "run_date",
    [date(2026, 9, 5), date(2026, 9, 4), date(2026, 9, 6)],  # Saturday, Friday, Sunday
)
@pytest.mark.parametrize("offset", [30, 60, 90])
def test_resolve_next_saturday(run_date: date, offset: int):
    depart, ret = resolve_dates(run_date, offset, 7)
    assert depart.weekday() == 5
    assert ret - depart == timedelta(days=7)
    assert ret.weekday() == 5
    anchor = run_date + timedelta(days=offset)
    assert anchor <= depart < anchor + timedelta(days=7)


def test_saturday_anchor_stays_on_saturday():
    # 2026-09-05 is a Saturday; +28 days is also a Saturday → depart is exactly the anchor
    assert resolve_dates(date(2026, 9, 5), 28, 7) == (date(2026, 10, 3), date(2026, 10, 10))


def test_year_rollover():
    depart, ret = resolve_dates(date(2026, 12, 1), 30, 7)
    assert depart == date(2027, 1, 2) and ret == date(2027, 1, 9)


def test_consecutive_runs_share_dates_for_a_week():
    dates = {resolve_dates(date(2026, 9, 4) + timedelta(days=i), 30, 7) for i in range(7)}  # anchors Sun..Sat
    assert len(dates) == 1


def test_exact_rule_and_validation():
    assert resolve_dates(date(2026, 9, 4), 30, 7, rule="exact") == (date(2026, 10, 4), date(2026, 10, 11))
    with pytest.raises(ValueError):
        resolve_dates(date(2026, 9, 4), 0, 7)
    with pytest.raises(ValueError):
        resolve_dates(date(2026, 9, 4), 30, 7, rule="whenever")
    assert next_saturday_on_or_after(date(2026, 9, 5)) == date(2026, 9, 5)


def test_run_local_date_uses_toronto():
    # 03:30 UTC on Sept 5 is still Sept 4 in Toronto (EDT, UTC-4)
    assert run_local_date(datetime(2026, 9, 5, 3, 30, tzinfo=ZoneInfo("UTC"))) == date(2026, 9, 4)
    assert run_local_date(datetime(2026, 9, 5, 5, 30, tzinfo=ZoneInfo("UTC"))) == date(2026, 9, 5)
