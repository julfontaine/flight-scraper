"""Sinks: where run/search/itinerary records go.

* ``DryRunSink`` — always available; writes ``out/<run_id>.json`` (run header + searches + picks).
* ``SupabaseSink`` — Phase 3 (idempotent upserts); a clearly named stub until then.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .models import SearchResult

log = logging.getLogger(__name__)


class RunInfo(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    git_sha: str | None = None
    host: str | None = None
    status: str = "running"  # running | ok | partial | blocked | failed
    page_loads: int = 0
    searches_total: int = 0
    searches_ok: int = 0
    searches_blocked: int = 0
    searches_error: int = 0
    searches_skipped: int = 0
    notes: str | None = None
    scrape_date: date
    dry_run: bool = True
    sources: list[str] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)


def git_sha(root: Path | None = None) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def hostname() -> str:
    return os.environ.get("HOSTNAME") or platform.node() or "unknown"


class Sink(Protocol):
    def start_run(self, run: RunInfo) -> None: ...

    def write_search(self, result: SearchResult) -> int | None: ...

    def finish_run(self, run: RunInfo) -> None: ...


def result_to_json(result: SearchResult) -> dict[str, Any]:
    data = result.model_dump(mode="json")
    data["query"]["cell_key"] = result.query.cell_key
    data["query"]["search_key"] = result.query.search_key
    return data


class DryRunSink:
    """Accumulates results and writes ``out/<run_id>.json``; flushed after every search for crash-safety."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = Path(out_dir)
        self.run: RunInfo | None = None
        self.results: list[SearchResult] = []
        self.path: Path | None = None

    def start_run(self, run: RunInfo) -> None:
        self.run = run
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.out_dir / f"{run.run_id}.json"
        self._flush()

    def write_search(self, result: SearchResult) -> int | None:
        self.results.append(result)
        self._flush()
        return len(self.results)  # pseudo search id (1-based position in the file)

    def finish_run(self, run: RunInfo) -> None:
        self.run = run
        self._flush()
        log.info("dry-run output written to %s", self.path)

    def _flush(self) -> None:
        if self.run is None or self.path is None:
            return
        payload = {
            "run": self.run.model_dump(mode="json"),
            "searches": [result_to_json(r) for r in self.results],
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)


class SupabaseSink:
    """Phase 3 deliverable — see plan phase 3. Instantiating it before then is a programming error."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("SupabaseSink lands in Phase 3; use DryRunSink (--dry-run)")


def utcnow() -> datetime:
    return datetime.now(UTC)
