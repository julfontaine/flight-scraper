"""The run loop: planned queries → adapter.run_search → sink + rotation state, with retries, block
breaker and the page-load budget guard. Browser-agnostic: a ``session_factory`` yields the page object
(``None`` in Phase 1 / tests with fake adapters)."""

from __future__ import annotations

import contextlib
import logging
import time
import traceback
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .adapters import REGISTRY, ArtifactSaver, BaseAdapter, BlockedError, NoResultsParsed, SourceDisabled
from .config import Settings, WatchList
from .dates import run_local_date
from .db import RunInfo, Sink, git_sha, hostname
from .models import SearchQuery, SearchResult
from .pacing import BudgetExhausted, PageLoadBudget, Sleeper
from .scheduler import RotationState

log = logging.getLogger(__name__)

SessionFactory = Callable[[str], AbstractContextManager[Any]]


@contextlib.contextmanager
def null_session(_source_id: str) -> Iterator[None]:
    """No browser (Phase 1, unit tests)."""
    yield None


class RunReport(BaseModel):
    run: RunInfo
    results: list[SearchResult] = Field(default_factory=list)
    elapsed_s: float = 0.0
    aborted_reason: str | None = None

    @property
    def exit_code(self) -> int:
        """0 = ok/partial, 2 = blocked, 3 = failed."""
        return {"ok": 0, "partial": 0, "blocked": 2, "failed": 3}.get(self.run.status, 3)


def describe_exception(exc: BaseException) -> str:
    """'Class: message @ file:line in func' — persisted into searches.error."""
    tb = traceback.extract_tb(exc.__traceback__)
    where = ""
    if tb:
        frame = tb[-1]
        where = f" @ {frame.filename.rsplit('/', 1)[-1]}:{frame.lineno} in {frame.name}"
    return f"{type(exc).__name__}: {exc}"[:500] + where


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, NoResultsParsed | TimeoutError):
        return True
    return type(exc).__name__ == "TimeoutError"  # playwright.sync_api.TimeoutError without importing it


