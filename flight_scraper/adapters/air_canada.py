"""Air Canada — DISABLED in v1. Confirmed deep-link builder kept for a future (headed) enablement."""

from __future__ import annotations

from urllib.parse import urlencode

from ..models import Pick, SearchQuery
from ._stub import DisabledAdapter

# Minimal country map for the seed watch-list; anything unknown is treated as international.
COUNTRY = {
    "YQB": "CA",
    "YUL": "CA",
    "YYZ": "CA",
    "YVR": "CA",
    "YOW": "CA",
    "YHZ": "CA",
    "YYC": "CA",
    "FLL": "US",
    "MCO": "US",
    "MIA": "US",
    "JFK": "US",
    "EWR": "US",
    "LAX": "US",
    "CUN": "MX",
    "CDG": "FR",
    "LHR": "GB",
}


def market_code(origin: str, destination: str) -> str:
    """DOM (both Canada), TNB (Canada <-> US), INT (everything else) — inferred AC convention, unverified."""
    a, b = COUNTRY.get(origin, "XX"), COUNTRY.get(destination, "XX")
    if a == "CA" and b == "CA":
        return "DOM"
    if {a, b} == {"CA", "US"}:
        return "TNB"
    return "INT"


class AirCanadaAdapter(DisabledAdapter):
    source_id = "air_canada"
    name = "Air Canada"
    kind = "airline"
    priority = 3
    default_price_stage = "fare_select"
    disabled_reason = (
        "v1 disabled: Akamai Bot Manager confirmed; ToS forbids automated access; review page needs dummy "
        "passenger data (unverified). Deep link exists. Research: finding category=air-canada"
    )

    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        params = {
            "org0": query.origin,
            "dest0": query.destination,
            "departureDate0": str(query.depart_date),
            "org1": query.destination,
            "dest1": query.origin,
            "departureDate1": str(query.return_date),
            "ADT": query.pax.adults,
            "YTH": 0,
            "CHD": query.pax.children,
            "INF": 0,
            "INS": 0,
            "lang": "en-CA",
            "tripType": "R",
            "marketCode": market_code(query.origin, query.destination),
        }
        return f"https://www.aircanada.com/booking/ca/en/aco/availability/rt/outbound?{urlencode(params)}"
