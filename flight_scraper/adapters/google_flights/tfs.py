"""Minimal protobuf encoder for Google Flights' ``tfs`` URL parameter (no runtime dependency on
fast-flights / faster-flights).

Message layout (decoded from the research golden string, verified byte-for-byte in tests/test_tfs.py)::

    field 3  (repeated, len-delimited)  leg  { 2: "YYYY-MM-DD", 13: { 2: origin }, 14: { 2: destination } }
    field 8  (packed varints)              passengers  ADULT=1 per adult, CHILD=2 per child
    field 9  (varint)                      cabin       ECONOMY=1, PREMIUM_ECONOMY=2, BUSINESS=3, FIRST=4
    field 19 (varint)                      trip type   ROUND_TRIP=1, ONE_WAY=2

The companion ``tfu`` parameter holds the UI state (Cheapest tab / Duration sort); the two constants
below were observed live in the research and are appended verbatim.
"""

from __future__ import annotations

import base64
from datetime import date
from urllib.parse import urlencode

from ...models import Pick, SearchQuery

SEARCH_BASE = "https://www.google.com/travel/flights/search"
TFU = {
    Pick.CHEAPEST: "EgoIABAAGAAgAigB",  # "Cheapest" tab (TfuState.search_mode = CHEAPEST)
    Pick.FASTEST: "EgYIBRAAGAA",  # sort menu -> Duration (SortMode = 5)
}
CABIN = {"economy": 1, "premium_economy": 2, "business": 3, "first": 4}
PAX_ADULT, PAX_CHILD, PAX_INFANT_LAP, PAX_INFANT_SEAT = 1, 2, 3, 4
TRIP_ROUND, TRIP_ONE_WAY = 1, 2

WT_VARINT, WT_LEN = 0, 2


# ------------------------------------------------------------------ primitives
def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("negative varints are not supported")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _tag(field: int, wire_type: int) -> bytes:
    return encode_varint((field << 3) | wire_type)


def field_varint(field: int, value: int) -> bytes:
    return _tag(field, WT_VARINT) + encode_varint(value)


def field_bytes(field: int, payload: bytes) -> bytes:
    return _tag(field, WT_LEN) + encode_varint(len(payload)) + payload


def field_string(field: int, text: str) -> bytes:
    return field_bytes(field, text.encode("utf-8"))


def field_packed(field: int, values: list[int]) -> bytes:
    return field_bytes(field, b"".join(encode_varint(v) for v in values))


# ------------------------------------------------------------------ tfs message
def encode_leg(depart: date, origin: str, destination: str) -> bytes:
    return (
        field_string(2, depart.isoformat())
        + field_bytes(13, field_string(2, origin.upper()))
        + field_bytes(14, field_string(2, destination.upper()))
    )


def passengers_list(adults: int, children: int, infants_lap: int = 0, infants_seat: int = 0) -> list[int]:
    return (
        [PAX_ADULT] * adults
        + [PAX_CHILD] * children
        + [PAX_INFANT_LAP] * infants_lap
        + [PAX_INFANT_SEAT] * infants_seat
    )


def encode_tfs(
    origin: str,
    destination: str,
    depart_date: date,
    return_date: date | None,
    adults: int,
    children: int = 0,
    cabin: str = "economy",
) -> str:
    """Urlsafe-base64 (unpadded) tfs string for a round trip (one way when return_date is None)."""
    if cabin not in CABIN:
        raise ValueError(f"unknown cabin {cabin!r}")
    msg = field_bytes(3, encode_leg(depart_date, origin, destination))
    if return_date is not None:
        msg += field_bytes(3, encode_leg(return_date, destination, origin))
    msg += field_packed(8, passengers_list(adults, children))
    msg += field_varint(9, CABIN[cabin])
    msg += field_varint(19, TRIP_ROUND if return_date is not None else TRIP_ONE_WAY)
    return base64.urlsafe_b64encode(msg).decode("ascii").rstrip("=")


def build_search_url(query: SearchQuery, variant: Pick | None = None) -> str:
    """Google Flights results deep link; variant CHEAPEST / FASTEST append the matching tfu state."""
    tfs = encode_tfs(
        query.origin,
        query.destination,
        query.depart_date,
        query.return_date,
        query.pax.adults,
        query.pax.children,
        query.cabin,
    )
    params = {"tfs": tfs, "hl": "en-US", "curr": query.currency, "gl": "CA"}
    if variant in TFU:
        params["tfu"] = TFU[variant]
    return f"{SEARCH_BASE}?{urlencode(params)}"


