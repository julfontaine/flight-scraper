"""PostgresSink / PostgresRotationState / PostgresBackend against a recording fake psycopg connection."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from flight_scraper.config import Settings
from flight_scraper.db import (
    ITINERARY_ON_CONFLICT,
    SEARCH_ON_CONFLICT,
    DryRunSink,
    PostgresBackend,
    PostgresRotationState,
    PostgresSink,
    upsert_sql,
)
from tests.test_db_sink import _result, _run


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class FakePg:
    """Records every ``execute(sql, params)`` and answers by matching the SQL text."""

    def __init__(self, fail_on: str | None = None):
        self.calls: list[tuple[str, tuple | None]] = []
        self.routes = {("YUL", "CDG"): 5, ("YQB", "CDG"): 6}
        self.searches: dict[tuple, int] = {}
        self.itineraries: dict[tuple[int, str], tuple] = {}
        self.runs: dict[str, dict] = {}
        self.cells: list[dict] = []
        self.fail_on = fail_on
        self.closed = False

    def execute(self, sql: str, params=None):
        self.calls.append((sql, params))
        head = " ".join(sql.split()).lower()
        if self.fail_on and self.fail_on in head:
            raise ConnectionError(f"{self.fail_on} unavailable")
        if head.startswith("select id from routes") or head.startswith(
            "select id, origin, destination from routes"
        ):
            rows = [{"id": i, "origin": o, "destination": d} for (o, d), i in self.routes.items()]
            if params:
                rows = [r for r in rows if (r["origin"], r["destination"]) == tuple(params)]
            return _Cursor(rows)
        if head.startswith("insert into routes"):
            self.routes.setdefault(tuple(params), max(self.routes.values()) + 1)
            return _Cursor([])
        if head.startswith("insert into search_runs"):
            self.runs[params[0]] = {"status": "running"}
            return _Cursor([])
        if head.startswith("update search_runs"):
            self.runs[params[-1]]["status"] = params[1]
            return _Cursor([])
        if head.startswith("insert into searches"):
            cols = _columns(sql)
            row = dict(zip(cols, params, strict=True))
            key = tuple(tuple(row[c]) if c == "child_ages" else row[c] for c in SEARCH_ON_CONFLICT.split(","))
            sid = self.searches.setdefault(key, len(self.searches) + 1)
            return _Cursor([{"id": sid}])
        if head.startswith("insert into itineraries"):
            cols = _columns(sql)
            row = dict(zip(cols, params, strict=True))
            self.itineraries[(row["search_id"], row["pick"])] = params
            return _Cursor([])
        if "from cell_last_scraped" in head:
            return _Cursor([c for c in self.cells if c["source_id"] == params[0]])
        if "from search_runs" in head:
            return _Cursor([])
        if head.startswith("select count(*)"):
            return _Cursor([{"n": 7}])
        return _Cursor([])

    def close(self):
        self.closed = True


def _columns(sql: str) -> list[str]:
    m = re.search(r"\(([^)]*)\)\s*values", sql, re.IGNORECASE | re.DOTALL)
    assert m, sql
    return [c.strip() for c in m.group(1).split(",")]


def test_upsert_sql_shape():
    sql = upsert_sql("searches", ["a", "b", "c"], ["a", "b"], {"c": "date"}, returning="id")
    flat = " ".join(sql.split())
    assert flat == (
        "insert into searches (a, b, c) values (%s, %s, %s::date) "
        "on conflict (a, b) do update set c = excluded.c returning id"
    )
    # every conflict column also in the update list would be a bug: nothing to update → do nothing
    sql = upsert_sql("routes", ["origin", "destination"], ["origin", "destination"], {})
    assert " ".join(sql.split()).endswith("on conflict (origin, destination) do nothing")


def test_write_search_upserts_and_returns_id(tmp_path: Path):
    fake = FakePg()
    sink = PostgresSink(fake, companion=DryRunSink(tmp_path / "out"))
    sink.start_run(_run())
    sid1 = sink.write_search(_result())
    sid2 = sink.write_search(_result())
    assert sid1 == sid2 == 1
    assert len(fake.itineraries) == 3 and {p for _, p in fake.itineraries} == {"best", "cheapest", "fastest"}
    search_sql = next(s for s, _ in fake.calls if s.lower().lstrip().startswith("insert into searches"))
    assert f"on conflict ({', '.join(SEARCH_ON_CONFLICT.split(','))})" in " ".join(search_sql.split())
    assert "returning id" in search_sql
    it_sql = next(s for s, _ in fake.calls if s.lower().lstrip().startswith("insert into itineraries"))
    assert f"on conflict ({', '.join(ITINERARY_ON_CONFLICT.split(','))})" in " ".join(it_sql.split())
    # raw travels as a JSON string cast to jsonb, never as a Python dict
    cols = _columns(it_sql)
    raw = next(p for p in fake.itineraries.values())[cols.index("raw")]
    assert isinstance(raw, str) and json.loads(raw)["providers"][0]["name"] == "Air Canada"
    assert "%s::jsonb" in it_sql and "%s::smallint[]" in search_sql
    run = _run()
    run.status, run.finished_at = "ok", datetime(2026, 9, 6, 11, tzinfo=UTC)
    sink.finish_run(run)
    assert fake.runs[run.run_id]["status"] == "ok"
    files = [f for f in (tmp_path / "out").glob("*.json") if f.name != "rotation_state.json"]
    assert len(files) == 1  # companion JSON still written


def test_unknown_route_is_created_on_the_fly():
    fake = FakePg()
    sink = PostgresSink(fake)
    sink.start_run(_run())
    r = _result()
    r.query.destination = "LHR"
    sink.write_search(r)
    assert ("YUL", "LHR") in fake.routes


def test_rotation_state_from_view_and_blocked_skip():
    fake = FakePg()

    def cell(origin, dest, offset, adults, last_ok, blocked):
        return {
            "source_id": "google_flights",
            "origin": origin,
            "destination": dest,
            "offset_days": offset,
            "adults": adults,
            "children": 0,
            "cabin": "economy",
            "last_ok_at": last_ok,
            "blocked_recently": blocked,
        }

    fake.cells = [
        cell("YUL", "CDG", 60, 1, datetime(2026, 9, 1, 10, tzinfo=UTC), False),  # psycopg gives datetimes
        cell("YUL", "CDG", 30, 1, None, True),
        cell("YQB", "CDG", None, 1, datetime(2026, 9, 2, 10, tzinfo=UTC), False),
        cell("YUL", "CDG", 90, 4, datetime(2026, 9, 2, 10, tzinfo=UTC), False),
    ]
    state = PostgresRotationState(fake, ["google_flights"], {(1, 0): "1a", (2, 0): "2a"})
    assert state.last_ok_at("google_flights:YUL-CDG:+60:1a") == datetime(2026, 9, 1, 10, tzinfo=UTC)
    assert state.blocked_recently("google_flights:YUL-CDG:+30:1a")
    assert not state.blocked_recently("google_flights:YUL-CDG:+60:1a")
    assert len(state.ok) == 1


def test_backend_counts_and_runs():
    fake = FakePg()
    backend = PostgresBackend(fake, Settings(database_url="postgres://u:p@h/db"))
    assert backend.label == "postgres://u@h/db"
    assert backend.counts(["sources", "routes"]) == {"sources": 7, "routes": 7}
    assert backend.recent_runs(3) == [] and backend.last_run() is None


def test_from_settings_requires_database_url():
    with pytest.raises(RuntimeError):
        PostgresSink.from_settings(Settings())
