from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
import yaml

from flight_scraper.config import CellFilters, Settings, WatchList, expand_cells, filter_cells


def test_seed_watchlist_loads(watchlist: WatchList):
    assert watchlist.origins == ["YQB", "YUL"]
    assert [d.code for d in watchlist.destinations] == ["YYZ", "YVR", "FLL", "MCO", "CUN", "CDG"]
    assert len(watchlist.resolved_routes()) == 12
    assert [p.key for p in watchlist.passenger_configs] == ["1a", "2a", "1a1c", "1a2c"]
    assert [p.priority for p in watchlist.passenger_configs] == [3, 2, 1, 1]
    assert all(p.child_ages == [] for p in watchlist.passenger_configs)
    assert watchlist.budget.max_page_loads_per_run == 40
    assert watchlist.budget.booking_visits == "all"
    assert watchlist.budget.abort_after_consecutive_blocks == 2
    assert watchlist.sources == ["google_flights"]


def test_expand_cells_144(watchlist: WatchList):
    cells = expand_cells(watchlist)
    assert len(cells) == 144
    assert len({c.key for c in cells}) == 144
    q = cells[0].to_query(date(2026, 9, 4), watchlist.defaults)
    assert q.cell_key == cells[0].key
    assert q.depart_date.weekday() == 5 and q.return_date == q.depart_date.replace(day=q.depart_date.day + 7)
    assert q.pax.child_ages == []


def test_filters(watchlist: WatchList):
    cells = expand_cells(watchlist)
    assert len(filter_cells(cells, CellFilters(route="yul-cdg"))) == 12
    assert len(filter_cells(cells, CellFilters(route="YUL-CDG", pax="1a"))) == 3
    assert len(filter_cells(cells, CellFilters(route="YUL-CDG", pax="1a", offset=60))) == 1
    assert len(filter_cells(cells, CellFilters(source="kayak"))) == 0
    assert filter_cells(cells, None) == cells


def test_explicit_routes_and_validation(tmp_path: Path):
    data = yaml.safe_load(Path("config/watchlist.yaml").read_text())
    data["routes"] = [
        {"origin": "YUL", "destination": "CDG"},
        {"origin": "YQB", "destination": "CDG", "active": False},
    ]
    wl = WatchList.model_validate(data)
    assert [r.key for r in wl.resolved_routes()] == ["YUL-CDG"]

    bad = dict(data)
    bad["origins"] = ["yul"]
    with pytest.raises(ValueError):
        WatchList.model_validate(bad)
    bad = dict(data)
    bad["defaults"] = dict(data["defaults"], offsets_days=[0])
    with pytest.raises(ValueError):
        WatchList.model_validate(bad)
    bad = dict(data)
    bad["passenger_configs"] = [{"key": "9a", "adults": 10}]
    with pytest.raises(ValueError):
        WatchList.model_validate(bad)


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "FS_BROWSER_ENGINE", "FS_HEADED", "FS_MAX_PAGE_LOADS"):
        monkeypatch.delenv(k, raising=False)
    s = Settings.from_env(env_file=tmp_path / "missing.env")
    assert not s.has_supabase and s.browser_engine == "playwright" and not s.headed
    monkeypatch.setenv("SUPABASE_URL", "https://abcd1234.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_x")
    monkeypatch.setenv("FS_BROWSER_ENGINE", "patchright")
    monkeypatch.setenv("FS_HEADED", "1")
    monkeypatch.setenv("FS_MAX_PAGE_LOADS", "12")
    s = Settings.from_env(env_file=tmp_path / "missing.env")
    assert s.has_supabase and s.supabase_project_ref == "abcd1234"
    assert s.browser_engine == "patchright" and s.headed and s.max_page_loads_override == 12
    monkeypatch.setenv("FS_BROWSER_ENGINE", "selenium")
    with pytest.raises(ValueError):
        Settings.from_env(env_file=tmp_path / "missing.env")
    assert "sb_secret" not in (s.supabase_project_ref or "")
    assert os.environ.get("SUPABASE_SERVICE_KEY") == "sb_secret_x"  # never printed, only read
