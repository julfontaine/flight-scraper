from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from flight_scraper.config import WatchList
from flight_scraper.models import Itinerary, Leg, PaxConfig, SearchQuery

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def watchlist() -> WatchList:
    return WatchList.load()


@pytest.fixture
def query_yul_cdg() -> SearchQuery:
    """The research golden query: YUL-CDG 2026-10-15/22, 2 adults + 1 child."""
    return SearchQuery(
        source_id="google_flights",
        origin="YUL",
        destination="CDG",
        depart_date=date(2026, 10, 15),
        return_date=date(2026, 10, 22),
        offset_days=60,
        pax=PaxConfig(key="2a1c", adults=2, children=1),
    )


def make_it(
    price: float | None,
    duration: int | None,
    stops: int = 0,
    source: str = "best_load",
    idx: int = 0,
    airlines: list[str] | None = None,
    depart: datetime | None = None,
    **raw,
) -> Itinerary:
    return Itinerary(
        outbound=Leg(
            duration_min=duration,
            stops=stops,
            airlines=airlines or ["Air Canada"],
            depart_local=depart or datetime(2026, 10, 15, 8, 0),
            arrive_local=datetime(2026, 10, 15, 8, 0) + timedelta(minutes=duration or 0),
        ),
        airlines=airlines or ["Air Canada"],
        duration_min=duration,
        stops=stops,
        price_results_cad=price,
        candidate_source=source,
        row_index=idx,
        raw=dict(raw),
    )


# ------------------------------------------------------------------ fake adapter (no browser)
def fake_google_picks(query: SearchQuery) -> dict:
    """Three picks the way the live adapter would return them (booking stage), without a browser."""
    from flight_scraper.models import Pick, PriceStage, Provider

    out = {}
    for pick, price, dur in (
        (Pick.BEST, 900.0, 600),
        (Pick.CHEAPEST, 700.0, 900),
        (Pick.FASTEST, 1200.0, 420),
    ):
        it = make_it(price, dur, source=f"{pick.value}_load")
        it.price_total_cad = price
        it.price_provider = "Air Canada"
        it.price_stage = PriceStage.BOOKING
        it.providers = [Provider(name="Air Canada", total_cad=price, is_airline=True)]
        it.carry_on_included = True
        it.checked_bag_fee_cad = 70.0
        it.luggage_source = "google_booking_page"
        it.deep_link_url = "https://www.google.com/travel/flights/booking?tfs=FAKE"
        out[pick] = it
    return out


class FakeGoogleAdapter:
    """Drop-in for REGISTRY['google_flights'] in CLI/runner tests: 9 page loads, three booking-stage picks."""

    source_id = "google_flights"
    name = "Google Flights (fake)"
    kind = "meta"
    enabled = True
    disabled_reason = None
    priority = 1
    loads_per_search = 9
    fail_with: Exception | None = None

    def __init__(self, settings=None, budget_cfg=None, budget=None, sleeper=None, artifacts=None):
        self.budget = budget
        self.calls: list[SearchQuery] = []

    def build_url(self, query: SearchQuery, variant=None) -> str:
        return f"https://www.google.com/travel/flights/search?tfs=FAKE&route={query.route_key}"

    def run_search(self, page, query: SearchQuery):
        from flight_scraper.models import SearchResult

        self.calls.append(query)
        if self.budget is not None:
            self.budget.consume(self.loads_per_search)
        if self.fail_with is not None:
            raise self.fail_with
        return SearchResult(
            query=query,
            status="ok",
            picks=fake_google_picks(query),
            candidates=20,
            page_url=self.build_url(query),
            page_loads=self.loads_per_search,
        )
