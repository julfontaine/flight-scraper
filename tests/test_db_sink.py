"""SupabaseSink / SupabaseRotationState against a recording fake client (no network)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from flight_scraper.config import Settings, WatchList
from flight_scraper.db import (
    ITINERARY_ON_CONFLICT,
    SEARCH_ON_CONFLICT,
    DryRunSink,
    RunInfo,
    SupabaseRotationState,
    SupabaseSink,
    itinerary_rows,
)
from flight_scraper.models import PaxConfig, SearchQuery, SearchResult
from flight_scraper.pacing import PageLoadBudget
from flight_scraper.runner import Runner
from flight_scraper.scheduler import FileRotationState
from tests.conftest import FakeGoogleAdapter, fake_google_picks


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Minimal PostgREST-builder look-alike recording upsert/insert/update/select calls."""

    def __init__(self, fake: FakeSupabase, table: str):
        self.fake, self.table, self.op, self.payload, self.kwargs, self.filters = (
            fake,
            table,
            None,
            None,
            {},
            [],
        )

    def upsert(self, rows, **kwargs):
        self.op, self.payload, self.kwargs = "upsert", rows, kwargs
        return self

    def insert(self, rows, **kwargs):
        self.op, self.payload, self.kwargs = "insert", rows, kwargs
        return self

    def update(self, rows, **kwargs):
        self.op, self.payload, self.kwargs = "update", rows, kwargs
        return self

    def select(self, *cols):
        self.op, self.payload = "select", cols
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def execute(self):
        self.fake.calls.append((self.table, self.op, self.payload, self.kwargs, list(self.filters)))
        return self.fake.respond(self)


class FakeSupabase:
    def __init__(self, fail_on: str | None = None):
        self.calls: list[tuple] = []
        self.searches: dict[tuple, int] = {}  # natural key -> id
        self.itineraries: dict[tuple[int, str], dict] = {}
        self.routes = {("YUL", "CDG"): 5, ("YQB", "CDG"): 6}
        self.cells: list[dict] = []
        self.fail_on = fail_on

    def table(self, name):
        return _Query(self, name)

    def respond(self, q: _Query):
        if self.fail_on and q.table == self.fail_on:
            raise ConnectionError(f"{q.table} unavailable")
        if q.table == "routes" and q.op == "select":
            rows = [{"id": i, "origin": o, "destination": d} for (o, d), i in self.routes.items()]
            for col, val in q.filters:
                rows = [r for r in rows if r[col] == val]
            return _Resp(rows)
        if q.table == "routes" and q.op == "upsert":
            key = (q.payload["origin"], q.payload["destination"])
            self.routes.setdefault(key, max(self.routes.values()) + 1)
            return _Resp([])
        if q.table == "searches" and q.op == "upsert":
            r = q.payload
            key = tuple(r[c] if c != "child_ages" else tuple(r[c]) for c in SEARCH_ON_CONFLICT.split(","))
            sid = self.searches.setdefault(key, len(self.searches) + 1)
            return _Resp([{"id": sid, **r}])
        if q.table == "itineraries" and q.op == "upsert":
            for r in q.payload:
                self.itineraries[(r["search_id"], r["pick"])] = r
            return _Resp([])
        if q.table == "cell_last_scraped":
            return _Resp([c for c in self.cells if all(c.get(k) == v for k, v in q.filters)])
        return _Resp([])


def _result(status="ok") -> SearchResult:
    q = SearchQuery(
        source_id="google_flights",
        origin="YUL",
        destination="CDG",
        depart_date=date(2026, 11, 7),
        return_date=date(2026, 11, 14),
        offset_days=60,
        pax=PaxConfig(key="1a", adults=1),
    )
    return SearchResult(
        query=q,
        status=status,
        picks=fake_google_picks(q),
        candidates=20,
        page_url="https://g/results",
        page_loads=9,
        started_at=datetime(2026, 9, 6, 10, tzinfo=UTC),
        finished_at=datetime(2026, 9, 6, 10, 2, tzinfo=UTC),
    )


def _run() -> RunInfo:
    return RunInfo(
        run_id="11111111-1111-1111-1111-111111111111",
        started_at=datetime(2026, 9, 6, 10, tzinfo=UTC),
        scrape_date=date(2026, 9, 6),
        git_sha="abc123",
        host="wsl",
        searches_total=1,
    )


