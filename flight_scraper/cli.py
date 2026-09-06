"""Command-line interface (typer). ``python -m flight_scraper.cli <command>``."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from .adapters import REGISTRY
from .config import CellFilters, Settings, WatchList, expand_cells, filter_cells
from .dates import run_local_date
from .db import DryRunSink, Sink, SupabaseRotationState, SupabaseSink
from .models import SearchQuery
from .pacing import PageLoadBudget
from .scheduler import FileRotationState, RotationState, explain_plan, plan_run

app = typer.Typer(
    help="flight-scraper: cheapest / fastest / best round trips from YQB and YUL.", no_args_is_help=True
)
log = logging.getLogger("flight_scraper")

WatchlistOpt = Annotated[Path | None, typer.Option("--watchlist", help="Path to watchlist.yaml")]
_RUN_FLAGS: dict[str, bool] = {}
ARTIFACT_RETENTION_DAYS = 14
STALE_CELL_DAYS = 45
MAX_RUN_AGE_HOURS = 48
DRIFT_ALARM_SEARCHES = 3


def _setup_logging(level: str | None = None, logs_dir: Path | None = None) -> None:
    from .logging_setup import setup_logging

    setup_logging(level or "INFO", logs_dir)


def _load(watchlist: Path | None) -> tuple[Settings, WatchList]:
    settings = Settings.from_env()
    _setup_logging(settings.log_level, settings.logs_dir)
    return settings, WatchList.load(watchlist)


def _filters(source: str | None, route: str | None, pax: str | None, offset: int | None) -> CellFilters:
    return CellFilters(source=source, route=route, pax=pax, offset=offset)


# ------------------------------------------------------------------ sources
@app.command()
def sources() -> None:
    """List all nine sources with enabled/disabled state and the research reason."""
    typer.echo(f"{'id':<15} {'kind':<8} {'enabled':<8} {'prio':<5} reason")
    for source_id, cls in REGISTRY.items():
        reason = cls.disabled_reason or "-"
        typer.echo(
            f"{source_id:<15} {cls.kind:<8} {'yes' if cls.enabled else 'no':<8} {cls.priority:<5} {reason}"
        )


# ------------------------------------------------------------------ watchlist
@app.command()
def watchlist(
    watchlist: WatchlistOpt = None,
    run_date: Annotated[str | None, typer.Option(help="YYYY-MM-DD (default: today, America/Toronto)")] = None,
) -> None:
    """Show the resolved cells and the concrete dates they would get today."""
    _settings, wl = _load(watchlist)
    today = date.fromisoformat(run_date) if run_date else run_local_date()
    cells = expand_cells(wl)
    typer.echo(
        f"{len(wl.resolved_routes())} routes x {len(wl.defaults.offsets_days)} offsets x "
        f"{len(wl.passenger_configs)} pax x {len(wl.sources)} sources = {len(cells)} cells "
        f"(run_date {today})"
    )
    for cell in cells:
        q = cell.to_query(today, wl.defaults)
        typer.echo(
            f"{cell.key:<40} {q.depart_date} -> {q.return_date}  adults={q.pax.adults} "
            f"children={q.pax.children} priority={cell.priority}"
        )


# ------------------------------------------------------------------ sink / rotation-state selection
def _supabase_client(settings: Settings):
    from supabase import create_client  # lazy: dry-run never imports the SDK

    return create_client(settings.supabase_url, settings.supabase_service_key)


def _rotation_state(settings: Settings, wl: WatchList, dry_run: bool, client=None) -> RotationState:
    """Supabase ``cell_last_scraped`` when credentials exist and this is not a dry run; else the file."""
    if not dry_run and settings.has_supabase and wl.rotation.state == "supabase":
        try:
            client = client or _supabase_client(settings)
            pax_keys = {(p.adults, p.children): p.key for p in wl.passenger_configs}
            return SupabaseRotationState(client, list(wl.sources), pax_keys)
        except Exception as exc:  # noqa: BLE001 - fall back, never abort a run for the planner
            log.warning("rotation state from Supabase failed (%s); using out/rotation_state.json", exc)
    return FileRotationState(settings.out_dir / "rotation_state.json")


def _sink(settings: Settings, dry_run: bool, client=None) -> Sink:
    companion = DryRunSink(settings.out_dir)  # the JSON file is always written (replayable)
    if dry_run or not settings.has_supabase:
        return companion
    return SupabaseSink(client or _supabase_client(settings), companion=companion)


# ------------------------------------------------------------------ plan
@app.command()
def plan(
    watchlist: WatchlistOpt = None,
    source: Annotated[str | None, typer.Option()] = None,
    route: Annotated[str | None, typer.Option(help="e.g. YUL-CDG")] = None,
    pax: Annotated[str | None, typer.Option(help="e.g. 1a")] = None,
    offset: Annotated[int | None, typer.Option()] = None,
    budget: Annotated[int | None, typer.Option(help="page-load budget override")] = None,
    explain: Annotated[bool, typer.Option("--explain", help="show every cell's score")] = False,
) -> None:
    """What the next run would scrape (rotation order) and its page-load estimate."""
    settings, wl = _load(watchlist)
    if budget or settings.max_page_loads_override:
        wl.budget.max_page_loads_per_run = budget or settings.max_page_loads_override  # type: ignore[assignment]
    state = _rotation_state(settings, wl, dry_run=False)
    now = datetime.now(UTC)
    cells = expand_cells(wl, [source] if source else None)
    filters = _filters(source, route, pax, offset)
    queries = plan_run(cells, state, wl.budget, now, filters, wl.defaults, run_local_date())
    est = wl.budget.est_page_loads_per_search
    typer.echo(
        f"budget {wl.budget.max_page_loads_per_run} loads, est {est}/search, cap "
        f"{wl.budget.max_searches_per_run} searches -> {len(queries)} searches planned "
        f"(~{len(queries) * est} loads)"
    )
    for q in queries:
        typer.echo(f"  {q.cell_key:<40} {q.depart_date} -> {q.return_date}")
    if explain:
        typer.echo("")
        for row in explain_plan(cells, state, wl.budget, now, filters):
            mark = "*" if row["selected"] else " "
            typer.echo(
                f"{mark} {row['rank']:>3} {row['cell']:<40} prio={row['priority']} "
                f"never={row['never_scraped']!s:<5} score={row['score']:<8} last_ok={row['last_ok_at']}"
            )


# ------------------------------------------------------------------ run
def build_queries(
    wl: WatchList,
    settings: Settings,
    state: RotationState,
    filters: CellFilters,
    depart: date | None,
    ret: date | None,
    limit: int | None,
) -> list[SearchQuery]:
    now = datetime.now(UTC)
    cells = expand_cells(wl, [filters.source] if filters.source else None)
    if depart:  # ad-hoc dates: one query per matching route x pax (no rotation, offset_days=None)
        ret = ret or (depart + timedelta(days=wl.defaults.stay_nights))
        seen: set[tuple] = set()
        out: list[SearchQuery] = []
        for cell in filter_cells(cells, filters):
            key = (cell.source_id, cell.route_key, cell.pax.key)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                SearchQuery(
                    source_id=cell.source_id,
                    origin=cell.origin,
                    destination=cell.destination,
                    depart_date=depart,
                    return_date=ret,
                    offset_days=None,
                    pax=cell.pax,
                    cabin=cell.cabin,
                    currency=cell.currency,
                )
            )
        return out[: limit or len(out)]
    return plan_run(cells, state, wl.budget, now, filters, wl.defaults, run_local_date(), limit=limit)


@app.command()
def run(
    watchlist: WatchlistOpt = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="write out/<run_id>.json only (no Supabase)")
    ] = False,
    source: Annotated[str | None, typer.Option()] = None,
    route: Annotated[str | None, typer.Option(help="e.g. YUL-CDG")] = None,
    pax: Annotated[str | None, typer.Option(help="e.g. 1a")] = None,
    offset: Annotated[int | None, typer.Option()] = None,
    budget: Annotated[int | None, typer.Option(help="page-load budget override")] = None,
    headed: Annotated[bool, typer.Option("--headed", help="show the browser (FS_HEADED=1)")] = False,
    depart: Annotated[str | None, typer.Option(help="ad-hoc depart date YYYY-MM-DD (skips rotation)")] = None,
    return_date: Annotated[str | None, typer.Option("--return", help="ad-hoc return date YYYY-MM-DD")] = None,
    limit: Annotated[int | None, typer.Option(help="max searches this run")] = None,
    capture_rpc: Annotated[
        bool, typer.Option("--capture-rpc", help="record Google RPC bodies + DOM cross-check (artifacts/)")
    ] = False,
    experimental_pax_derive: Annotated[
        bool,
        typer.Option(
            "--experimental-pax-derive",
            help="lever D experiment: reload the Best booking link re-encoded for the other pax configs",
        ),
    ] = False,
) -> None:
    """Run the scraper (rotation-planned or ad-hoc). Exit codes: 0 ok/partial, 2 blocked, 3 failed."""
    settings, wl = _load(watchlist)
    if headed:
        settings.headed = True
    global _RUN_FLAGS
    _RUN_FLAGS = {"capture_rpc": capture_rpc, "pax_derive": experimental_pax_derive}
    max_loads = budget or settings.max_page_loads_override or wl.budget.max_page_loads_per_run
    if not dry_run and not settings.has_supabase:
        msg = "SUPABASE_URL / SUPABASE_SERVICE_KEY not set: falling back to --dry-run (out/<run_id>.json)"
        log.warning(msg)
        typer.echo(f"warning: {msg}")
        dry_run = True
    client = None if dry_run else _supabase_client(settings)
    state = _rotation_state(settings, wl, dry_run, client)
    filters = _filters(source, route, pax, offset)
    queries = build_queries(
        wl,
        settings,
        state,
        filters,
        date.fromisoformat(depart) if depart else None,
        date.fromisoformat(return_date) if return_date else None,
        limit,
    )
    if not queries:
        typer.echo("nothing to do (filters matched no cells or budget is zero)")
        raise typer.Exit(code=0)
    report = _execute(settings, wl, state, queries, dry_run, max_loads, sink=_sink(settings, dry_run, client))
    typer.echo(
        f"run {report.run.run_id}: status={report.run.status} searches={len(report.results)} "
        f"ok={report.run.searches_ok} error={report.run.searches_error} "
        f"blocked={report.run.searches_blocked} skipped={report.run.searches_skipped} "
        f"page_loads={report.run.page_loads} elapsed={report.elapsed_s:.0f}s"
    )
    typer.echo(f"output: {settings.out_dir / (report.run.run_id + '.json')}")
    if not dry_run:
        typer.echo(f"upserted into Supabase project {settings.supabase_project_ref}")
    from .browser import prune_artifacts

    removed = prune_artifacts(settings.artifacts_dir, days=ARTIFACT_RETENTION_DAYS)
    if removed:
        log.info("pruned %d artifact directories older than %d days", len(removed), ARTIFACT_RETENTION_DAYS)
    raise typer.Exit(code=report.exit_code)


def _execute(
    settings: Settings,
    wl: WatchList,
    state: RotationState,
    queries: list[SearchQuery],
    dry_run: bool,
    max_loads: int,
    capture_dir: Path | None = None,
    sink: Sink | None = None,
):
    import uuid

    from .browser import BrowserArtifacts, open_context
    from .logging_setup import set_run_id
    from .runner import Runner  # local: keeps `sources`/`plan` import-light

    run_id = str(uuid.uuid4())
    set_run_id(run_id)
    sink = sink or DryRunSink(settings.out_dir)
    adapters = None
    flags = dict(_RUN_FLAGS)
    if capture_dir is not None or flags.get("capture_rpc") or flags.get("pax_derive"):
        from .adapters.google_flights.adapter import GoogleFlightsAdapter

        class ConfiguredGoogle(GoogleFlightsAdapter):  # fixtures / RPC capture / lever-D experiment
            def __init__(self, *a, **kw):
                super().__init__(*a, capture_dir=capture_dir, **kw)
                self.capture_rpc = bool(flags.get("capture_rpc"))
                if flags.get("pax_derive"):
                    self.pax_derive_configs = [(p.key, p.adults, p.children) for p in wl.passenger_configs]

        adapters = dict(REGISTRY) | {"google_flights": ConfiguredGoogle}
    runner = Runner(
        settings,
        wl,
        sink,
        state,
        dry_run=dry_run,
        page_budget=PageLoadBudget(max_loads),
        session_factory=lambda source_id: open_context(settings, source_id),
        artifacts=BrowserArtifacts(settings.artifacts_dir, run_id),
        adapters=adapters,
        run_id=run_id,
    )
    return runner.run(queries)


@app.command()
def capture(
    watchlist: WatchlistOpt = None,
    route: Annotated[str, typer.Option(help="e.g. YUL-CDG")] = "YUL-CDG",
    pax: Annotated[str, typer.Option(help="e.g. 1a")] = "1a",
    offset: Annotated[int, typer.Option()] = 60,
    depart: Annotated[str | None, typer.Option(help="ad-hoc depart date YYYY-MM-DD")] = None,
    out: Annotated[
        Path | None, typer.Option(help="fixture dir (default tests/fixtures/google_flights/<route>)")
    ] = None,
    headed: Annotated[bool, typer.Option("--headed")] = False,
) -> None:
    """Run ONE Google Flights search (dry-run) and save sanitised fixtures for the parser tests."""
    settings, wl = _load(watchlist)
    if headed:
        settings.headed = True
    state = FileRotationState(settings.out_dir / "rotation_state.json")
    filters = _filters("google_flights", route, pax, offset)
    queries = build_queries(
        wl, settings, state, filters, date.fromisoformat(depart) if depart else None, None, 1
    )
    if not queries:
        typer.echo("no cell matches the filters")
        raise typer.Exit(code=1)
    q = queries[0]
    fixture_dir = out or (settings.project_root / "tests" / "fixtures" / "google_flights" / q.route_key)
    if fixture_dir.exists():  # never mix two captures (a deduplicated pick writes no booking file)
        for stale in fixture_dir.iterdir():
            if stale.is_file():
                stale.unlink()
    typer.echo(f"capturing {q.search_key} -> {fixture_dir}")
    report = _execute(settings, wl, state, [q], True, wl.budget.est_page_loads_per_search, fixture_dir)
    (fixture_dir / "query.json").write_text(q.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(
        f"status={report.run.status} page_loads={report.run.page_loads} files: "
        f"{sorted(p.name for p in fixture_dir.iterdir())}"
    )
    raise typer.Exit(code=report.exit_code)


# ------------------------------------------------------------------ health / prune
def _latest_run_file(out_dir: Path) -> Path | None:
    files = [f for f in out_dir.glob("*.json") if f.name != "rotation_state.json"]
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


def _last_run_summary(settings: Settings, wl: WatchList) -> dict | None:
    """Latest run: Supabase ``search_runs`` when credentials exist, else the newest out/ file."""
    if settings.has_supabase:
        try:
            client = _supabase_client(settings)
            runs = (
                client.table("search_runs").select("*").order("started_at", desc=True).limit(1).execute().data
            )
            if runs:
                run = runs[0]
                searches = (
                    client.table("searches").select("status,error").eq("run_id", run["run_id"]).execute().data
                )
                return {
                    "source": f"supabase:{settings.supabase_project_ref}",
                    "run_id": run["run_id"],
                    "status": run["status"],
                    "started_at": datetime.fromisoformat(str(run["started_at"]).replace("Z", "+00:00")),
                    "page_loads": run.get("page_loads"),
                    "searches": [{"status": x["status"], "error": x.get("error")} for x in searches],
                    "itineraries": None,
                }
        except Exception as exc:  # noqa: BLE001 - fall back to the local file
            log.warning("health: Supabase unavailable (%s); reading out/", exc)
    path = _latest_run_file(settings.out_dir)
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    run = data["run"]
    return {
        "source": str(path),
        "run_id": run["run_id"],
        "status": run["status"],
        "started_at": datetime.fromisoformat(run["started_at"]),
        "page_loads": run.get("page_loads"),
        "searches": [{"status": x["status"], "error": x.get("error")} for x in data["searches"]],
        "itineraries": sum(len(x.get("picks") or {}) for x in data["searches"]),
    }


@app.command()
def health(watchlist: WatchlistOpt = None) -> None:
    """Last run status/age, stale cells, itineraries written, selector-drift alarm; exit 1 when unhealthy."""
    settings, wl = _load(watchlist)
    problems: list[str] = []
    warnings: list[str] = []
    last = _last_run_summary(settings, wl)
    now = datetime.now(UTC)
    if last is None:
        problems.append("no run recorded yet (no out/*.json and no Supabase run)")
    else:
        started = last["started_at"] if last["started_at"].tzinfo else last["started_at"].replace(tzinfo=UTC)
        age_h = (now - started).total_seconds() / 3600
        typer.echo(
            f"last run {last['run_id']} status={last['status']} age={age_h:.1f}h "
            f"page_loads={last['page_loads']} searches={len(last['searches'])} "
            f"itineraries={last['itineraries'] if last['itineraries'] is not None else 'n/a'} "
            f"({last['source']})"
        )
        if age_h > MAX_RUN_AGE_HOURS:
            problems.append(f"last run is {age_h:.0f} h old (> {MAX_RUN_AGE_HOURS} h): is the timer firing?")
        if last["status"] in ("failed", "blocked"):
            problems.append(f"last run status is {last['status']}")
        no_rows = [s for s in last["searches"] if "no_results_parsed" in (s.get("error") or "")]
        if len(no_rows) >= DRIFT_ALARM_SEARCHES:
            problems.append(
                f"selector drift? {len(no_rows)} searches parsed 0 rows (>= {DRIFT_ALARM_SEARCHES}); "
                "check artifacts/ and re-capture fixtures"
            )
        if last["itineraries"] == 0 and any(s["status"] in ("ok", "partial") for s in last["searches"]):
            problems.append("last run wrote 0 itineraries despite ok searches")
    state = _rotation_state(settings, wl, dry_run=False)
    cells = expand_cells(wl)
    stale, never = [], []
    for c in cells:
        ok_at = state.last_ok_at(c.key)
        if ok_at is None:
            never.append(c.key)
        elif (now - (ok_at if ok_at.tzinfo else ok_at.replace(tzinfo=UTC))).days > STALE_CELL_DAYS:
            stale.append(c.key)
    typer.echo(
        f"cells: {len(cells)} total, {len(never)} never scraped, "
        f"{len(stale)} older than {STALE_CELL_DAYS} days"
    )
    if stale:
        warnings.append(f"{len(stale)} cells older than {STALE_CELL_DAYS} days, e.g. {stale[:3]}")
    for w in warnings:
        typer.echo(f"warning: {w}")
    for p in problems:
        typer.echo(f"PROBLEM: {p}")
    typer.echo("healthy" if not problems else "UNHEALTHY")
    raise typer.Exit(code=1 if problems else 0)


PROBE_ENTRY = {
    "westjet": "https://www.westjet.com/en-ca/flights",
    "air_canada": "https://www.aircanada.com/ca/en/aco/home.html",
    "kayak": "https://www.ca.kayak.com/flights",
    "air_transat": "https://www.airtransat.com/en-CA/home",
    "skyscanner": "https://www.skyscanner.ca/",
    "porter": "https://www.flyporter.com/en-ca/",
    "flair": "https://www.flyflair.com/",
    "expedia": "https://www.expedia.ca/Flights",
    "google_flights": "https://www.google.com/travel/flights?hl=en-US&curr=CAD&gl=CA",
}
PROBE_REQUEST_RE = r"/graphql|/shop|/api/"


@app.command()
def probe(source: Annotated[str, typer.Argument(help="source id, e.g. westjet")]) -> None:
    """Open a HEADED browser on the source's entry page; YOU drive one search by hand. Records the final
    URL, request URLs matching /graphql|/shop|/api/ and a screenshot under artifacts/probe/<source>/."""
    import re

    from .browser import open_context

    if source not in PROBE_ENTRY:
        typer.echo(f"unknown source {source!r}; one of {sorted(PROBE_ENTRY)}")
        raise typer.Exit(code=1)
    settings = Settings.from_env()
    _setup_logging(settings.log_level, settings.logs_dir)
    settings.headed = True
    target = settings.artifacts_dir / "probe" / source
    target.mkdir(parents=True, exist_ok=True)
    seen: list[str] = []
    pattern = re.compile(PROBE_REQUEST_RE)
    typer.echo(f"opening {PROBE_ENTRY[source]} — drive one search manually, then CLOSE the browser window")
    with open_context(settings, f"probe_{source}") as page:
        page.unroute("**/*")  # the probe must see the site exactly as a person does (images too)
        page.on("request", lambda req: seen.append(req.url) if pattern.search(req.url) else None)
        page.goto(PROBE_ENTRY[source], wait_until="domcontentloaded")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:  # noqa: BLE001 - window closed / context gone
            pass
        finally:
            try:
                (target / "final_url.txt").write_text(page.url, encoding="utf-8")
                page.screenshot(path=str(target / "final.png"))
            except Exception:  # noqa: BLE001
                pass
    (target / "requests.txt").write_text("\n".join(dict.fromkeys(seen)), encoding="utf-8")
    typer.echo(f"recorded {len(set(seen))} matching request URLs into {target}")


@app.command("prune-artifacts")
def prune_artifacts_cmd(
    days: Annotated[int, typer.Option(help="delete artifact runs older than N days")] = 14,
) -> None:
    """Delete artifacts/<run_id> directories older than --days."""
    from .browser import prune_artifacts

    settings = Settings.from_env()
    removed = prune_artifacts(settings.artifacts_dir, days=days)
    typer.echo(f"removed {len(removed)} artifact directories older than {days} days")


@app.command("db-check")
def db_check() -> None:
    """Connect to Supabase, count sources/routes/latest_prices, print the last 3 runs (exit 1 on failure)."""
    settings = Settings.from_env()
    _setup_logging(settings.log_level)
    if not settings.has_supabase:
        typer.echo("SUPABASE_URL / SUPABASE_SERVICE_KEY not set (.env)")
        raise typer.Exit(code=1)
    typer.echo(f"project: {settings.supabase_project_ref}")  # never the key
    try:
        client = _supabase_client(settings)
        for table in ("sources", "routes", "latest_prices"):
            resp = client.table(table).select("*", count="exact").limit(1).execute()
            typer.echo(f"{table:<14} {resp.count} rows")
        runs = (
            client.table("search_runs")
            .select("run_id,started_at,status,page_loads,searches_ok,searches_blocked")
            .order("started_at", desc=True)
            .limit(3)
            .execute()
        )
        for r in runs.data or []:
            typer.echo(
                f"run {r['run_id']} {r['started_at']} {r['status']} loads={r['page_loads']} "
                f"ok={r['searches_ok']} blocked={r['searches_blocked']}"
            )
        if not runs.data:
            typer.echo("no runs yet")
    except Exception as exc:  # noqa: BLE001 - report and exit 1
        typer.echo(f"db-check FAILED: {type(exc).__name__}: {exc}")
        raise typer.Exit(code=1) from None


@app.command("show")
def show(path: Annotated[Path, typer.Argument(help="out/<run_id>.json")]) -> None:
    """Pretty-print the picks of a dry-run file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    typer.echo(
        f"run {data['run']['run_id']} status={data['run']['status']} loads={data['run']['page_loads']}"
    )
    for s in data["searches"]:
        q = s["query"]
        typer.echo(f"- {q['search_key']}: {s['status']} {s.get('error') or ''}")
        for pick, it in (s.get("picks") or {}).items():
            typer.echo(
                f"    {pick:<9} results={it.get('price_results_cad')} total={it.get('price_total_cad')} "
                f"({it.get('price_provider')}, {it.get('price_stage')}) "
                f"carry_on={it.get('carry_on_included')} "
                f"bag={it.get('checked_bag_fee_cad')} dur={it.get('duration_min')} stops={it.get('stops')}"
            )


if __name__ == "__main__":
    app()
