"""`cli health` reads out/ (never Google): run age, status, drift alarm, stale cells; exit 1 if unhealthy."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from flight_scraper import cli
from flight_scraper.config import Settings

runner = CliRunner()


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(
            lambda c, env_file=None: Settings(
                out_dir=tmp_path / "out", artifacts_dir=tmp_path / "artifacts", logs_dir=tmp_path / "logs"
            )
        ),
    )
    (tmp_path / "out").mkdir()
    return tmp_path


def write_run(home: Path, *, status="ok", age_hours=1.0, searches=None, picks=3) -> Path:
    started = datetime.now(UTC) - timedelta(hours=age_hours)
    searches = searches if searches is not None else [{"status": "ok", "error": None}]
    payload = {
        "run": {"run_id": "r1", "started_at": started.isoformat(), "status": status, "page_loads": 9},
        "searches": [
            {"status": s["status"], "error": s["error"], "picks": {f"p{i}": {} for i in range(picks)}}
            for s in searches
        ],
    }
    path = home / "out" / "r1.json"
    path.write_text(json.dumps(payload))
    return path


def test_no_run_is_unhealthy(home: Path):
    result = runner.invoke(cli.app, ["health"])
    assert result.exit_code == 1 and "no run recorded" in result.output


def test_recent_ok_run_is_healthy(home: Path):
    write_run(home)
    result = runner.invoke(cli.app, ["health"])
    assert result.exit_code == 0, result.output
    assert "healthy" in result.output and "status=ok" in result.output and "never scraped" in result.output


def test_old_run_and_failed_status_are_problems(home: Path):
    write_run(home, status="failed", age_hours=72)
    result = runner.invoke(cli.app, ["health"])
    assert result.exit_code == 1
    assert "72 h old" in result.output and "status is failed" in result.output


def test_selector_drift_alarm(home: Path):
    err = "NoResultsParsed: no_results_parsed (best_load: 0 rows, 0 parsed)"
    write_run(home, searches=[{"status": "error", "error": err}] * 3, picks=0)
    result = runner.invoke(cli.app, ["health"])
    assert result.exit_code == 1 and "selector drift" in result.output


def test_stale_cells_are_a_warning_not_a_problem(home: Path):
    write_run(home)
    state = {
        "version": 1,
        "cells": {
            "google_flights:YUL-CDG:+60:1a": {
                "last_ok_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
                "last_attempt_at": None,
                "last_blocked_at": None,
            }
        },
    }
    (home / "out" / "rotation_state.json").write_text(json.dumps(state))
    result = runner.invoke(cli.app, ["health"])
    assert result.exit_code == 0 and "warning: 1 cells older than 45 days" in result.output


def test_prune_artifacts_removes_old_runs(home: Path):
    import os
    import time

    old = home / "artifacts" / "old-run" / "search"
    new = home / "artifacts" / "new-run"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    ancient = time.time() - 30 * 86400
    os.utime(old.parent, (ancient, ancient))
    result = runner.invoke(cli.app, ["prune-artifacts", "--days", "14"])
    assert result.exit_code == 0 and "removed 1" in result.output
    assert not old.parent.exists() and new.exists()


def test_run_daily_script_dry_run_passthrough(home: Path):
    """The wrapper builds `run --dry-run <args>` from FS_DRY_RUN=1 (checked statically: no browser here)."""
    script = Path(cli.__file__).resolve().parent.parent / "scripts" / "run_daily.sh"
    text = script.read_text()
    assert "FS_DRY_RUN" in text and "--dry-run" in text and "xvfb-run" in text and "exec python" in text
    assert (script.parent / "flight-scraper.timer").read_text().count("Persistent=true") == 1
    service = (script.parent / "flight-scraper.service").read_text()
    assert (
        "TZ=America/Toronto" in service and "TimeoutStartSec=45min" in service and "User=jfontaine" in service
    )
