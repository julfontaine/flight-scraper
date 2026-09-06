"""Shared behaviour for disabled sources: every call into the browser raises SourceDisabled(reason)."""

from __future__ import annotations

from typing import Any

from ..models import Itinerary, Pick, SearchQuery
from .base import BaseAdapter, SourceDisabled

DEFAULT_CHILD_AGE = 8  # research default for sources that require an age; Google itself has none


def child_ages_for(query: SearchQuery) -> list[int]:
    ages = list(query.pax.child_ages)
    while len(ages) < query.pax.children:
        ages.append(DEFAULT_CHILD_AGE)
    return ages[: query.pax.children]


class DisabledAdapter(BaseAdapter):
    enabled = False

    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        raise SourceDisabled(self.disabled_reason or "disabled")

    def search(self, page: Any, query: SearchQuery) -> list[Itinerary]:
        raise SourceDisabled(self.disabled_reason or "disabled")
