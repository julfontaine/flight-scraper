"""Opt-in live DB test: needs .env with SUPABASE_URL / SUPABASE_SERVICE_KEY and the migration applied.

pytest -m live tests/live/test_supabase_live.py
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from flight_scraper.config import Settings
from flight_scraper.db import RunInfo, SupabaseSink
from flight_scraper.models import PaxConfig, SearchQuery, SearchResult
from tests.conftest import fake_google_picks

pytestmark = pytest.mark.live


def test_write_twice_yields_one_search_and_three_itineraries():
    settings = Settings.from_env()
    if not settings.has_supabase:
        pytest.skip("no Supabase credentials in .env")
    sink = SupabaseSink.from_settings(settings)
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
    sid1 = sink.write_search(result)
    sid2 = sink.write_search(result)
    assert sid1 == sid2
    run.status, run.finished_at = "ok", datetime.now(UTC)
    sink.finish_run(run)
    client = sink.client
    rows = client.table("itineraries").select("pick").eq("search_id", sid1).execute().data
    assert sorted(r["pick"] for r in rows) == ["best", "cheapest", "fastest"]
    latest = client.table("latest_prices").select("pick,price_total_cad").eq("search_id", sid1).execute().data
    assert len(latest) == 3
    # cleanup: cascade from search_runs
    client.table("search_runs").delete().eq("run_id", run.run_id).execute()
