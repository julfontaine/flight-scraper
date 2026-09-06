"""Rotation: which cells to scrape tonight (weighted oldest-first) and where their last-ok time lives."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from .config import Budget, Cell, CellFilters, Defaults, filter_cells
from .models import SearchQuery

log = logging.getLogger(__name__)


class RotationState(Protocol):
    def last_ok_at(self, cell_key: str) -> datetime | None: ...

    def mark(self, cell_key: str, ok: bool, at: datetime) -> None: ...

    def blocked_recently(self, cell_key: str, now: datetime | None = None) -> bool: ...


class MemoryRotationState:
    """In-memory state (tests, simulations)."""

    def __init__(self) -> None:
        self.ok: dict[str, datetime] = {}
        self.attempt: dict[str, datetime] = {}

    def last_ok_at(self, cell_key: str) -> datetime | None:
        return self.ok.get(cell_key)

    def mark(self, cell_key: str, ok: bool, at: datetime) -> None:
        self.attempt[cell_key] = at
        if ok:
            self.ok[cell_key] = at

    def blocked_recently(self, cell_key: str, now: datetime | None = None) -> bool:
        return False


class FileRotationState(MemoryRotationState):
    """``out/rotation_state.json`` — the only mutable local state; written atomically (tmp + rename)."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.blocked: dict[str, datetime] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("rotation state unreadable (%s); starting empty", exc)
            return
        for key, rec in data.get("cells", {}).items():
            if rec.get("last_ok_at"):
                self.ok[key] = datetime.fromisoformat(rec["last_ok_at"])
            if rec.get("last_attempt_at"):
                self.attempt[key] = datetime.fromisoformat(rec["last_attempt_at"])
            if rec.get("last_blocked_at"):
                self.blocked[key] = datetime.fromisoformat(rec["last_blocked_at"])

    def mark(self, cell_key: str, ok: bool, at: datetime, blocked: bool = False) -> None:
        super().mark(cell_key, ok, at)
        if blocked:
            self.blocked[cell_key] = at
        self.save()

    def blocked_recently(self, cell_key: str, now: datetime | None = None, days: int = 2) -> bool:
        at = self.blocked.get(cell_key)
        if at is None:
            return False
        now = now or datetime.now(UTC)
        return (now - at).total_seconds() < days * 86400

    def save(self) -> None:
        keys = set(self.ok) | set(self.attempt) | set(self.blocked)
        payload = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "cells": {
                k: {
                    "last_ok_at": self.ok[k].isoformat() if k in self.ok else None,
                    "last_attempt_at": self.attempt[k].isoformat() if k in self.attempt else None,
                    "last_blocked_at": self.blocked[k].isoformat() if k in self.blocked else None,
                }
                for k in sorted(keys)
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def score_cell(cell: Cell, state: RotationState, now: datetime) -> tuple[int, float]:
    """(never_scraped, priority x days_since_last_ok); higher sorts first."""
    last = state.last_ok_at(cell.key)
    if last is None:
        return (1, float(cell.priority))
    days = max((_as_aware(now) - _as_aware(last)).total_seconds() / 86400.0, 0.0)
    return (0, cell.priority * days)


def rank_cells(
    cells: list[Cell], state: RotationState, now: datetime
) -> list[tuple[Cell, tuple[int, float]]]:
    scored = [(c, score_cell(c, state, now)) for c in cells if not state.blocked_recently(c.key, now)]
    # stable: ties keep watch-list order (route, offset, pax)
    scored.sort(key=lambda t: (t[1][0], t[1][1]), reverse=True)
    return scored


def plan_run(
    cells: list[Cell],
    state: RotationState,
    budget: Budget,
    now: datetime,
    filters: CellFilters | None = None,
    defaults: Defaults | None = None,
    run_date: date | None = None,
    limit: int | None = None,
) -> list[SearchQuery]:
    """Never-scraped first, then priority x days_since_last_ok desc, capped by budget and search cap."""
    defaults = defaults or Defaults()
    run_date = run_date or now.date()
    cap = min(budget.max_searches_per_run, budget.max_searches_by_loads)
    if limit is not None:
        cap = min(cap, limit)
    selected = rank_cells(filter_cells(cells, filters), state, now)[:cap]
    return [cell.to_query(run_date, defaults) for cell, _score in selected]


def explain_plan(
    cells: list[Cell], state: RotationState, budget: Budget, now: datetime, filters: CellFilters | None = None
) -> list[dict]:
    cap = min(budget.max_searches_per_run, budget.max_searches_by_loads)
    rows = []
    for i, (cell, (never, score)) in enumerate(rank_cells(filter_cells(cells, filters), state, now)):
        last = state.last_ok_at(cell.key)
        rows.append(
            {
                "rank": i + 1,
                "selected": i < cap,
                "cell": cell.key,
                "priority": cell.priority,
                "never_scraped": bool(never),
                "score": round(score, 2),
                "last_ok_at": last.isoformat() if last else None,
            }
        )
    return rows
