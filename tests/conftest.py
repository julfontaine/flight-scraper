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
