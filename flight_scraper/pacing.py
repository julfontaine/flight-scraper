"""Page-load budget and jittered sleeping — pure, browser-free, injectable into tests."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable

from .config import Budget

log = logging.getLogger(__name__)


class BudgetExhausted(RuntimeError):
    """Raised when a page load would exceed the per-run hard cap."""


class PageLoadBudget:
    """Counts page loads (1 per goto, 1 per outbound click, 1 per return click) against a hard cap."""

    def __init__(self, max_loads: int) -> None:
        self.max_loads = max_loads
        self.used = 0
        self.used_in_current_search = 0

    @property
    def remaining(self) -> int:
        return max(self.max_loads - self.used, 0)

    def begin_search(self) -> None:
        self.used_in_current_search = 0

    def can_start_search(self, est_loads: int) -> bool:
        return self.remaining >= est_loads

    def consume(self, n: int = 1) -> None:
        if self.used + n > self.max_loads:
            raise BudgetExhausted(f"page-load budget exhausted ({self.used}/{self.max_loads}, wanted {n})")
        self.used += n
        self.used_in_current_search += n


class Sleeper:
    """Uniform-random jitter from the watch-list delays; ``clock`` is injectable for tests."""

    def __init__(
        self, budget: Budget, clock: Callable[[float], None] | None = None, scale: float = 1.0
    ) -> None:
        self.budget = budget
        self.clock = clock or time.sleep
        self.scale = scale
        self.rng = random.Random()
        self.total_slept = 0.0

    def _sleep_range(self, rng: tuple[float, float], label: str) -> float:
        lo, hi = rng
        seconds = self.rng.uniform(lo, hi) * self.scale
        log.debug("sleep %.1fs (%s)", seconds, label)
        self.clock(seconds)
        self.total_slept += seconds
        return seconds

    def between_actions(self) -> float:
        return self._sleep_range(self.budget.delays_s.between_actions, "between_actions")

    def between_loads(self) -> float:
        return self._sleep_range(self.budget.delays_s.between_loads, "between_loads")

    def between_searches(self) -> float:
        return self._sleep_range(self.budget.delays_s.between_searches, "between_searches")

    def retry_pause(self) -> float:
        return self._sleep_range(self.budget.retry.retry_pause_s, "retry_pause")

    def block_pause(self) -> float:
        return self._sleep_range(self.budget.block_pause_s, "block_pause")

    def settle(self, lo: float = 3.0, hi: float = 5.0) -> float:
        return self._sleep_range((lo, hi), "settle")
