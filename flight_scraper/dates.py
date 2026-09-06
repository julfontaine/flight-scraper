"""Relative-date resolution for the watch-list (pure functions)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

RUN_TZ = ZoneInfo("America/Toronto")
SATURDAY = 5  # date.weekday(): Monday = 0


def run_local_date(now: datetime | None = None) -> date:
    """The scraper's notion of 'today' (America/Toronto), used for scrape_date and date resolution."""
    now = now or datetime.now(tz=RUN_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=RUN_TZ)
    return now.astimezone(RUN_TZ).date()


def next_saturday_on_or_after(d: date) -> date:
    return d + timedelta(days=(SATURDAY - d.weekday()) % 7)


def resolve_dates(
    run_date: date, offset_days: int, stay_nights: int, rule: str = "next_saturday"
) -> tuple[date, date]:
    """depart = first Saturday on/after run_date + offset_days (next_saturday); return = depart + stay."""
    if offset_days <= 0:
        raise ValueError("offset_days must be > 0")
    if stay_nights <= 0:
        raise ValueError("stay_nights must be > 0")
    anchor = run_date + timedelta(days=offset_days)
    if rule == "next_saturday":
        depart = next_saturday_on_or_after(anchor)
    elif rule == "exact":
        depart = anchor
    else:
        raise ValueError(f"unknown date_rule {rule!r}")
    return depart, depart + timedelta(days=stay_nights)
