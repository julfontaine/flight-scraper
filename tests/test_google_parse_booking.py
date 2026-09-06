"""Google Flights booking-page parser: synthetic body (research transcript) + captured fixtures."""

from __future__ import annotations

import pytest

from flight_scraper.adapters.google_flights.parse_booking import parse_booking_text
from tests.conftest import FIXTURES

YUL_CDG = FIXTURES / "google_flights" / "YUL-CDG"

RESEARCH_BODY = """Skip to main content
Itinerary summary
Montréal-Pierre Elliott Trudeau International Airport
5:00 PM – 9:30 AM+1
Porter Airlines, Air Transat
1 stop
11 hr 30 min
1 free carry-on per passenger
First checked bag costs between 150 Canadian dollars and 170 Canadian dollars per passenger
1st checked bag per passenger: CA$150–170
Fare non-refundable, taxes may be refundable
Booking options
Book with Air Transat
Airline
CA$2,173
Continue
Book with FlightHub
CA$2,254
Continue
Book with Justfly.com
CA$2,254
Continue
Book with Gotogate
CA$2,359
Continue
Book with Porter Airlines
Price hidden because it might be incorrect
Visit site for price
2 more booking options
Prices include required taxes + fees for 3 passengers. Optional charges and bag fees may apply.
Price insights
CA$2,173 is low for Economy — CA$1,403 cheaper than usual; usually CA$2,700–5,600
"""


def test_research_body_providers_prices_luggage_and_insight():
    info = parse_booking_text(RESEARCH_BODY)
    names = [p.name for p in info.providers]
    assert names == ["Air Transat", "FlightHub", "Justfly.com", "Gotogate", "Porter Airlines"]
    assert info.providers[0].total_cad == 2173.0 and info.providers[0].is_airline
    assert info.providers[1].total_cad == 2254.0 and not info.providers[1].is_airline
    porter = info.providers[-1]
    assert porter.total_cad is None and porter.note and "hidden" in porter.note.lower()
    assert info.cheapest and info.cheapest.name == "Air Transat" and info.cheapest.total_cad == 2173.0
    assert info.passengers_note == 3
    assert info.carry_on_included is True and info.carry_on_fee_cad is None
    assert info.checked_bag_fee_cad == 150.0 and info.checked_bag_fee_max_cad == 170.0
    assert "150" in (info.checked_bag_fee_raw or "")
    assert info.price_insight and info.price_insight.startswith("CA$2,173 is low for Economy")
    assert info.currency_raw == "CA$" and info.has_luggage_info and not info.separate_tickets
    raw = info.to_raw()
    assert raw["parser_version"] and len(raw["providers"]) == 5 and raw["luggage_text"]


def test_no_carry_on_basic_fare_and_free_checked_bag():
    body = "Book with Air Canada\nAirline\nCA$999\nNo carry-on bag\n1 free checked bag per passenger\n"
    info = parse_booking_text(body)
    assert info.carry_on_included is False and info.checked_bag_fee_cad == 0.0
    assert info.cheapest and info.cheapest.total_cad == 999.0


def test_no_luggage_text_leaves_fields_none():
    info = parse_booking_text("Book with X\nCA$1,000\nPrices include required taxes + fees for 1 passenger.")
    assert info.carry_on_included is None and info.checked_bag_fee_cad is None and not info.has_luggage_info
    assert info.passengers_note == 1


def test_hidden_price_only_means_no_cheapest():
    info = parse_booking_text(
        "Book with Y\nPrice hidden because it might be incorrect\nVisit site for price\n"
    )
    assert len(info.providers) == 1 and info.cheapest is None


def test_loading_page_yields_nothing():
    info = parse_booking_text("Itinerary summary\nGetting prices\nLoading results\n")
    assert info.providers == [] and info.cheapest is None and info.passengers_note is None


@pytest.mark.parametrize("pick", ["best", "cheapest", "fastest"])
def test_captured_booking_fixture(pick: str):
    path = YUL_CDG / f"booking_{pick}.txt"
    if not path.exists():
        pytest.skip("fixture not captured")
    info = parse_booking_text(path.read_text(encoding="utf-8"))
    assert info.providers, "captured booking page must list at least one provider"
    assert info.cheapest is not None and info.cheapest.total_cad and info.cheapest.total_cad > 0
    assert info.passengers_note == 1  # 1a capture
    assert info.currency_raw == "CA$"
    assert any(p.is_airline for p in info.providers) or info.cheapest.name