class Runner:
    def __init__(
        self,
        settings: Settings,
        watchlist: WatchList,
        sink: Sink,
        state: RotationState,
        *,
        dry_run: bool = True,
        page_budget: PageLoadBudget | None = None,
        sleeper: Sleeper | None = None,
        session_factory: SessionFactory | None = None,
        artifacts: ArtifactSaver | None = None,
        adapters: dict[str, type[BaseAdapter]] | None = None,
        run_id: str | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.watchlist = watchlist
        self.sink = sink
        self.state = state
        self.dry_run = dry_run
        self.budget_cfg = watchlist.budget
        self.page_budget = page_budget or PageLoadBudget(watchlist.budget.max_page_loads_per_run)
        self.sleeper = sleeper or Sleeper(watchlist.budget)
        self.session_factory = session_factory or null_session
        self.artifacts = artifacts or ArtifactSaver()
        self.registry = adapters or REGISTRY
        self.run_id = run_id or str(uuid.uuid4())
        self.now = now or (lambda: datetime.now(UTC))
        self._adapters: dict[str, BaseAdapter] = {}
        self._sessions: dict[str, tuple[AbstractContextManager[Any], Any]] = {}

    # ---- helpers --------------------------------------------------------------------------
    def adapter_for(self, source_id: str) -> BaseAdapter:
        if source_id not in self._adapters:
            cls = self.registry[source_id]
            self._adapters[source_id] = cls(
                self.settings, self.budget_cfg, self.page_budget, self.sleeper, self.artifacts
            )
        return self._adapters[source_id]

    def page_for(self, source_id: str) -> Any:
        """One browser context per source, opened lazily, closed at the end of the run."""
        if source_id not in self._sessions:
            cm = self.session_factory(source_id)
            page = cm.__enter__()
            self._sessions[source_id] = (cm, page)
        return self._sessions[source_id][1]

    def _close_sessions(self) -> None:
        for source_id, (cm, _page) in list(self._sessions.items()):
            try:
                cm.__exit__(None, None, None)
            except Exception as exc:  # noqa: BLE001 - closing must never mask the run outcome
                log.warning("closing browser session for %s failed: %s", source_id, exc)
        self._sessions.clear()

    def _mark_state(self, result: SearchResult) -> None:
        ok = result.status in ("ok", "partial")
        try:
            if result.blocked and hasattr(self.state, "blocked"):
                self.state.mark(result.query.cell_key, ok, self.now(), blocked=True)  # type: ignore[call-arg]
            elif result.status != "skipped":
                self.state.mark(result.query.cell_key, ok, self.now())
        except Exception as exc:  # noqa: BLE001
            log.warning("rotation state update failed: %s", exc)

    # ---- one search ---------------------------------------------------------------------------
    def run_one(self, query: SearchQuery) -> SearchResult:
        adapter = self.adapter_for(query.source_id)
        started = self.now()
        if not adapter.enabled:
            return SearchResult(
                query=query,
                status="skipped",
                error=f"SourceDisabled: {adapter.disabled_reason}",
                started_at=started,
                finished_at=self.now(),
            )
        attempts = self.budget_cfg.retry.per_search_attempts
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            self.page_budget.begin_search()
            try:
                page = self.page_for(query.source_id)
                result = adapter.run_search(page, query)
                result.started_at, result.finished_at, result.attempts = started, self.now(), attempt
                return result
            except SourceDisabled as exc:
                return SearchResult(
                    query=query,
                    status="skipped",
                    error=f"SourceDisabled: {exc}",
                    started_at=started,
                    finished_at=self.now(),
                    attempts=attempt,
                )
            except BlockedError as exc:
                log.warning("BLOCKED %s: %s", query.search_key, exc)
                return SearchResult(
                    query=query,
                    status="blocked",
                    blocked=True,
                    error=describe_exception(exc),
                    page_url=adapter.build_url(query),
                    page_loads=self.page_budget.used_in_current_search,
                    started_at=started,
                    finished_at=self.now(),
                    attempts=attempt,
                )
            except BudgetExhausted as exc:
                return SearchResult(
                    query=query,
                    status="error",
                    error=describe_exception(exc),
                    page_url=adapter.build_url(query),
                    page_loads=self.page_budget.used_in_current_search,
                    started_at=started,
                    finished_at=self.now(),
                    attempts=attempt,
                )
            except Exception as exc:  # noqa: BLE001 - captured into searches.error, never swallowed
                last_error = describe_exception(exc)
                retry = is_retryable(exc) and attempt < attempts
                log.warning(
                    "search %s attempt %d failed: %s%s",
                    query.search_key,
                    attempt,
                    last_error,
                    " (retrying)" if retry else "",
                )
                if not retry:
                    break
                self.sleeper.retry_pause()
        return SearchResult(
            query=query,
            status="error",
            error=last_error,
            page_url=adapter.build_url(query),
            page_loads=self.page_budget.used_in_current_search,
            started_at=started,
            finished_at=self.now(),
            attempts=attempts,
        )

    # ---- the run --------------------------------------------------------------------------
    def run(self, queries: list[SearchQuery]) -> RunReport:
        t0 = time.monotonic()
        run = RunInfo(
            run_id=self.run_id,
            started_at=self.now(),
            git_sha=git_sha(self.settings.project_root),
            host=hostname(),
            scrape_date=run_local_date(),
            dry_run=self.dry_run,
            sources=sorted({q.source_id for q in queries}),
            budget=self.budget_cfg.model_dump(mode="json")
            | {"max_page_loads_per_run": self.page_budget.max_loads},
            searches_total=len(queries),
        )
        self.sink.start_run(run)
        results: list[SearchResult] = []
        aborted: str | None = None
        consecutive_blocks = 0
        est = self.budget_cfg.est_page_loads_per_search
        try:
            for i, query in enumerate(queries):
                if not self.page_budget.can_start_search(est):
                    aborted = f"budget: {self.page_budget.remaining} loads left < {est} needed"
                    log.info("stopping: %s", aborted)
                    break
                log.info("search %d/%d %s", i + 1, len(queries), query.search_key)
                result = self.run_one(query)
                results.append(result)
                try:
                    self.sink.write_search(result)
                except Exception as exc:  # noqa: BLE001 - DB errors must not abort the run
                    log.error("sink write failed for %s: %s", query.search_key, describe_exception(exc))
                    run.notes = (run.notes or "") + f"sink error: {describe_exception(exc)}; "
                self._mark_state(result)
                if result.blocked:
                    consecutive_blocks += 1
                    if consecutive_blocks >= self.budget_cfg.abort_after_consecutive_blocks:
                        aborted = f"{consecutive_blocks} consecutive blocks"
                        log.error("aborting run: %s", aborted)
                        break
                    self.sleeper.block_pause()
                else:
                    consecutive_blocks = 0
                more = i + 1 < len(queries) and self.page_budget.can_start_search(est)
                if more and result.status != "skipped":
                    self.sleeper.between_searches()
        finally:
            self._close_sessions()

        run.finished_at = self.now()
        run.page_loads = self.page_budget.used
        run.searches_ok = sum(r.status in ("ok", "partial") for r in results)
        run.searches_blocked = sum(r.blocked for r in results)
        run.searches_error = sum(r.status == "error" for r in results)
        run.searches_skipped = sum(r.status == "skipped" for r in results)
        run.status = self._run_status(results, aborted)
        if aborted:
            run.notes = (run.notes or "") + f"aborted: {aborted}"
        self.sink.finish_run(run)
        elapsed = time.monotonic() - t0
        log.info(
            "run %s %s: %d searches (%d ok, %d error, %d blocked, %d skipped), %d page loads, %.0fs",
            run.run_id,
            run.status,
            len(results),
            run.searches_ok,
            run.searches_error,
            run.searches_blocked,
            run.searches_skipped,
            run.page_loads,
            elapsed,
        )
        return RunReport(run=run, results=results, elapsed_s=elapsed, aborted_reason=aborted)

    def _run_status(self, results: list[SearchResult], aborted: str | None) -> str:
        if aborted and "block" in aborted:
            return "blocked"
        attempted = [r for r in results if r.status != "skipped"]
        ok = [r for r in attempted if r.status in ("ok", "partial")]
        if not attempted:
            return "ok"  # nothing attempted (all skipped) is not a failure
        if len(ok) == len(attempted) and (not aborted or aborted.startswith("budget")):
            return "ok"  # stopping because the page-load budget is spent is the normal end of a run
        if not ok:
            return "failed"
        return "partial"
