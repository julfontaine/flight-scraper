"""Opt-in live DB test: needs DATABASE_URL in .env and a database with the migration applied
(``just up`` starts one and applies it).

pytest -m live tests/live/test_postgres_live.py
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from flight_scraper.config import Settings
from flight_scraper.db import PostgresBackend, PostgresRotationState, PostgresSink, RunInfo
from flight_scraper.models import PaxConfig, SearchQuery, SearchResult
from tests.conftest import fake_google_picks

pytestmark = pytest.mark.live


def test_write_twice_yields_one_search_and_three_itineraries():
    settings = Settings.from_env()
    if not settings.has_postgres:
        pytest.skip("no DATABASE_URL in .env")
    sink = PostgresSink.from_settings(settings)
    conn = sink.conn
    run = RunInfo(run_id=str(uuid.uuid4()), started_at=datetime.now(UTC), scrape_date=date.today())
    sink.start_run(run)
    q = SearchQuery(
        source_id="google_flights",
        origin="YUL",
        destination="CDG",
        depart_date=date(2030, 1, 5),  # far future: never collides with real scrapes
        return_date=date(2030, 1, 12),
        offset_days=None,
        pax=PaxConfig(key="1a", adults=1),
    )
    result = SearchResult(query=q, status="ok", picks=fake_google_picks(q), candidates=3, page_loads=9,
                          started_at=datetime.now(UTC), finished_at=datetime.now(UTC))  # fmt: skip
    try:
        sid1 = sink.write_search(result)
        sid2 = sink.write_search(result)
        assert sid1 == sid2
        run.status, run.finished_at = "ok", datetime.now(UTC)
        sink.finish_run(run)
        rows = conn.execute("select pick, raw from itineraries where search_id = %s", (sid1,)).fetchall()
        assert sorted(r["pick"] for r in rows) == ["best", "cheapest", "fastest"]
        assert all(isinstance(r["raw"], dict) and r["raw"]["providers"] for r in rows)  # jsonb round-trip
        latest = conn.execute(
            "select pick, price_total_cad from latest_prices where search_id = %s", (sid1,)
        ).fetchall()
        assert len(latest) == 3 and all(r["price_total_cad"] is not None for r in latest)
        backend = PostgresBackend(conn, settings)
        last, searches = backend.last_run()
        assert str(last["run_id"]) == run.run_id and last["status"] == "ok" and len(searches) == 1
        assert backend.counts(["sources", "routes"])["sources"] == 9
        # ad-hoc search (offset None) is not a rotation cell → state stays empty for it
        state = PostgresRotationState(conn, ["google_flights"], {(1, 0): "1a"})
        assert state.last_ok_at("google_flights:YUL-CDG:+None:1a") is None
    finally:
        conn.execute("delete from search_runs where run_id = %s::uuid", (run.run_id,))  # cascades
        conn.close()
