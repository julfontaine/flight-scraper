<objective>
Implement **flight-scraper** in `/home/jfontaine/Projects/flight-scraper/` by executing the phases defined in the plan, in order, until all phases are complete.

Purpose: Produce a working, scheduled Python + Playwright scraper that stores cheapest / fastest / best round-trip itineraries from YQB and YUL — with final-stage price, luggage pricing, passenger variations, and deep-link URLs — into Supabase for the user's website.
Output: Working codebase, Supabase migration, tests, README, and SUMMARY.md.
</objective>

<context>
Research: @.prompts/001-flight-scraper-research/flight-scraper-research.md
Plan (authoritative for phases, schema, adapter contract, watch-list): @.prompts/002-flight-scraper-plan/flight-scraper-plan.md

Environment: Linux (WSL2), Python 3.12+, no Supabase credentials in the repo. `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` come from `.env` (git-ignored); if they are absent at run time, the CLI must still work in `--dry-run` mode and write JSON to `./out/` instead of failing.
</context>

<requirements>
Functional:
- Follow the plan's phases **exactly and sequentially**. Finish and verify each phase before starting the next. Update the plan file's phase with `status="done"` when complete.
- Every source in the plan gets an adapter module, even disabled ones (a stub that raises `SourceDisabled(reason)`), so the `sources` table and CLI list all nine.
- Passenger matrix, luggage fields (`carry_on_included`, `carry_on_fee_cad`, `checked_bag_fee_cad`, `luggage_source`), `price_stage`, and `deep_link_url` are populated per the adapter contract; never invent a price — use NULL and record why in `raw`/`error`.
- Picks: use native Best/Cheapest/Fastest when the site has them; otherwise apply the plan's scoring rule. Store all three picks per search.
- Idempotent upserts keyed as the schema defines; re-running the same day overwrites, never duplicates.

Quality / safety:
- Politeness from the plan: one browser context per source, sequential searches, randomized delays, hard cap per run. Detect blocks (403/429, captcha markers, empty results with challenge iframe) → mark `blocked=true`, save screenshot + HTML to `artifacts/<run_id>/`, continue with the next search. **Do not implement or call any CAPTCHA-solving or access-control bypass** — a block is a data point, not an obstacle to defeat.
- Secrets only via env; `.env.example` committed, `.env` git-ignored.
- Type hints, `ruff` clean, `pytest` green. Fixture-based parser tests using saved HTML/JSON under `tests/fixtures/<source>/`; live tests behind `-m live` and skipped by default.

Constraints:
- Python + Playwright + the stealth layer named in the plan; `supabase-py`; `pydantic` for models; `pyyaml` for config; `typer` or `argparse` for CLI. No paid services.
- Keep the layout the plan specifies; if the plan is silent, use:
  `flight_scraper/{config.py,models.py,db.py,picks.py,browser.py,cli.py,adapters/{base.py,google_flights.py,kayak.py,expedia.py,skyscanner.py,air_canada.py,air_transat.py,westjet.py,porter.py,flair.py}}`, `config/watchlist.yaml`, `supabase/migrations/0001_init.sql`, `scripts/run_daily.sh`, `tests/`.
</requirements>

<implementation>
- Start each phase by re-reading its `<execution_notes>` in the plan.
- Build URL builders and pick-selection as pure functions first (testable without a browser).
- Prefer intercepting the page's XHR/JSON responses (`page.on("response")` / `page.expect_response`) over DOM scraping when the research identified an endpoint — JSON is far more stable than CSS selectors. Fall back to ARIA-role/text selectors, not brittle class names.
- Google Flights: use the `tfs`-encoded URL approach from research (or `fast-flights` if verified working) and switch tabs/sorts to obtain the three picks from one session.
- Airline sites: go results → fare-family selection → review page, reading carry-on inclusion and the review total; if the review page is unreachable, record `price_stage="fare_select"` and continue.
- OTAs: if enabled, take results-page prices with `price_stage="results"`; do not follow handoff redirects to the airline (that would double-count the airline adapters).
- Write `run_daily.sh` + the cron/systemd unit from the plan; `--dry-run` writes `out/<run_id>.json`.
- Avoid: global mutable state across adapters; sleeping with fixed intervals (use jitter); catching bare `Exception` without persisting the error into `searches.error`.

<efficiency>
Create independent files in parallel (models, config, several adapter stubs at once). Run `ruff` and `pytest` once per phase, after changes — not after every file.
</efficiency>
</implementation>

<output>
Create/modify under `/home/jfontaine/Projects/flight-scraper/`:
- `pyproject.toml` — deps, ruff, pytest config (`markers = ["live"]`)
- `flight_scraper/**` — package per layout above
- `config/watchlist.yaml` — seed list + passenger matrix from the plan
- `supabase/migrations/0001_init.sql` — schema, RLS, `latest_prices` view (verbatim from plan, fixed if invalid)
- `scripts/run_daily.sh`, `scripts/flight-scraper.service`/`.timer` or crontab line
- `tests/**` — unit + fixture tests; `tests/fixtures/<source>/`
- `.env.example`, `.gitignore` (add `.env`, `out/`, `artifacts/`, `.venv/`)
- `README.md` — setup (venv, `playwright install chromium`, `.env`), running, schema, how the website should query `latest_prices`, how to add a route
</output>

<verification>
Per phase and at the end:
1. `uv sync` or `pip install -e .[dev]` succeeds; `playwright install chromium` documented
2. `ruff check .` clean; `pytest -q` green (live tests skipped)
3. `python -m flight_scraper.cli run --dry-run --source google_flights --route YUL-CDG` produces `out/<run_id>.json` with three picks and populated luggage/price_stage fields (or a documented block)
4. `python -m flight_scraper.cli sources` lists all 9 with enabled/disabled + reason
5. With real credentials (only if the user has put them in `.env`): one live search upserts into Supabase and `select * from latest_prices` returns rows; re-run does not duplicate
6. Migration SQL applies cleanly on a fresh Supabase project (validate at least with `psql --dry-run`-style syntax parsing or by careful review if no DB is available)
</verification>

<summary_requirements>
Create `.prompts/003-flight-scraper-implement/SUMMARY.md`:

# Flight Scraper Implement Summary
**{One-liner: e.g., "Scraper complete: 6 live adapters + 3 disabled stubs, 42 tests, daily systemd timer; awaiting Supabase credentials for first live upsert"}**
## Version — v1
## Key Findings — what was implemented, which adapters verified live vs fixture-only, which sites blocked during smoke tests
## Files Created — path + one-line description for every file
## Decisions Needed — e.g., "Paste migration into Supabase SQL editor", "Provide SUPABASE_URL/SERVICE_KEY", "Confirm watch-list"
## Blockers — missing credentials, blocked sources, etc.
## Next Step — concrete (e.g., "Fill .env and run `scripts/run_daily.sh` once")
---
*Confidence: …* *Iterations: 1*
</summary_requirements>

<success_criteria>
- All plan phases marked done; codebase matches the plan's layout and schema
- Tests and lint pass; dry-run produces the expected JSON for Google Flights and at least two airline adapters
- Every one of the 9 sources is represented (live or disabled-with-reason)
- Luggage, passenger-matrix, price_stage, and deep-link fields flow config → adapter → DB → `latest_prices`
- No secrets committed; no CAPTCHA/bypass code
- README lets the user run the scraper and query results from their website
- SUMMARY.md created with full file list and next step
</success_criteria>
