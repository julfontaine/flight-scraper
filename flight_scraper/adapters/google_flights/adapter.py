"""Google Flights adapter — Phase 1 skeleton: URL builder only; the browser flow lands in Phase 2."""

from __future__ import annotations

from typing import Any

from ...models import Itinerary, Pick, SearchQuery
from ..base import BaseAdapter
from .tfs import build_search_url


class GoogleFlightsAdapter(BaseAdapter):
    source_id = "google_flights"
    name = "Google Flights"
    kind = "meta"
    enabled = True
    priority = 1
    disabled_reason = None
    native_picks = frozenset({Pick.BEST, Pick.CHEAPEST, Pick.FASTEST})
    default_price_stage = "booking"

    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        return build_search_url(query, variant)

    def search(self, page: Any, query: SearchQuery) -> list[Itinerary]:
        raise NotImplementedError("adapter not implemented (phase 2)")
