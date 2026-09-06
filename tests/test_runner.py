"""Runner behaviour with a fake adapter (no browser): budget guard, retries, block breaker, sink errors."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from flight_scraper.adapters.base import BlockedError, NoResultsParsed
from flight_scraper.config import Settings, WatchList
from flight_scraper.db import DryRunSink, RunInfo
from flight_scraper.models import SearchResult
from flight_scraper.pacing import PageLoadBudget, Sleeper
from flight_scraper.runner import Runner
from flight_scraper.scheduler import FileRotationState
from tests.conftest import FakeGoogleAdapter


class RecordingSleeper(Sleeper):
    def __init__(self, budget):
        super().__init__(budget, clock=lambda s: None)
        self.labels: list[str] = []

    def _sleep_range(self, rng, label):
        self.labels.append(label)
        return 0.0


def make_runner(tmp_path: Path, watchlist: WatchList, adapter_cls=FakeGoogleAdapter, max_loads=40, sink=None):
    settings = Settings(out_dir=tmp_path / "out", artifacts_dir=tmp_path / "artifacts")
    sink = sink or DryRunSink(settings.out_dir)
    state = FileRotationState(settings.out_dir / "rotation_state.json")
    sleeper = RecordingSleeper(watchlist.budget)
    runner = Runner(
        settings,
        watchlist,
        sink,
        state,
        dry_run=True,
        page_budget=PageLoadBudget(max_loads),
        sleeper=sleeper,
        adapters={"google_flights": adapter_cls},
        now=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    )
    return runner, sleeper, state


def queries(watchlist: WatchList, n: int):
    from flight_scraper.config import expand_cells

    cells = expand_cells(watchlist)[:n]
    return [c.to_query(datetime(2026, 9, 6).date(), watchlist.defaults) for c in cells]


def test_budget_guard_stops_before_a_search_that_cannot_fit(tmp_path: Path, watchlist: WatchList):
    runner, sleeper, state = make_runner(tmp_path, watchlist, max_loads=40)
    report = runner.run(queries(watchlist, 6))
    assert len(report.results) == 4  # 4 x 9 = 36; the 5th needs 9 > 4 remaining
    assert report.run.page_loads == 36 and report.aborted_reason.startswith("budget")
    assert report.run.status == "ok" and report.exit_code == 0
    assert sleeper.labels.count("between_searches") == 3
    assert all(state.last_ok_at(q.cell_key) for q in queries(watchlist, 4))


def test_retry_once_on_no_results_then_error(tmp_path: Path, watchlist: WatchList):
    class Flaky(FakeGoogleAdapter):
        loads_per_search = 3
        fail_with = NoResultsParsed("no_results_parsed")

    runner, sleeper, _ = make_runner(tmp_path, watchlist, Flaky)
    report = runner.run(queries(watchlist, 1))
    r = report.results[0]
    assert r.status == "error" and "no_results_parsed" in (r.error or "") and r.attempts == 2
    assert sleeper.labels.count("retry_pause") == 1
    assert report.run.page_loads == 6 and report.run.status == "failed" and report.exit_code == 3


def test_retry_succeeds_second_time(tmp_path: Path, watchlist: WatchList):
    class FlakyOnce(FakeGoogleAdapter):
        loads_per_search = 3
        attempts = 0

        def run_search(self, page, query):
            FlakyOnce.attempts += 1
            self.fail_with = NoResultsParsed("no_results_parsed") if FlakyOnce.attempts == 1 else None
            return super().run_search(page, query)

    runner, _, _ = make_runner(tmp_path, watchlist, FlakyOnce)
    report = runner.run(queries(watchlist, 1))
    assert report.results[0].status == "ok" and report.results[0].attempts == 2


def test_blocked_is_never_retried_and_breaker_aborts_run(tmp_path: Path, watchlist: WatchList):
    class Blocked(FakeGoogleAdapter):
        loads_per_search = 1
        fail_with = BlockedError("http 429")

    runner, sleeper, state = make_runner(tmp_path, watchlist, Blocked)
    report = runner.run(queries(watchlist, 5))
    assert len(report.results) == 2  # abort_after_consecutive_blocks = 2
    assert all(r.blocked and r.status == "blocked" and r.attempts == 1 for r in report.results)
    assert report.run.status == "blocked" and report.exit_code == 2
    assert sleeper.labels.count("block_pause") == 1 and "retry_pause" not in sleeper.labels
    assert state.blocked_recently(report.results[0].query.cell_key, datetime(2026, 9, 6, 13, tzinfo=UTC))


def test_generic_exception_is_recorded_not_retried(tmp_path: Path, watchlist: WatchList):
    class Broken(FakeGoogleAdapter):
        loads_per_search = 2
        fail_with = RuntimeError("selector exploded")

    runner, sleeper, _ = make_runner(tmp_path, watchlist, Broken)
    report = runner.run(queries(watchlist, 2))
    assert [r.status for r in report.results] == ["error", "error"]
    assert "RuntimeError: selector exploded" in report.results[0].error
    assert "retry_pause" not in sleeper.labels and report.run.status == "failed"


def test_sink_error_does_not_abort_run_and_is_noted(tmp_path: Path, watchlist: WatchList):
    class FailingSink(DryRunSink):
        def write_search(self, result: SearchResult) -> int | None:
            raise ConnectionError("supabase down")

    runner, _, _ = make_runner(tmp_path, watchlist, sink=FailingSink(tmp_path / "out"))
    report = runner.run(queries(watchlist, 2))
    assert len(report.results) == 2 and "sink error" in (report.run.notes or "")
    assert report.run.status == "ok"


def test_disabled_source_is_skipped_without_sleeping(tmp_path: Path, watchlist: WatchList):
    from flight_scraper.adapters import REGISTRY

    settings = Settings(out_dir=tmp_path / "out")
    runner = Runner(
        settings,
        watchlist,
        DryRunSink(settings.out_dir),
        FileRotationState(settings.out_dir / "rotation_state.json"),
        page_budget=PageLoadBudget(40),
        sleeper=RecordingSleeper(watchlist.budget),
        adapters=REGISTRY,
    )
    q = queries(watchlist, 1)[0].model_copy(update={"source_id": "kayak"})
    report = runner.run([q])
    assert report.results[0].status == "skipped" and "SourceDisabled" in report.results[0].error
    assert report.run.page_loads == 0 and report.run.status == "ok"
    assert runner.sleeper.labels == []  # type: ignore[attr-defined]


def test_run_info_roundtrip():
    info = RunInfo(
        run_id="x", started_at=datetime(2026, 9, 6, tzinfo=UTC), scrape_date=datetime(2026, 9, 6).date()
    )
    assert RunInfo.model_validate(info.model_dump(mode="json")) == info


@pytest.mark.parametrize("exc", [NoResultsParsed("x"), TimeoutError("y")])
def test_is_retryable(exc):
    from flight_scraper.runner import is_retryable

    assert is_retryable(exc)
