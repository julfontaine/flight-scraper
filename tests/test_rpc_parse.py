"""batchexecute envelope decoding + the DOM/RPC price cross-check (synthetic bodies: no captured RPC yet)."""

from __future__ import annotations

import json

from flight_scraper.adapters.google_flights.rpc import (
    cross_check,
    decode_batchexecute,
    numbers_in,
    strip_xssi,
)

INNER = [[None, [[720, "TS", "110"], [752, "AC", "870"]], "CAD"]]
BODY = ")]}'\n" + json.dumps(
    [["wrb.fr", "GetShoppingResults", json.dumps(INNER), None, None, None, "generic"]]
)
CHUNKED = (
    ")]}'\n\n42\n" + json.dumps([["wrb.fr", "GetShoppingResults", json.dumps(INNER)]]) + '\n7\n[["di",1]]\n'
)


def test_strip_xssi():
    assert strip_xssi(")]}'\n[1]") == "[1]" and strip_xssi("[1]") == "[1]"


def test_decode_batchexecute_plain_and_chunked():
    assert decode_batchexecute(BODY) == [INNER]
    assert decode_batchexecute(CHUNKED) == [INNER]
    assert decode_batchexecute("garbage") == []


def test_numbers_in_and_cross_check():
    assert {720, 752} <= numbers_in(INNER)
    report = cross_check([BODY], [720.0, 752.0])
    assert report["dom_min_in_rpc"] and report["dom_max_in_rpc"] and report["payloads"] == 1
    report = cross_check([BODY], [720.0, 999.0])
    assert report["dom_min_in_rpc"] and not report["dom_max_in_rpc"]
    assert cross_check([], []) == {"bodies": 0, "payloads": 0, "dom_rows": 0}
