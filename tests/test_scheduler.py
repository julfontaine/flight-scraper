from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flight_scraper.config import CellFilters, WatchList, expand_cells
from flight_scraper.scheduler import FileRotationState, MemoryRotationState, explain_plan, plan_run


def test_cold_start_caps_by_budget(watchlist: WatchList):
    cells = expand_cells(watchlist)
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    queries = plan_run(cells, MemoryRotationState(), watchlist.budget, now, defaults=watchlist.defaults)
    assert len(queries) == 4  # floor(40 / 9)
    assert [q.pax.key for q in queries] == ["1a"] * 4  # highest priority first on a cold start
    assert all(q.offset_days in (30, 60, 90) for q in queries)
    assert all(q.depart_date.weekday() == 5 for q in queries)


def test_steady_state_60_days_every_cell_scraped_and_weighted(watchlist: WatchList):
    cells = expand_cells(watchlist)
    state = MemoryRotationState()
    start = datetime(2026, 9, 4, 10, tzinfo=UTC)
    counts: Counter[str] = Counter()
    for day in range(60):
        now = start + timedelta(days=day)
        for q in plan_run(cells, state, watchlist.budget, now, defaults=watchlist.defaults, limit=5):
            state.mark(q.cell_key, True, now)
            counts[q.pax.key] += 1
    assert all(state.last_ok_at(c.key) is not None for c in cells), (
        "every cell must be scraped within 60 days"
    )
    assert counts["1a"] > counts["2a"] > counts["1a1c"]
    assert abs(counts["1a1c"] - counts["1a2c"]) <= 6


def test_filters_narrow_before_ranking(watchlist: WatchList):
    cells = expand_cells(watchlist)
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    q = plan_run(
        cells,
        MemoryRotationState(),
        watchlist.budget,
        now,
        CellFilters(route="YUL-CDG", pax="1a"),
        watchlist.defaults,
    )
    assert [x.route_key for x in q] == ["YUL-CDG"] * 3 and {x.offset_days for x in q} == {30, 60, 90}
    q = plan_run(
        cells,
        MemoryRotationState(),
        watchlist.budget,
        now,
        CellFilters(route="YUL-CDG", pax="1a", offset=60),
        watchlist.defaults,
    )
    assert len(q) == 1 and q[0].offset_days == 60
    assert plan_run(cells, MemoryRotationState(), watchlist.budget, now, CellFilters(source="nope")) == []


def test_file_state_round_trip_and_blocked(tmp_path: Path, watchlist: WatchList):
    path = tmp_path / "rotation_state.json"
    state = FileRotationState(path)
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    state.mark("google_flights:YUL-CDG:+60:1a", True, now)
    state.mark("google_flights:YUL-CDG:+30:1a", False, now, blocked=True)
    assert path.exists() and not path.with_suffix(".json.tmp").exists()
    data = json.loads(path.read_text())
    assert data["cells"]["google_flights:YUL-CDG:+60:1a"]["last_ok_at"].startswith("2026-09-04T10:00")
    reloaded = FileRotationState(path)
    assert reloaded.last_ok_at("google_flights:YUL-CDG:+60:1a") == now
    assert reloaded.blocked_recently("google_flights:YUL-CDG:+30:1a", now + timedelta(hours=5))
    assert not reloaded.blocked_recently("google_flights:YUL-CDG:+30:1a", now + timedelta(days=3))
    # blocked cell is skipped for the next run
    cells = expand_cells(watchlist)
    q = plan_run(
        cells,
        reloaded,
        watchlist.budget,
        now + timedelta(hours=1),
        CellFilters(route="YUL-CDG", pax="1a"),
        watchlist.defaults,
    )
    assert {x.offset_days for x in q} == {60, 90}


def test_corrupt_state_file_starts_empty(tmp_path: Path):
    path = tmp_path / "rotation_state.json"
    path.write_text("{not json")
    assert FileRotationState(path).last_ok_at("x") is None


def test_explain(watchlist: WatchList):
    cells = expand_cells(watchlist)
    rows = explain_plan(cells, MemoryRotationState(), watchlist.budget, datetime(2026, 9, 4, tzinfo=UTC))
    assert len(rows) == 144 and rows[0]["selected"] and not rows[10]["selected"] and rows[0]["never_scraped"]
