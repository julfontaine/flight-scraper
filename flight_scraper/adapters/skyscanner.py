"""Skyscanner.ca — DISABLED in v1. Official referral URL builder kept for a future enablement."""

from __future__ import annotations

from urllib.parse import urlencode

from ..models import Pick, SearchQuery
from ._stub import DisabledAdapter, child_ages_for

SORTBY = {Pick.CHEAPEST: "cheapest", Pick.FASTEST: "fastest"}


class SkyscannerAdapter(DisabledAdapter):
    source_id = "skyscanner"
    name = "Skyscanner.ca"
    kind = "meta"
    priority = 6
    native_picks = frozenset({Pick.BEST, Pick.CHEAPEST, Pick.FASTEST})
    disabled_reason = (
        "v1 disabled: PerimeterX confirmed (_pxhd), 2026 reports of persistent 403 captcha; "
        "robots disallows /transport/*; partner-only deep links; no bag data. "
        "Research: finding category=skyscanner"
    )

    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        """/transport/flights/{orig}/{dest}/{YYMMDD}/{YYMMDD}/?adultsv2=..&childrenv2=8|12&cabinclass=economy&rtn=1"""
        params: dict[str, str] = {"adultsv2": str(query.pax.adults)}
        ages = child_ages_for(query)
        if ages:
            params["childrenv2"] = "|".join(str(a) for a in ages)
        params.update({"cabinclass": query.cabin, "rtn": "1", "preferdirects": "false"})
        if variant in SORTBY:
            params["sortby"] = SORTBY[variant]
        d1, d2 = query.depart_date.strftime("%y%m%d"), query.return_date.strftime("%y%m%d")
        return (
            f"https://www.skyscanner.ca/transport/flights/{query.origin.lower()}/{query.destination.lower()}/"
            f"{d1}/{d2}/?{urlencode(params)}"
        )
