"""Booking-tfs helpers: flight numbers from the itinerary link and the lever-D passenger rewrite."""

from __future__ import annotations

from datetime import date

from flight_scraper.adapters.google_flights.tfs import (
    booking_flight_numbers,
    decode_booking_tfs,
    decode_tfs,
    encode_tfs,
    rewrite_passengers,
)

# captured live 2026-09-06: YUL-CDG 2026-11-07/14, 1 adult, Air Transat TS 110 / TS 111
BOOKING_TFS = (
    "CBwQAho_EgoyMDI2LTExLTA3Ih8KA1lVTBIKMjAyNi0xMS0wNxoDQ0RHKgJUUzIDMTEwagcIARIDWVVMcgcIARIDQ0RHGj8SCjIwMjYt"
    "MTEtMTQiHwoDQ0RHEgoyMDI2LTExLTE0GgNZVUwqAlRTMgMxMTFqBwgBEgNDREdyBwgBEgNZVUxAAUgBcAGCAQsI____________AZgBAQ"
)


def test_decode_booking_tfs_legs_segments_passengers():
    d = decode_booking_tfs(BOOKING_TFS)
    assert [leg["origin"] + "-" + leg["destination"] for leg in d["legs"]] == ["YUL-CDG", "CDG-YUL"]
    assert [leg["date"] for leg in d["legs"]] == ["2026-11-07", "2026-11-14"]
    assert d["legs"][0]["segments"] == [
        {"origin": "YUL", "date": "2026-11-07", "destination": "CDG", "carrier": "TS", "number": "110"}
    ]
    assert d["passengers"] == [1] and d["cabin"] == 1 and d["trip_type"] == 1


def test_booking_flight_numbers():
    assert booking_flight_numbers(BOOKING_TFS) == ["TS 110", "TS 111"]
    assert booking_flight_numbers("") == []
    assert booking_flight_numbers("!!!not-base64") == []


def test_rewrite_passengers_replaces_only_field_8():
    t2 = rewrite_passengers(BOOKING_TFS, 2, 1)
    d1, d2 = decode_booking_tfs(BOOKING_TFS), decode_booking_tfs(t2)
    assert d2["passengers"] == [1, 1, 2]
    assert d2["legs"] == d1["legs"] and d2["cabin"] == d1["cabin"] and d2["trip_type"] == d1["trip_type"]
    assert booking_flight_numbers(t2) == ["TS 110", "TS 111"]
    assert rewrite_passengers(t2, 1, 0) == BOOKING_TFS  # round trip back to the original bytes


def test_rewrite_passengers_on_a_search_tfs_packed_field():
    tfs = encode_tfs("YUL", "CDG", date(2026, 10, 15), date(2026, 10, 22), 2, 1)
    assert decode_tfs(tfs)["passengers"] == [1, 1, 2]
    t2 = rewrite_passengers(tfs, 1, 2)
    assert decode_booking_tfs(t2)["passengers"] == [1, 2, 2]
    assert decode_tfs(t2)["legs"] == decode_tfs(tfs)["legs"]
