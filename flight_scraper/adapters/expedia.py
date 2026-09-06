"""Expedia.ca — DISABLED in v1. Official white-label deep link builder kept for a future enablement."""

from __future__ import annotations

from urllib.parse import urlencode

from ..models import Pick, SearchQuery
from ._stub import DisabledAdapter, child_ages_for

CLASS = {"economy": 3, "business": 2, "first": 1, "premium_economy": 3}


class ExpediaAdapter(DisabledAdapter):
    source_id = "expedia"
    name = "Expedia.ca"
    kind = "ota"
    priority = 9
    default_price_stage = "results"
    disabled_reason = (
        "v1 disabled: Akamai Bot Manager returned HTTP 429 on first request; robots disallows "
        "/Flights-Search and /Checkout; ToS forbids scrapers; checkout needs 5+ unverified JS steps. "
        "Research: finding category=expedia"
    )

    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        params: dict[str, str] = {
            "FromAirport": query.origin,
            "ToAirport": query.destination,
            "NumAdult": str(query.pax.adults),
            "NumChild": str(query.pax.children),
        }
        for i, age in enumerate(child_ages_for(query), start=1):
            params[f"Child{i}Age"] = str(age)
        params["Class"] = str(CLASS.get(query.cabin, 3))
        params["currency"] = query.currency
        return (
            f"https://www.expedia.ca/go/flight/search/Roundtrip/{query.depart_date}/{query.return_date}"
            f"?{urlencode(params)}"
        )
