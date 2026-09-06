"""Google Flights results-row parser: synthetic research sentence + captured fixtures (never hand-edited)."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from flight_scraper.adapters.google_flights.parse_results import (
    infer_year,
    parse_row_aria,
    rows_to_itineraries,
    split_carriers,
)
from flight_scraper.models import PaxConfig, SearchQuery
from flight_scraper.picks import select_picks
from tests.conftest import FIXTURES

YUL_CDG = FIXTURES / "google_flights" / "YUL-CDG"
RESEARCH_ROW = (
    "From 2173 Canadian dollars round trip total. 1 stop flight with Porter Airlines and Air Transat. "
    "Leaves Montréal-Pierre Elliott Trudeau International Airport at 5:00 PM on Thursday, October 15 and "
    "arrives at Paris Charles de Gaulle Airport at 9:30 AM on Friday, October 16. "
    "Total duration 11 hr 30 min. "
    "Layover (1 of 1) is a 2 hr 37 min layover at Toronto Pearson International Airport.   Select flight"
)


def load_query() -> SearchQuery:
    return SearchQuery.model_validate_json((YUL_CDG / "query.json").read_text(encoding="utf-8"))


def load_rows(name: str) -> list[str]:
    return json.loads((YUL_CDG / f"{name}_rows.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ synthetic
def test_research_sentence_parses_every_field():
    p = parse_row_aria(RESEARCH_ROW, date(2026, 10, 15))
    assert p is not None
    assert p.price == 2173.0 and p.currency_raw == "Canadian dollars"
    assert p.leg.stops == 1 and p.leg.airlines == ["Porter Airlines", "Air Transat"]
    assert p.leg.depart_local == datetime(2026, 10, 15, 17, 0)
    assert p.leg.arrive_local == datetime(2026, 10, 16, 9, 30)
    assert p.leg.duration_min == 690
    assert p.raw["layovers"] == [
        {"minutes": 157, "overnight": False, "airport": "Toronto Pearson International Airport"}
    ]
    assert "long_layover" not in p.raw and "unparsed" not in p.raw
    assert p.raw["depart_airport"].startswith("Montréal") and p.raw["arrive_airport"].startswith("Paris")


def test_long_overnight_layover_and_self_transfer_flags():
    text = (
        "From 1,050 Canadian dollars round trip total. "
        "2 stops flight with Flair Airlines, WestJet, and Condor. "
        "Leaves A at 11:45 PM on Friday, December 31 and arrives at B at 12:05 AM on Sunday, January 2. "
        "Total duration 24 hr 20 min. Layover (1 of 2) is a 5 hr 10 min overnight layover at C. "
        "Layover (2 of 2) is a 45 min layover at D. Self transfer required."
    )
    p = parse_row_aria(text, date(2026, 12, 20))
    assert p and p.price == 1050.0 and p.leg.stops == 2
    assert p.leg.airlines == ["Flair Airlines", "WestJet", "Condor"]
    assert p.leg.depart_local == datetime(2026, 12, 31, 23, 45)
    assert p.leg.arrive_local == datetime(2027, 1, 2, 0, 5)  # year rollover inferred
    assert p.leg.duration_min == 1460 and p.raw["long_layover"] and p.raw["self_transfer"]
    assert [lo["minutes"] for lo in p.raw["layovers"]] == [310, 45]


def test_unparseable_and_foreign_currency_rows_are_excluded():
    assert parse_row_aria("Select flight", date(2026, 10, 1)) is None
    p = parse_row_aria(
        "From 500 US dollars round trip total. Nonstop flight with X. Total duration 2 hr.", date(2026, 10, 1)
    )
    assert p and p.raw["currency_mismatch"]
    q = load_query()
    its, unparsed = rows_to_itineraries(["garbage", RESEARCH_ROW], q, "best_load", "u")
    assert len(its) == 1 and unparsed == ["garbage"] and its[0].row_index == 1


@pytest.mark.parametrize(
    "month,day,anchor,expected",
    [(11, 7, date(2026, 9, 6), 2026), (1, 3, date(2026, 12, 20), 2027), (12, 30, date(2027, 1, 2), 2026)],
)
def test_infer_year(month, day, anchor, expected):
    assert infer_year(month, day, anchor) == expected


def test_split_carriers():
    assert split_carriers("Air Canada") == ["Air Canada"]
    assert split_carriers("Porter Airlines and Air Transat") == ["Porter Airlines", "Air Transat"]
    assert split_carriers("Air Canada, WestJet, and Condor") == ["Air Canada", "WestJet", "Condor"]
    assert split_carriers("Air Canada and Air Canada") == ["Air Canada"]


# ------------------------------------------------------------------ captured fixtures (YUL-CDG)
@pytest.mark.skipif(not (YUL_CDG / "best_rows.json").exists(), reason="fixture not captured")
def test_best_load_fixture_parses_at_least_15_rows_and_row0_fields():
    q = load_query()
    rows = load_rows("best")
    its, unparsed = rows_to_itineraries(rows, q, "best_load", "https://example/best")
    assert len(its) >= 15 and len(unparsed) <= len(rows) // 10
    r0 = its[0]
    assert r0.row_index == 0 and r0.candidate_source == "best_load"
    assert r0.price_results_cad and r0.price_results_cad > 0 and r0.currency_raw == "Canadian dollars"
    assert r0.stops is not None and r0.duration_min and r0.duration_min > 0
    assert r0.outbound.depart_local and r0.outbound.arrive_local and r0.airlines
    assert r0.outbound.depart_local.date() == q.depart_date
    assert r0.outbound.arrive_local >= r0.outbound.depart_local
    assert all(i.price_results_cad for i in its) and all(i.duration_min for i in its)


@pytest.mark.skipif(not (YUL_CDG / "duration_rows.json").exists(), reason="fixture not captured")
def test_native_picks_from_three_fixture_loads():
    q = load_query()
    cands = []
    for load in ("best", "cheapest", "duration"):
        its, _ = rows_to_itineraries(load_rows(load), q, f"{load}_load", f"https://example/{load}")
        cands.extend(its)
    from flight_scraper.models import Pick

    picks = select_picks(cands, native=frozenset(Pick))
    best, cheapest, fastest = picks[Pick.BEST], picks[Pick.CHEAPEST], picks[Pick.FASTEST]
    assert best.candidate_source == "best_load" and best.row_index == 0
    assert cheapest.candidate_source == "cheapest_load"
    assert fastest.candidate_source == "duration_load"
    cheapest_pool = [c for c in cands if c.candidate_source == "cheapest_load"]
    assert cheapest.price_results_cad == min(c.price_results_cad for c in cheapest_pool)
    duration_pool = [c for c in cands if c.candidate_source == "duration_load"]
    assert fastest.duration_min == min(c.duration_min for c in duration_pool)
    assert fastest.row_index == 0  # Duration sort → the first row is the fastest
    assert all(p.pick_rule == "native" for p in picks.values())


def test_query_fixture_matches_watchlist_shape():
    q = load_query()
    assert q.origin == "YUL" and q.destination == "CDG" and q.pax == PaxConfig(key="1a", adults=1, priority=3)
    assert q.return_date == q.depart_date.replace(day=q.depart_date.day + 7)