# ------------------------------------------------------------------ decoder (tests / debugging only)
def decode_varint(buf: bytes, pos: int) -> tuple[int, int]:
    shift, value = 0, 0
    while True:
        b = buf[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, pos
        shift += 7


def decode_fields(buf: bytes) -> list[tuple[int, int, int | bytes]]:
    """Flat list of (field, wire_type, value) — value is int for varints, bytes for length-delimited."""
    out: list[tuple[int, int, int | bytes]] = []
    pos = 0
    while pos < len(buf):
        key, pos = decode_varint(buf, pos)
        field, wt = key >> 3, key & 7
        if wt == WT_VARINT:
            value, pos = decode_varint(buf, pos)
            out.append((field, wt, value))
        elif wt == WT_LEN:
            length, pos = decode_varint(buf, pos)
            out.append((field, wt, buf[pos : pos + length]))
            pos += length
        else:
            raise ValueError(f"unsupported wire type {wt} at {pos}")
    return out


def decode_tfs(tfs: str) -> dict:
    """Human-readable structure of a search tfs string (legs, passengers, cabin, trip_type)."""
    raw = base64.urlsafe_b64decode(tfs + "=" * (-len(tfs) % 4))
    legs: list[dict] = []
    result: dict = {"legs": legs, "passengers": [], "cabin": None, "trip_type": None, "other": []}
    for field, _wt, value in decode_fields(raw):
        if field == 3 and isinstance(value, bytes):
            leg: dict = {}
            for f, _w, v in decode_fields(value):
                if f == 2 and isinstance(v, bytes):
                    leg["date"] = v.decode()
                elif f in (13, 14) and isinstance(v, bytes):
                    inner = dict((ff, vv) for ff, _ww, vv in decode_fields(v))
                    code = inner.get(2)
                    leg["origin" if f == 13 else "destination"] = (
                        code.decode() if isinstance(code, bytes) else code
                    )
                else:
                    leg.setdefault("other", []).append((f, v))
            legs.append(leg)
        elif field == 8 and isinstance(value, bytes):
            pos = 0
            while pos < len(value):
                v, pos = decode_varint(value, pos)
                result["passengers"].append(v)
        elif field == 9:
            result["cabin"] = value
        elif field == 19:
            result["trip_type"] = value
        else:
            result["other"].append((field, value))
    return result


# ------------------------------------------------------------------ booking tfs (itinerary-specific)
def _decode_segment(buf: bytes) -> dict:
    """Leg field 4 = selected segment {1 origin, 2 date, 3 destination, 5 carrier, 6 flight number}."""
    seg: dict = {}
    names = {1: "origin", 2: "date", 3: "destination", 5: "carrier", 6: "number"}
    for f, _w, v in decode_fields(buf):
        if f in names and isinstance(v, bytes):
            seg[names[f]] = v.decode()
    return seg


def decode_booking_tfs(tfs: str) -> dict:
    """Structure of a ``/travel/flights/booking?tfs=…`` string: legs with their selected segments,
    passengers (packed or repeated varints), cabin and trip type. Observed live 2026-09-06."""
    raw = base64.urlsafe_b64decode(tfs + "=" * (-len(tfs) % 4))
    legs: list[dict] = []
    passengers: list[int] = []
    result: dict = {"legs": legs, "passengers": passengers, "cabin": None, "trip_type": None}
    for field, wt, value in decode_fields(raw):
        if field == 3 and isinstance(value, bytes):
            leg: dict = {"segments": []}
            for f, _w, v in decode_fields(value):
                if f == 2 and isinstance(v, bytes):
                    leg["date"] = v.decode()
                elif f == 4 and isinstance(v, bytes):
                    leg["segments"].append(_decode_segment(v))
                elif f in (13, 14) and isinstance(v, bytes):
                    inner = {ff: vv for ff, _ww, vv in decode_fields(v)}
                    code = inner.get(2)
                    leg["origin" if f == 13 else "destination"] = (
                        code.decode() if isinstance(code, bytes) else code
                    )
            legs.append(leg)
        elif field == 8:
            if wt == WT_VARINT:
                passengers.append(int(value))  # type: ignore[arg-type]
            elif isinstance(value, bytes):
                pos = 0
                while pos < len(value):
                    v, pos = decode_varint(value, pos)
                    passengers.append(v)
        elif field == 9:
            result["cabin"] = value
        elif field == 19:
            result["trip_type"] = value
    return result


def booking_flight_numbers(tfs: str) -> list[str]:
    """'TS 110', 'TS 111' … in leg order, from a booking tfs (empty when the structure is unknown)."""
    out: list[str] = []
    try:
        for leg in decode_booking_tfs(tfs)["legs"]:
            for seg in leg["segments"]:
                if seg.get("carrier") and seg.get("number"):
                    code = f"{seg['carrier']} {seg['number']}"
                    if code not in out:
                        out.append(code)
    except (ValueError, IndexError, KeyError):
        return []
    return out


def rewrite_passengers(tfs: str, adults: int, children: int) -> str:
    """Lever D experiment: the same booking tfs re-encoded for another passenger configuration.
    Field 8 is replaced (whether Google wrote it packed or as repeated varints); everything else is
    copied byte-for-byte."""
    raw = base64.urlsafe_b64decode(tfs + "=" * (-len(tfs) % 4))
    out = bytearray()
    inserted = False
    for field, wt, value in decode_fields(raw):
        if field == 8:
            if not inserted:
                for p in passengers_list(adults, children):
                    out += field_varint(8, p)
                inserted = True
            continue
        if wt == WT_VARINT:
            out += field_varint(field, int(value))  # type: ignore[arg-type]
        else:
            out += field_bytes(field, value)  # type: ignore[arg-type]
    if not inserted:
        for p in passengers_list(adults, children):
            out += field_varint(8, p)
    return base64.urlsafe_b64encode(bytes(out)).decode("ascii").rstrip("=")
