"""Adapter contract shared by all nine sources (only google_flights is enabled in v1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from .. import picks as pick_rules
from ..models import Itinerary, Pick, SearchQuery, SearchResult

if TYPE_CHECKING:  # no Playwright import at runtime outside browser.py / the live adapter
    from ..config import Budget, Settings
    from ..pacing import PageLoadBudget, Sleeper


class SourceDisabled(RuntimeError):
    """Raised by stub adapters; the runner records status='skipped' with the reason and moves on."""


class BlockedError(RuntimeError):
    """Raised when block markers are detected (403/429, /sorry/, consent page, 'unusual traffic', captcha)."""


class NoResultsParsed(RuntimeError):
    """Zero parsed rows after the wait, without block markers (retryable once)."""


class ArtifactSaver:
    """Default no-op; browser.py provides the real one (screenshot + HTML under artifacts/<run_id>/)."""

    def save(self, page: Any, search_key: str, reason: str) -> Any:
        return None


class BaseAdapter(ABC):
    source_id: ClassVar[str]
    name: ClassVar[str]
    kind: ClassVar[str]  # 'meta' | 'ota' | 'airline'
    enabled: ClassVar[bool] = False
    disabled_reason: ClassVar[str | None] = None
    native_picks: ClassVar[frozenset[Pick]] = frozenset()  # picks the site ranks itself
    default_price_stage: ClassVar[str] = "results"
    priority: ClassVar[int] = 99  # enable order (1 = first)

    def __init__(
        self,
        settings: Settings | None = None,
        budget_cfg: Budget | None = None,
        budget: PageLoadBudget | None = None,
        sleeper: Sleeper | None = None,
        artifacts: ArtifactSaver | None = None,
    ) -> None:
        from ..config import Budget as _Budget  # local import keeps module import cheap

        self.settings = settings
        self.budget_cfg = budget_cfg or _Budget()
        self.budget = budget
        self.sleep = sleeper
        self.artifacts = artifacts or ArtifactSaver()
        self.current_search_key: str | None = None

    # ---- pure -------------------------------------------------------------------------------
    @abstractmethod
    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        """Pure function. variant=None → default/Best load; Pick.CHEAPEST / Pick.FASTEST → sort state."""

    # ---- browser ----------------------------------------------------------------------------
    @abstractmethod
    def search(self, page: Any, query: SearchQuery) -> list[Itinerary]:
        """Load the results view(s); return ALL parsed candidates tagged with candidate_source + row_index.
        Must call self.budget.consume(1) per page load and raise BlockedError on block markers."""

    def select_picks(self, itineraries: list[Itinerary]) -> dict[Pick, Itinerary]:
        """Native tabs/sorts when the site has them (self.native_picks), local-v1 scoring otherwise."""
        return pick_rules.select_picks(itineraries, native=self.native_picks)

    def enrich_luggage(self, page: Any, query: SearchQuery, itinerary: Itinerary, pick: Pick) -> Itinerary:
        """Deepest step reachable without paying/logging in: final price, luggage, deep link (no-op)."""
        return itinerary

    def run_search(self, page: Any, query: SearchQuery) -> SearchResult:  # template method used by runner.py
        if not self.enabled:
            raise SourceDisabled(self.disabled_reason or "disabled")
        self.current_search_key = query.search_key
        candidates = self.search(page, query)
        if not candidates:
            raise NoResultsParsed("no_results_parsed")
        picks = self.select_picks(candidates)
        mode = self.budget_cfg.booking_visits
        visited: dict[tuple, Itinerary] = {}
        for pick, it in list(picks.items()):
            if mode == "none" or (mode == "best_only" and pick is not Pick.BEST):
                continue
            key = it.identity()
            if key in visited:
                picks[pick] = visited[key].model_copy(deep=True)
                picks[pick].raw["booking_dedup_of"] = visited[key].raw.get("booking_pick")
            else:
                enriched = self.enrich_luggage(page, query, it, pick)
                enriched.raw.setdefault("booking_pick", pick.value)
                visited[key] = enriched
                picks[pick] = enriched
        page_loads = self.budget.used_in_current_search if self.budget else 0
        return SearchResult(
            query=query,
            picks=picks,
            candidates=len(candidates),
            status="ok",
            page_url=self.build_url(query),
            page_loads=page_loads,
        )
