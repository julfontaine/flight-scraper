from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from flight_scraper import cli
from flight_scraper.config import Settings

runner = CliRunner()


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point out/ and artifacts/ at tmp and make sure no Supabase creds leak in from a real .env."""
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "FS_MAX_PAGE_LOADS"):
        monkeypatch.delenv(k, raising=False)

    def fake_from_env(cls=None, env_file=None):
        return Settings(
            out_dir=tmp_path / "out", artifacts_dir=tmp_path / "artifacts", profiles_dir=tmp_path / "p"
        )

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls, env_file=None: fake_from_env()))
    return tmp_path


def test_sources_lists_nine_with_reasons():
    result = runner.invoke(cli.app, ["sources"])
    assert result.exit_code == 0, result.output
    lines = [line for line in result.output.splitlines() if line and not line.startswith("id ")]
    assert len(lines) == 9
    assert lines[0].startswith("google_flights") and " yes " in lines[0]
    assert sum(" no " in line for line in lines) == 8
    assert "Research: finding category=westjet" in result.output


def test_watchlist_lists_144_cells(isolated: Path):
    result = runner.invoke(cli.app, ["watchlist", "--run-date", "2026-09-04"])
    assert result.exit_code == 0, result.output
    assert "= 144 cells" in result.output
    assert "google_flights:YUL-CDG:+60:1a" in result.output
    assert "2026-11-07 -> 2026-11-14" in result.output  # +60 from 2026-09-04 snapped to Saturday


def test_plan_prints_at_most_5_searches_at_40_loads(isolated: Path):
    result = runner.invoke(cli.app, ["plan", "--explain"])
    assert result.exit_code == 0, result.output
    assert "-> 4 searches planned" in result.output
    assert "budget 40 loads" in result.output
    assert "score=" in result.output


@pytest.fixture
def no_browser(monkeypatch: pytest.MonkeyPatch):
    """Fake Google adapter + null browser session: the full CLI pipeline without Playwright or network."""
    import contextlib

    import flight_scraper.browser as browser
    import flight_scraper.runner as runner_mod
    from tests.conftest import FakeGoogleAdapter

    @contextlib.contextmanager
    def null_context(settings, source_id):
        yield None

    monkeypatch.setattr(browser, "open_context", null_context)
    monkeypatch.setattr(
        runner_mod, "REGISTRY", dict(runner_mod.REGISTRY) | {"google_flights": FakeGoogleAdapter}
    )


def test_run_dry_run_end_to_end_records_phase_state(isolated: Path, no_browser):
    result = runner.invoke(
        cli.app,
        [
            "run",
            "--dry-run",
            "--source",
            "google_flights",
            "--route",
            "YUL-CDG",
            "--pax",
            "1a",
            "--offset",
            "60",
        ],
    )
    assert result.exit_code == 0, result.output
    files = list((isolated / "out").glob("*.json"))
    files = [f for f in files if f.name != "rotation_state.json"]
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["run"]["dry_run"] is True and data["run"]["status"] in ("ok", "failed", "partial")
    assert len(data["searches"]) == 1
    s = data["searches"][0]
    assert s["query"]["cell_key"] == "google_flights:YUL-CDG:+60:1a"
    assert s["query"]["pax"]["child_ages"] == []
    assert s["status"] == "ok" and set(s["picks"]) == {"best", "cheapest", "fastest"}
    assert s["picks"]["best"]["price_stage"] == "booking" and s["picks"]["best"]["luggage_source"]
    assert data["run"]["page_loads"] == 9
    state = json.loads((isolated / "out" / "rotation_state.json").read_text())
    assert state["cells"]["google_flights:YUL-CDG:+60:1a"]["last_ok_at"]


def test_run_without_credentials_falls_back_to_dry_run(isolated: Path):
    result = runner.invoke(cli.app, ["run", "--source", "kayak", "--limit", "1"])
    assert result.exit_code == 0, result.output  # all skipped → nothing attempted
    assert "falling back to --dry-run" in result.output or "dry-run" in result.output.lower()
    files = [f for f in (isolated / "out").glob("*.json") if f.name != "rotation_state.json"]
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["searches"][0]["status"] == "skipped" and "SourceDisabled" in data["searches"][0]["error"]


def test_run_no_matching_cells(isolated: Path):
    result = runner.invoke(cli.app, ["run", "--dry-run", "--route", "YUL-XXX"])
    assert result.exit_code == 0 and "nothing to do" in result.output


def test_run_with_credentials_uses_supabase_sink_and_state(isolated: Path, no_browser, monkeypatch):
    """Credentials + not --dry-run → SupabaseSink (JSON companion kept) + rotation state from the view."""
    from tests.test_db_sink import FakeSupabase

    fake = FakeSupabase()
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(
            lambda c, env_file=None: Settings(
                supabase_url="https://abcdefgh.supabase.co",
                supabase_service_key="sb_secret_x",
                out_dir=isolated / "out",
                artifacts_dir=isolated / "artifacts",
            )
        ),
    )
    monkeypatch.setattr(cli, "_supabase_client", lambda settings: fake)
    result = runner.invoke(
        cli.app, ["run", "--source", "google_flights", "--route", "YUL-CDG", "--pax", "1a", "--offset", "60"]
    )
    assert result.exit_code == 0, result.output
    assert "upserted into supabase:abcdefgh" in result.output and "sb_secret" not in result.output
    tables = [c[0] for c in fake.calls]
    assert "cell_last_scraped" in tables and "search_runs" in tables and "searches" in tables
    assert "itineraries" in tables and len(fake.itineraries) == 3
    files = [f for f in (isolated / "out").glob("*.json") if f.name != "rotation_state.json"]
    assert len(files) == 1  # companion JSON still written


def test_db_check_without_credentials_exits_1(isolated: Path):
    result = runner.invoke(cli.app, ["db-check"])
    assert result.exit_code == 1 and "not set" in result.output


def test_run_with_database_url_uses_postgres_sink_and_state(isolated: Path, no_browser, monkeypatch):
    """DATABASE_URL + not --dry-run → PostgresSink (JSON companion kept) + rotation state from the view."""
    from tests.test_db_postgres import FakePg

    fake = FakePg()
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(
            lambda c, env_file=None: Settings(
                database_url="postgres://scraper:s3cret@localhost:5433/flights",
                supabase_url="https://abcdefgh.supabase.co",  # both set: DATABASE_URL wins
                supabase_service_key="sb_secret_x",
                out_dir=isolated / "out",
                artifacts_dir=isolated / "artifacts",
            )
        ),
    )
    monkeypatch.setattr(cli, "_pg_conn", lambda settings: fake)
    monkeypatch.setattr(
        cli, "_supabase_client", lambda settings: pytest.fail("Supabase client must not be used")
    )
    result = runner.invoke(
        cli.app, ["run", "--source", "google_flights", "--route", "YUL-CDG", "--pax", "1a", "--offset", "60"]
    )
    assert result.exit_code == 0, result.output
    assert "upserted into postgres://scraper@localhost:5433/flights" in result.output
    assert "s3cret" not in result.output
    sql = " ".join(s.lower() for s, _ in fake.calls)
    assert (
        "from cell_last_scraped" in sql and "insert into search_runs" in sql and "insert into searches" in sql
    )
    assert len(fake.itineraries) == 3
    files = [f for f in (isolated / "out").glob("*.json") if f.name != "rotation_state.json"]
    assert len(files) == 1


def test_db_check_with_database_url(isolated: Path, monkeypatch):
    from tests.test_db_postgres import FakePg

    fake = FakePg()
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda c, env_file=None: Settings(database_url="postgres://u:pw@h:5433/flights")),
    )
    monkeypatch.setattr(cli, "_pg_conn", lambda settings: fake)
    result = runner.invoke(cli.app, ["db-check"])
    assert result.exit_code == 0, result.output
    assert (
        "postgres://u@h:5433/flights" in result.output and "pw" not in result.output.split("flights")[0][-4:]
    )
    assert "sources" in result.output and "no runs yet" in result.output
