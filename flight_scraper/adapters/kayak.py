"""Kayak (ca.kayak.com) — DISABLED in v1. URL builder is implemented and tested for a future enablement."""

from __future__ import annotations

from ..models import Pick, SearchQuery
from ._stub import DisabledAdapter, child_ages_for

SORT = {None: "bestflight_a", Pick.BEST: "bestflight_a", Pick.CHEAPEST: "price_a", Pick.FASTEST: "duration_a"}


class KayakAdapter(DisabledAdapter):
    source_id = "kayak"
    name = "Kayak (ca.kayak.com)"
    kind = "meta"
    priority = 4
    native_picks = frozenset({Pick.BEST, Pick.CHEAPEST, Pick.FASTEST})
    default_price_stage = "results"
    disabled_reason = (
        "v1 disabled: PerimeterX/HUMAN (or Akamai) reported; robots.txt disallows /flights/; "
        "ToS s.4 forbids automated tools; metasearch handoff = no checkout total. "
        "Research: finding category=kayak"
    )

    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        """Verified 200: /flights/YUL-CDG/2026-10-15/2026-10-22/2adults/children-8?sort=bestflight_a"""
        q = query
        path = f"{q.origin}-{q.destination}/{q.depart_date}/{q.return_date}/{q.pax.adults}adults"
        ages = child_ages_for(query)
        if ages:
            path += "/children-" + "-".join(str(a) for a in ages)
        return f"https://www.ca.kayak.com/flights/{path}?sort={SORT[variant]}"