def test_upsert_strings_and_same_day_rewrite_reuses_search_id(tmp_path: Path):
    fake = FakeSupabase()
    sink = SupabaseSink(fake, companion=DryRunSink(tmp_path / "out"))
    sink.start_run(_run())
    sid1 = sink.write_search(_result())
    sid2 = sink.write_search(_result())
    assert sid1 == sid2 == 1 and len(fake.searches) == 1
    search_upserts = [c for c in fake.calls if c[0] == "searches" and c[1] == "upsert"]
    assert len(search_upserts) == 2
    assert all(
        c[3] == {"on_conflict": SEARCH_ON_CONFLICT, "returning": "representation"} for c in search_upserts
    )
    it_upserts = [c for c in fake.calls if c[0] == "itineraries"]
    assert len(it_upserts) == 2 and all(len(c[2]) == 3 for c in it_upserts)
    assert all(c[3] == {"on_conflict": ITINERARY_ON_CONFLICT, "returning": "minimal"} for c in it_upserts)
    assert len(fake.itineraries) == 3  # upserts, not inserts
    row = fake.searches and search_upserts[0][2]
    assert row["child_ages"] == [] and row["scrape_date"] == "2026-09-06" and row["route_id"] == 5
    assert row["depart_date"] == "2026-11-07" and row["adults"] == 1 and row["children"] == 0
    run = _run()
    run.status, run.finished_at, run.page_loads, run.searches_ok = (
        "ok",
        datetime(2026, 9, 6, 11, tzinfo=UTC),
        18,
        1,
    )
    sink.finish_run(run)
    upd = [c for c in fake.calls if c[0] == "search_runs" and c[1] == "update"][0]
    assert upd[2]["status"] == "ok" and upd[2]["page_loads"] == 18 and upd[4] == [("run_id", run.run_id)]
    assert (tmp_path / "out" / f"{run.run_id}.json").exists()  # companion JSON always written


def test_itinerary_rows_carry_every_contract_field():
    rows = itinerary_rows(_result(), 42)
    best = next(r for r in rows if r["pick"] == "best")
    assert best["search_id"] == 42 and best["price_stage"] == "booking" and best["price_total_cad"] == 900.0
    assert best["carry_on_included"] is True and best["checked_bag_fee_cad"] == 70.0
    assert best["luggage_source"] == "google_booking_page" and "/booking" in best["deep_link_url"]
    assert best["outbound_depart_local"] == "2026-10-15T08:00:00" and best["duration_min"] == 600
    assert best["raw"]["providers"][0]["name"] == "Air Canada" and best["pick_rule"] == "native"
    assert {r["pick"] for r in rows} == {"best", "cheapest", "fastest"}


def test_unknown_route_is_created_on_the_fly(tmp_path: Path):
    fake = FakeSupabase()
    sink = SupabaseSink(fake)
    sink.start_run(_run())
    r = _result()
    r.query.destination = "LHR"
    sink.write_search(r)
    assert ("YUL", "LHR") in fake.routes
    assert [c for c in fake.calls if c[0] == "routes" and c[1] == "upsert"]


def test_db_error_is_logged_run_continues_and_json_is_written(tmp_path: Path, watchlist: WatchList):
    fake = FakeSupabase(fail_on="searches")
    settings = Settings(out_dir=tmp_path / "out")
    sink = SupabaseSink(fake, companion=DryRunSink(settings.out_dir))
    runner = Runner(
        settings,
        watchlist,
        sink,
        FileRotationState(settings.out_dir / "rotation_state.json"),
        dry_run=False,
        page_budget=PageLoadBudget(40),
        adapters={"google_flights": FakeGoogleAdapter},
        now=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    )
    from flight_scraper.config import expand_cells

    q = expand_cells(watchlist)[0].to_query(date(2026, 9, 6), watchlist.defaults)
    report = runner.run([q])
    assert report.results[0].status == "ok" and "sink error" in (report.run.notes or "")
    files = [f for f in (tmp_path / "out").glob("*.json") if f.name != "rotation_state.json"]
    assert len(files) == 1


def test_rotation_state_from_view_and_blocked_skip():
    fake = FakeSupabase()

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
        cell("YUL", "CDG", 60, 1, "2026-09-01T10:00:00+00:00", False),
        cell("YUL", "CDG", 30, 1, None, True),
        cell("YQB", "CDG", None, 1, "2026-09-02T10:00:00Z", False),
        cell("YUL", "CDG", 90, 4, "2026-09-02T10:00:00Z", False),
    ]
    state = SupabaseRotationState(fake, ["google_flights"], {(1, 0): "1a", (2, 0): "2a"})
    assert state.last_ok_at("google_flights:YUL-CDG:+60:1a") == datetime(2026, 9, 1, 10, tzinfo=UTC)
    assert state.last_ok_at("google_flights:YUL-CDG:+30:1a") is None
    assert state.blocked_recently("google_flights:YUL-CDG:+30:1a")
    assert not state.blocked_recently("google_flights:YUL-CDG:+60:1a")
    assert len(state.ok) == 1  # ad-hoc (offset None) and unknown pax rows are ignored
    state.mark("google_flights:YUL-CDG:+90:1a", True, datetime(2026, 9, 6, tzinfo=UTC))
    assert state.last_ok_at("google_flights:YUL-CDG:+90:1a")


def test_from_settings_requires_credentials():
    with pytest.raises(RuntimeError):
        SupabaseSink.from_settings(Settings())
