"""Sinks: where run/search/itinerary records go.

* ``DryRunSink`` — always available; writes ``out/<run_id>.json`` (run header + searches + picks).
* ``SupabaseSink`` — idempotent upserts (searches on the natural key + scrape_date, itineraries on
  (search_id, pick)); wraps a ``DryRunSink`` companion so the JSON file is always written too.
* ``SupabaseRotationState`` — rotation state read from the ``cell_last_scraped`` view.
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


SEARCH_ON_CONFLICT = "source_id,route_id,depart_date,return_date,adults,children,child_ages,cabin,scrape_date"
ITINERARY_ON_CONFLICT = "search_id,pick"


def _iso(dt: datetime | date | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def search_row(result: SearchResult, run_id: str, route_id: int, scrape_date: date) -> dict[str, Any]:
    q = result.query
    return {
        "run_id": run_id,
        "source_id": q.source_id,
        "route_id": route_id,
        "depart_date": q.depart_date.isoformat(),
        "return_date": q.return_date.isoformat(),
        "offset_days": q.offset_days,
        "adults": q.pax.adults,
        "children": q.pax.children,
        "child_ages": list(q.pax.child_ages),  # [] never null: part of the unique key
        "cabin": q.cabin,
        "scrape_date": scrape_date.isoformat(),
        "status": result.status,
        "error": result.error,
        "blocked": result.blocked,
        "page_url": result.page_url,
        "page_loads": result.page_loads,
        "started_at": _iso(result.started_at),
        "finished_at": _iso(result.finished_at),
    }


def itinerary_rows(result: SearchResult, search_id: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pick, it in result.picks.items():
        inbound = it.inbound
        raw = dict(it.raw)
        raw["outbound"] = it.outbound.model_dump(mode="json")
        if inbound is not None:
            raw["inbound"] = inbound.model_dump(mode="json")
        raw["providers"] = [p.model_dump() for p in it.providers]
        raw["candidate_source"], raw["row_index"], raw["results_url"] = (
            it.candidate_source,
            it.row_index,
            it.results_url,
        )
        rows.append(
            {
                "search_id": search_id,
                "pick": pick.value if hasattr(pick, "value") else str(pick),
                "pick_rule": it.pick_rule,
                "airlines": list(it.airlines),
                "flight_numbers": list(it.flight_numbers),
                "outbound_depart_local": _iso(it.outbound.depart_local),
                "outbound_arrive_local": _iso(it.outbound.arrive_local),
                "return_depart_local": _iso(inbound.depart_local) if inbound else None,
                "return_arrive_local": _iso(inbound.arrive_local) if inbound else None,
                "outbound_duration_min": it.outbound.duration_min,
                "return_duration_min": inbound.duration_min if inbound else None,
                "duration_min": it.duration_min,
                "stops": it.stops,
                "return_stops": it.return_stops,
                "fare_family": it.fare_family,
                "price_total_cad": it.price_total_cad,
                "price_results_cad": it.price_results_cad,
                "price_provider": it.price_provider,
                "price_stage": it.price_stage.value,
                "currency_raw": it.currency_raw,
                "carry_on_included": it.carry_on_included,
                "carry_on_fee_cad": it.carry_on_fee_cad,
                "checked_bag_fee_cad": it.checked_bag_fee_cad,
                "luggage_source": it.luggage_source,
                "price_insight": it.price_insight,
                "deep_link_url": it.deep_link_url,
                "raw": raw,
            }
        )
    return rows


class SupabaseSink:
    """Idempotent upserts into Supabase (service-role key bypasses RLS).

    ``searches`` upserts on the natural key + ``scrape_date`` (same-day re-runs overwrite, other days
    accumulate history) and returns the id; ``itineraries`` upsert on ``(search_id, pick)``.
    ``search_runs`` is inserted at start and updated at the end. A ``DryRunSink`` companion always keeps
    the JSON file so a failed night can be replayed."""

    def __init__(
        self, client: Any, scrape_date: date | None = None, companion: DryRunSink | None = None
    ) -> None:
        self.client = client
        self.scrape_date = scrape_date
        self.companion = companion
        self.run: RunInfo | None = None
        self._routes: dict[tuple[str, str], int] = {}

    @classmethod
    def from_settings(cls, settings: Any, companion: DryRunSink | None = None) -> SupabaseSink:
        from supabase import create_client  # lazy: keep the import off the dry-run path

        if not settings.has_supabase:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY are not set")
        client = create_client(settings.supabase_url, settings.supabase_service_key)
        return cls(client, companion=companion)

    # ---- helpers ----------------------------------------------------------------------------
    def route_id(self, origin: str, destination: str) -> int:
        key = (origin, destination)
        if key not in self._routes:
            resp = self.client.table("routes").select("id,origin,destination").execute()
            for row in resp.data or []:
                self._routes[(row["origin"], row["destination"])] = int(row["id"])
        if key not in self._routes:  # route added to the watch-list but not to the DB: create it
            self.client.table("routes").upsert(
                {"origin": origin, "destination": destination}, on_conflict="origin,destination"
            ).execute()
            resp = (
                self.client.table("routes")
                .select("id")
                .eq("origin", origin)
                .eq("destination", destination)
                .execute()
            )
            if not resp.data:
                raise RuntimeError(f"route {origin}-{destination} could not be created")
            self._routes[key] = int(resp.data[0]["id"])
        return self._routes[key]

    # ---- Sink protocol ----------------------------------------------------------------------
    def start_run(self, run: RunInfo) -> None:
        self.run = run
        if self.scrape_date is None:
            self.scrape_date = run.scrape_date
        if self.companion is not None:
            self.companion.start_run(run)
        self.client.table("search_runs").insert(
            {
                "run_id": run.run_id,
                "started_at": run.started_at.isoformat(),
                "git_sha": run.git_sha,
                "host": run.host,
                "status": "running",
                "searches_total": run.searches_total,
            }
        ).execute()

    def write_search(self, result: SearchResult) -> int | None:
        if self.companion is not None:
            self.companion.write_search(result)
        assert self.run is not None, "start_run() first"
        assert self.scrape_date is not None
        rid = self.route_id(result.query.origin, result.query.destination)
        row = search_row(result, self.run.run_id, rid, self.scrape_date)
        resp = (
            self.client.table("searches")
            .upsert(row, on_conflict=SEARCH_ON_CONFLICT, returning="representation")
            .execute()
        )
        if not resp.data:
            raise RuntimeError("searches upsert returned no row (is the migration applied?)")
        search_id = int(resp.data[0]["id"])
        rows = itinerary_rows(result, search_id)
        for i in range(0, len(rows), 500):
            self.client.table("itineraries").upsert(
                rows[i : i + 500], on_conflict=ITINERARY_ON_CONFLICT, returning="minimal"
            ).execute()
        return search_id

    def finish_run(self, run: RunInfo) -> None:
        self.run = run
        if self.companion is not None:
            self.companion.finish_run(run)
        self.client.table("search_runs").update(
            {
                "finished_at": _iso(run.finished_at),
                "status": run.status,
                "page_loads": run.page_loads,
                "searches_total": run.searches_total,
                "searches_ok": run.searches_ok,
                "searches_blocked": run.searches_blocked,
                "notes": run.notes,
            }
        ).eq("run_id", run.run_id).execute()


class SupabaseRotationState:
    """Rotation state read from the ``cell_last_scraped`` view (service role only).

    Marks are kept in memory for the current run only — the database rows written by the sink are the
    durable record. Cells blocked in the last 2 days are skipped for one run."""

    def __init__(self, client: Any, source_ids: list[str], pax_keys: dict[tuple[int, int], str]) -> None:
        self.client = client
        self.pax_keys = pax_keys
        self.ok: dict[str, datetime] = {}
        self.blocked: set[str] = set()
        for source_id in source_ids:
            resp = self.client.table("cell_last_scraped").select("*").eq("source_id", source_id).execute()
            for row in resp.data or []:
                key = self._cell_key(row)
                if key is None:
                    continue
                if row.get("last_ok_at"):
                    self.ok[key] = datetime.fromisoformat(str(row["last_ok_at"]).replace("Z", "+00:00"))
                if row.get("blocked_recently"):
                    self.blocked.add(key)

    def _cell_key(self, row: dict[str, Any]) -> str | None:
        pax_key = self.pax_keys.get((int(row["adults"]), int(row["children"])))
        if pax_key is None or row.get("offset_days") is None:
            return None  # ad-hoc searches or unknown passenger configs are not rotation cells
        return f"{row['source_id']}:{row['origin']}-{row['destination']}:+{row['offset_days']}:{pax_key}"

    def last_ok_at(self, cell_key: str) -> datetime | None:
        return self.ok.get(cell_key)

    def mark(self, cell_key: str, ok: bool, at: datetime, blocked: bool = False) -> None:
        if ok:
            self.ok[cell_key] = at
        if blocked:
            self.blocked.add(cell_key)

    def blocked_recently(self, cell_key: str, now: datetime | None = None) -> bool:
        return cell_key in self.blocked


def utcnow() -> datetime:
    return datetime.now(UTC)
