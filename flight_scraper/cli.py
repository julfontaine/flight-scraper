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
from .db import DryRunSink
from .models import SearchQuery
from .pacing import PageLoadBudget
from .scheduler import FileRotationState, explain_plan, plan_run

app = typer.Typer(
    help="flight-scraper: cheapest / fastest / best round trips from YQB and YUL.", no_args_is_help=True
)
log = logging.getLogger("flight_scraper")

WatchlistOpt = Annotated[Path | None, typer.Option("--watchlist", help="Path to watchlist.yaml")]


def _setup_logging(level: str | None = None) -> None:
    logging.basicConfig(level=level or "INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _load(watchlist: Path | None) -> tuple[Settings, WatchList]:
    settings = Settings.from_env()
    _setup_logging(settings.log_level)
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
    state = FileRotationState(settings.out_dir / "rotation_state.json")
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
    state: FileRotationState,
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
) -> None:
    """Run the scraper (rotation-planned or ad-hoc). Exit codes: 0 ok/partial, 2 blocked, 3 failed."""
    settings, wl = _load(watchlist)
    if headed:
        settings.headed = True
    max_loads = budget or settings.max_page_loads_override or wl.budget.max_page_loads_per_run
    if not dry_run and not settings.has_supabase:
        msg = "SUPABASE_URL / SUPABASE_SERVICE_KEY not set: falling back to --dry-run (out/<run_id>.json)"
        log.warning(msg)
        typer.echo(f"warning: {msg}")
        dry_run = True
    state = FileRotationState(settings.out_dir / "rotation_state.json")
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
    report = _execute(settings, wl, state, queries, dry_run, max_loads)
    typer.echo(
        f"run {report.run.run_id}: status={report.run.status} searches={len(report.results)} "
        f"ok={report.run.searches_ok} error={report.run.searches_error} "
        f"blocked={report.run.searches_blocked} skipped={report.run.searches_skipped} "
        f"page_loads={report.run.page_loads} elapsed={report.elapsed_s:.0f}s"
    )
    if dry_run:
        typer.echo(f"output: {settings.out_dir / (report.run.run_id + '.json')}")
    raise typer.Exit(code=report.exit_code)


def _execute(
    settings: Settings,
    wl: WatchList,
    state: FileRotationState,
    queries: list[SearchQuery],
    dry_run: bool,
    max_loads: int,
):
    from .runner import Runner  # local: keeps `sources`/`plan` import-light

    sink = DryRunSink(settings.out_dir)
    runner = Runner(
        settings,
        wl,
        sink,
        state,
        dry_run=dry_run,
        page_budget=PageLoadBudget(max_loads),
        session_factory=_session_factory(settings),
    )
    return runner.run(queries)


def _session_factory(settings: Settings):
    """Phase 1: no browser module yet — adapters that need one report 'adapter not implemented'."""
    try:
        from .browser import open_context  # noqa: WPS433 - Phase 2 module
    except ImportError:
        return None
    return lambda source_id: open_context(settings, source_id)


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
