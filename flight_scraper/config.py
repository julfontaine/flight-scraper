"""Settings (environment) and the watch-list model (config/watchlist.yaml)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

from .dates import resolve_dates
from .models import PaxConfig, SearchQuery

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WATCHLIST = PROJECT_ROOT / "config" / "watchlist.yaml"
IATA_RE = re.compile(r"^[A-Z]{3}$")


# ------------------------------------------------------------------ environment settings
@dataclass
class Settings:
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    browser_engine: Literal["playwright", "patchright"] = "playwright"
    headed: bool = False
    max_page_loads_override: int | None = None
    log_level: str = "INFO"
    project_root: Path = PROJECT_ROOT
    out_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "out")
    artifacts_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "artifacts")
    profiles_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "profiles")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def supabase_project_ref(self) -> str | None:
        """Only ever print this, never the key."""
        if not self.supabase_url:
            return None
        m = re.match(r"https?://([a-z0-9-]+)\.", self.supabase_url)
        return m.group(1) if m else self.supabase_url

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> Settings:
        load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
        engine = os.environ.get("FS_BROWSER_ENGINE", "playwright").strip().lower()
        if engine not in ("playwright", "patchright"):
            raise ValueError(f"FS_BROWSER_ENGINE must be playwright|patchright, got {engine!r}")
        override = os.environ.get("FS_MAX_PAGE_LOADS")
        return cls(
            supabase_url=os.environ.get("SUPABASE_URL") or None,
            supabase_service_key=os.environ.get("SUPABASE_SERVICE_KEY") or None,
            browser_engine=engine,  # type: ignore[arg-type]
            headed=os.environ.get("FS_HEADED", "0") in ("1", "true", "yes"),
            max_page_loads_override=int(override) if override else None,
            log_level=os.environ.get("FS_LOG_LEVEL", "INFO").upper(),
        )


# ------------------------------------------------------------------ watch-list model
class Defaults(BaseModel):
    cabin: str = "economy"
    currency: str = "CAD"
    stay_nights: int = Field(default=7, gt=0)
    date_rule: Literal["next_saturday", "exact"] = "next_saturday"
    offsets_days: list[int] = Field(default_factory=lambda: [30, 60, 90])

    @field_validator("offsets_days")
    @classmethod
    def _offsets_positive(cls, v: list[int]) -> list[int]:
        if not v or any(o <= 0 for o in v):
            raise ValueError("offsets_days must be a non-empty list of positive integers")
        return v


class Destination(BaseModel):
    code: str
    region: str | None = None
    why: str | None = None

    @field_validator("code")
    @classmethod
    def _iata(cls, v: str) -> str:
        if not IATA_RE.match(v):
            raise ValueError(f"invalid IATA code {v!r}")
        return v


class Route(BaseModel):
    origin: str
    destination: str
    active: bool = True

    @field_validator("origin", "destination")
    @classmethod
    def _iata(cls, v: str) -> str:
        if not IATA_RE.match(v):
            raise ValueError(f"invalid IATA code {v!r}")
        return v

    @property
    def key(self) -> str:
        return f"{self.origin}-{self.destination}"


class Delays(BaseModel):
    between_actions: tuple[float, float] = (2, 5)
    between_loads: tuple[float, float] = (4, 9)
    between_searches: tuple[float, float] = (20, 45)


class Retry(BaseModel):
    per_search_attempts: int = Field(default=2, ge=1)
    retry_pause_s: tuple[float, float] = (15, 30)


class Budget(BaseModel):
    max_page_loads_per_run: int = Field(default=40, ge=1)
    est_page_loads_per_search: int = Field(default=9, ge=1)
    max_searches_per_run: int = Field(default=8, ge=1)
    booking_visits: Literal["all", "best_only", "none"] = "all"
    delays_s: Delays = Field(default_factory=Delays)
    retry: Retry = Field(default_factory=Retry)
    block_pause_s: tuple[float, float] = (60, 120)
    abort_after_consecutive_blocks: int = Field(default=2, ge=1)

    @property
    def max_searches_by_loads(self) -> int:
        return self.max_page_loads_per_run // self.est_page_loads_per_search


class Rotation(BaseModel):
    strategy: Literal["weighted_oldest_first"] = "weighted_oldest_first"
    state: Literal["supabase", "file"] = "supabase"


class WatchList(BaseModel):
    version: int = 1
    defaults: Defaults = Field(default_factory=Defaults)
    origins: list[str] = Field(default_factory=list)
    destinations: list[Destination] = Field(default_factory=list)
    routes: Literal["all"] | list[Route] = "all"
    passenger_configs: list[PaxConfig] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    rotation: Rotation = Field(default_factory=Rotation)
    sources: list[str] = Field(default_factory=lambda: ["google_flights"])

    @field_validator("origins")
    @classmethod
    def _origins(cls, v: list[str]) -> list[str]:
        for code in v:
            if not IATA_RE.match(code):
                raise ValueError(f"invalid IATA origin {code!r}")
        return v

    @model_validator(mode="after")
    def _check(self) -> WatchList:
        if not self.passenger_configs:
            raise ValueError("passenger_configs must not be empty")
        keys = [p.key for p in self.passenger_configs]
        if len(set(keys)) != len(keys):
            raise ValueError("passenger_configs keys must be unique")
        if self.routes == "all" and (not self.origins or not self.destinations):
            raise ValueError("routes: all requires origins and destinations")
        return self

    def resolved_routes(self) -> list[Route]:
        if self.routes == "all":
            return [Route(origin=o, destination=d.code) for o in self.origins for d in self.destinations]
        return [r for r in self.routes if r.active]

    def pax_by_key(self, key: str) -> PaxConfig:
        for p in self.passenger_configs:
            if p.key == key:
                return p
        raise KeyError(f"unknown passenger config {key!r}")

    @classmethod
    def load(cls, path: Path | None = None) -> WatchList:
        path = path or DEFAULT_WATCHLIST
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)


# ------------------------------------------------------------------ cells
class Cell(BaseModel):
    """One rotation unit: source x route x offset x pax (dates resolved per run)."""

    source_id: str
    origin: str
    destination: str
    offset_days: int
    pax: PaxConfig
    cabin: str = "economy"
    currency: str = "CAD"

    @property
    def key(self) -> str:
        return f"{self.source_id}:{self.origin}-{self.destination}:+{self.offset_days}:{self.pax.key}"

    @property
    def route_key(self) -> str:
        return f"{self.origin}-{self.destination}"

    @property
    def priority(self) -> int:
        return self.pax.priority

    def to_query(self, run_date: date, defaults: Defaults) -> SearchQuery:
        depart, ret = resolve_dates(run_date, self.offset_days, defaults.stay_nights, defaults.date_rule)
        return SearchQuery(
            source_id=self.source_id,
            origin=self.origin,
            destination=self.destination,
            depart_date=depart,
            return_date=ret,
            offset_days=self.offset_days,
            pax=self.pax,
            cabin=self.cabin,
            currency=self.currency,
        )


def expand_cells(watchlist: WatchList, sources: list[str] | None = None) -> list[Cell]:
    """route x offset x pax x source, in a stable order."""
    out: list[Cell] = []
    for source_id in sources or watchlist.sources:
        for route in watchlist.resolved_routes():
            for offset in watchlist.defaults.offsets_days:
                for pax in watchlist.passenger_configs:
                    out.append(
                        Cell(
                            source_id=source_id,
                            origin=route.origin,
                            destination=route.destination,
                            offset_days=offset,
                            pax=pax,
                            cabin=watchlist.defaults.cabin,
                            currency=watchlist.defaults.currency,
                        )
                    )
    return out


@dataclass
class CellFilters:
    """CLI filters that narrow the cell set before ranking."""

    source: str | None = None
    route: str | None = None  # 'YUL-CDG'
    pax: str | None = None  # '1a'
    offset: int | None = None

    def matches(self, cell: Cell) -> bool:
        if self.source and cell.source_id != self.source:
            return False
        if self.route and cell.route_key != self.route.upper():
            return False
        if self.pax and cell.pax.key != self.pax:
            return False
        return not (self.offset is not None and cell.offset_days != self.offset)


def filter_cells(cells: list[Cell], filters: CellFilters | None) -> list[Cell]:
    if filters is None:
        return list(cells)
    return [c for c in cells if filters.matches(c)]
