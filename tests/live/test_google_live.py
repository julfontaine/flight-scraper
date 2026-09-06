"""Opt-in live smoke test: ``pytest -m live tests/live/test_google_live.py`` (hits Google, ≤ 9 page loads)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from flight_scraper.browser import BrowserArtifacts, open_context
from flight_scraper.config import Settings, WatchList, expand_cells
from flight_scraper.dates import run_local_date
from flight_scraper.db import DryRunSink
from flight_scraper.models import Pick, PriceStage
from flight_scraper.pacing import PageLoadBudget
from flight_scraper.runner import Runner
from flight_scraper.scheduler import FileRotationState

pytestmark = pytest.mark.live


def test_yul_cdg_1a_plus60_three_picks_with_booking_page(tmp_path: Path):
    settings = Settings.from_env()
    settings.out_dir, settings.artifacts_dir = tmp_path / "out", tmp_path / "artifacts"
    wl = WatchList.load()
    cell = next(
        c for c in expand_cells(wl) if c.route_key == "YUL-CDG" and c.pax.key == "1a" and c.offset_days == 60
    )
    query = cell.to_query(run_local_date(), wl.defaults)
    runner = Runner(
        settings,
        wl,
        DryRunSink(settings.out_dir),
        FileRotationState(settings.out_dir / "rotation_state.json"),
        page_budget=PageLoadBudget(wl.budget.est_page_loads_per_search),
        session_factory=lambda source_id: open_context(settings, source_id),
        artifacts=BrowserArtifacts(settings.artifacts_dir, "live-test"),
        now=lambda: datetime.now(UTC),
    )
    report = runner.run([query])
    result = report.results[0]
    assert result.status in ("ok", "partial"), result.error
    assert set(result.picks) == {Pick.BEST, Pick.CHEAPEST, Pick.FASTEST}
    assert result.page_loads <= wl.budget.est_page_loads_per_search
    best = result.picks[Pick.BEST]
    assert best.price_results_cad and best.price_results_cad > 0
    if best.price_stage is PriceStage.BOOKING:
        assert best.price_total_cad and best.price_total_cad > 0 and best.price_provider
        assert best.deep_link_url and "/travel/flights/booking" in best.deep_link_url
        assert best.luggage_source == "google_booking_page" or best.raw["booking"]["luggage_text"] == []
    else:
        assert best.raw.get("booking_error") or best.raw.get("booking_price_unavailable")
