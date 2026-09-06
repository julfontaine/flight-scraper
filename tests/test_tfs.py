from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

from flight_scraper.adapters.google_flights.tfs import (
    TFU,
    build_search_url,
    decode_tfs,
    encode_tfs,
    encode_varint,
)
from flight_scraper.models import PaxConfig, Pick, SearchQuery

GOLDEN = "GhoSCjIwMjYtMTAtMTVqBRIDWVVMcgUSA0NERxoaEgoyMDI2LTEwLTIyagUSA0NER3IFEgNZVUxCAwEBAkgBmAEB"


def test_varint():
    assert encode_varint(0) == b"\x00"
    assert encode_varint(1) == b"\x01"
    assert encode_varint(127) == b"\x7f"
    assert encode_varint(128) == b"\x80\x01"
    assert encode_varint(300) == b"\xac\x02"


def test_golden_string_byte_for_byte():
    assert encode_tfs("YUL", "CDG", date(2026, 10, 15), date(2026, 10, 22), adults=2, children=1) == GOLDEN


def test_decode_round_trip():
    decoded = decode_tfs(GOLDEN)
    assert decoded["legs"] == [
        {"date": "2026-10-15", "origin": "YUL", "destination": "CDG"},
        {"date": "2026-10-22", "origin": "CDG", "destination": "YUL"},
    ]
    assert decoded["passengers"] == [1, 1, 2]
    assert decoded["cabin"] == 1
    assert decoded["trip_type"] == 1
    assert decoded["other"] == []


def test_one_adult_two_children_and_one_way():
    d = decode_tfs(encode_tfs("YQB", "MCO", date(2026, 12, 5), date(2026, 12, 12), 1, 2))
    assert d["passengers"] == [1, 2, 2]
    ow = decode_tfs(encode_tfs("YQB", "MCO", date(2026, 12, 5), None, 1))
    assert ow["trip_type"] == 2 and len(ow["legs"]) == 1


def test_build_search_url(query_yul_cdg: SearchQuery):
    url = build_search_url(query_yul_cdg)
    parsed = urlparse(url)
    assert parsed.netloc == "www.google.com" and parsed.path == "/travel/flights/search"
    qs = parse_qs(parsed.query)
    assert qs["tfs"] == [GOLDEN]
    assert qs["hl"] == ["en-US"] and qs["curr"] == ["CAD"] and qs["gl"] == ["CA"]
    assert "tfu" not in qs
    assert parse_qs(urlparse(build_search_url(query_yul_cdg, Pick.CHEAPEST)).query)["tfu"] == [
        TFU[Pick.CHEAPEST]
    ]
    assert parse_qs(urlparse(build_search_url(query_yul_cdg, Pick.FASTEST)).query)["tfu"] == [
        TFU[Pick.FASTEST]
    ]
    assert "tfu" not in parse_qs(urlparse(build_search_url(query_yul_cdg, Pick.BEST)).query)


def test_tfu_constants_verbatim_from_research():
    assert TFU[Pick.CHEAPEST] == "EgoIABAAGAAgAigB"
    assert TFU[Pick.FASTEST] == "EgYIBRAAGAA"


def test_unknown_cabin_rejected():
    with pytest.raises(ValueError):
        encode_tfs("YUL", "CDG", date(2026, 10, 15), date(2026, 10, 22), 1, cabin="cargo")


def test_cross_check_with_fast_flights_if_installed():
    ff = pytest.importorskip("fast_flights")
    q = ff.create_query(
        flights=[
            ff.FlightQuery(date="2026-10-15", from_airport="YUL", to_airport="CDG"),
            ff.FlightQuery(date="2026-10-22", from_airport="CDG", to_airport="YUL"),
        ],
        trip="round-trip",
        seat="economy",
        passengers=ff.Passengers(adults=2, children=1),
        language="en-US",
        currency="CAD",
    )
    assert q.params()["tfs"] == GOLDEN


def test_query_pax_model_validation():
    with pytest.raises(ValueError):
        PaxConfig(key="0a", adults=0)
