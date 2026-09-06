# Flight Scraper Implement Summary

**Scraper complete on branch `implement-003`: Google Flights live adapter (three results loads + booking-page visits, ≤ 9 loads/search, 5–7 observed) with 8 disabled stubs, Supabase sink + rotation state, systemd timer, health/db-check/probe CLI, 115 tests green, README; live-verified 5× today from this WSL2 box with no block — awaiting Supabase credentials for the first real upsert and systemd enablement for the timer.**

## Version — v1

## Key Findings

**What was implemented (plan phases 1–4 done, 5 partial):**
- **Phase 1** — package, `config/watchlist.yaml` (12 routes × 3 offsets × 4 pax = 144 cells), settings from env, date rule (next Saturday, 7 nights), models per the adapter contract, in-repo `tfs` protobuf encoder (golden string verified), pick rules, weighted oldest-first rotation with atomic file state, dry-run sink, typer CLI (`sources`, `watchlist`, `plan [--explain]`, `run`, `show`), migration SQL parsed by `pglast`, 8 stub adapters raising `SourceDisabled(reason)` (Kayak/Skyscanner/Expedia/Air Canada keep tested URL builders).
- **Phase 2** — `browser.py` (persistent headless Chromium, en-CA/Toronto, image/font/media blocking, block detection for 403/429, `/sorry/`, consent, captcha iframe, "unusual traffic"; artifacts screenshot+HTML+url+reason), `parse_results.py` (aria-label sentence → price/stops/carriers/times/duration/layovers/self-transfer flags; waits on ≥ 2 `GetShoppingResults` responses + stable row list; "more flights" expansion; duplicate-label and "Total price is unavailable" rows handled), `parse_booking.py` (providers incl. hidden prices, "Airline" badge, "taxes + fees for N adult(s)/passengers", carry-on / 1st checked bag range, price insight), the adapter's interleaved flow (load → pick → click outbound → returning list detected by "arrives at <origin airport>" → click return → booking page waits for "Book with"), dedup of identical picks, runner retries/breaker/budget guard, `cli capture` writing sanitised fixtures (row JSON, booking text, gzipped HTML). **Live-verified:** YUL-CDG 1a +60 → status ok, 7 loads, best/cheapest CA$716 (Adam Vacations; Air Transat CA$720 also listed) and fastest CA$757 (Delta), carry-on included, 1st bag CA$150–170 / CA$180, booking deep links, return legs, price insights; YQB-CDG 1a +60 → 5 loads (all three picks share one outbound).
- **Phase 3** — `SupabaseSink` (upsert `searches` on the 9-column natural key incl. `child_ages` + `scrape_date` with `returning=representation`, `itineraries` on `(search_id, pick)` minimal, `search_runs` insert/update, unknown routes created, JSON companion always written), `SupabaseRotationState` from `cell_last_scraped` (blocked cells skipped one run), sink/state selection in the CLI (credentials + not `--dry-run` → Supabase, else file), `db-check`, fake-client idempotency tests, opt-in live DB test. **Not live-verified: no credentials.**
- **Phase 4** — `scripts/run_daily.sh` (exit 0/2/3, `FS_DRY_RUN`, `xvfb-run` when headed), `flight-scraper.service` (oneshot, user, `TZ=America/Toronto`, `EnvironmentFile=.env`, 45 min timeout) + `.timer` (06:30, `RandomizedDelaySec=45m`, `Persistent=true`), `install_systemd.sh` (prints WSL2 prerequisites, refuses when systemd is offline — it is offline on this box today), rotating file log with run id, `cli health` (run age > 48 h, failed/blocked, ≥ 3 zero-row searches = selector-drift alarm, stale cells > 45 days as warning), `prune-artifacts` + automatic 14-day pruning, complete README.
- **Phase 5 (partial)** — `rpc.py` + `--capture-rpc` (batchexecute decode, saves bodies under `artifacts/<run>/rpc/`, warns when the DOM min/max price is absent from the RPC payload; live: 2 bodies / 4 payloads, both prices found), flight numbers recovered from the booking `tfs` (leg field 4 = carrier + number, e.g. TS 110 / TS 111 — the booking page itself prints none), `rewrite_passengers` + `--experimental-pax-derive` (lever D; see Blockers for the live result), `cli probe <source>` (headed, human-driven, records final URL + `/graphql|/shop|/api/` requests + screenshot), `docs/enabling-a-source.md`. **Not done:** patchright path only wired (`FS_BROWSER_ENGINE=patchright`, package not installed), carry-on filter experiment.

**Observed vs research:** default load exposes ~76 unique itineraries for YUL-CDG (152 DOM rows with re-render duplicates) and 56 for YQB-CDG (6 unpriced), not 2–4; the aria-label `div[role=link]` cannot be clicked directly (overlay) — the departure-times span is clicked instead; booking text glues "Airline" to the provider name and says "for 1 adult"; cheapest provider is often an OTA (Adam Vacations CA$716 vs Air Transat CA$720) — `price_provider` says which, `raw.booking.providers` keeps all.

**Verification:** `ruff check .` clean; `pytest -q` → 115 passed, 2 skipped (optional cross-check, no faster-flights), live tests deselected; `cli sources` lists 9; `cli plan` → 4 searches at 40 loads; `cli run --dry-run --source google_flights --route YUL-CDG --pax 1a --offset 60` → `out/<run_id>.json` with three booking-stage picks; migration parsed by pglast. ~40 page loads were spent on Google today across 5 runs (the daily budget); no block.

## Files Created
- `pyproject.toml` — deps (playwright 1.62, supabase ≥ 2.31, pydantic, pyyaml, typer, python-dotenv; dev pytest/ruff/pglast), pytest `live` marker, ruff config
- `config/watchlist.yaml` — seed watch-list (YQB/YUL × YYZ/YVR/FLL/MCO/CUN/CDG, +30/60/90, 1a/2a/1a1c/1a2c), budget, rotation
- `flight_scraper/config.py` — env `Settings`, `WatchList` model, cell expansion, CLI filters
- `flight_scraper/dates.py` — America/Toronto run date, next-Saturday date rule
- `flight_scraper/models.py` — Pick/PriceStage/PaxConfig/SearchQuery/Leg/Provider/Itinerary/SearchResult
- `flight_scraper/picks.py` — native pick selection + `local_v1` scoring
- `flight_scraper/scheduler.py` — rotation state (memory/file), weighted oldest-first `plan_run`, `explain_plan`
- `flight_scraper/pacing.py` — page-load budget, jittered sleeper
- `flight_scraper/db.py` — `DryRunSink`, `SupabaseSink`, `SupabaseRotationState`, row serialisation
- `flight_scraper/runner.py` — run loop: retries, block breaker, budget guard, sink/state updates, exit codes
- `flight_scraper/browser.py` — Playwright/patchright context, block detection, artifacts, pruning
- `flight_scraper/logging_setup.py` — console + rotating file log with run id
- `flight_scraper/cli.py` — `sources`, `watchlist`, `plan`, `run`, `capture`, `show`, `health`, `db-check`, `probe`, `prune-artifacts`
- `flight_scraper/adapters/base.py` — adapter contract, `SourceDisabled`/`BlockedError`/`NoResultsParsed`
- `flight_scraper/adapters/__init__.py` — registry of the nine sources by priority
- `flight_scraper/adapters/_stub.py`, `westjet.py`, `air_canada.py`, `kayak.py`, `air_transat.py`, `skyscanner.py`, `porter.py`, `flair.py`, `expedia.py` — disabled stubs with research reasons (tested URL builders where known)
- `flight_scraper/adapters/google_flights/tfs.py` — tfs encoder/decoder, `tfu` constants, booking-tfs decoder, flight numbers, passenger rewrite
- `flight_scraper/adapters/google_flights/parse_results.py` — aria-label parser, row reading/waiting helpers, RPC counter
- `flight_scraper/adapters/google_flights/parse_booking.py` — booking-page text parser
- `flight_scraper/adapters/google_flights/adapter.py` — the live flow (loads, picks, booking visits, dedup, RPC capture, lever-D experiment)
- `flight_scraper/adapters/google_flights/rpc.py` — batchexecute decoding and DOM/RPC cross-check
- `supabase/migrations/0001_init.sql` — schema, seeds, views, RLS (verbatim from the plan)
- `scripts/run_daily.sh`, `flight-scraper.service`, `flight-scraper.timer`, `install_systemd.sh` — scheduling on WSL2
- `docs/enabling-a-source.md` — playbook for enabling WestJet/Air Canada/…
- `tests/conftest.py` (fixtures, fake adapter), `test_tfs.py`, `test_dates.py`, `test_config.py`, `test_picks.py`, `test_scheduler.py`, `test_stubs.py`, `test_cli.py`, `test_migration_sql.py`, `test_runner.py`, `test_google_parse_results.py`, `test_google_parse_booking.py`, `test_db_sink.py`, `test_cli_health.py`, `test_tfs_rewrite.py`, `test_rpc_parse.py`, `tests/live/test_google_live.py`, `tests/live/test_supabase_live.py`
- `tests/fixtures/google_flights/YUL-CDG/`, `YQB-CDG/` — captured rows/booking text/gzipped HTML (2026-09-06)
- `.env.example`, `.gitignore`, `README.md`

## Decisions Needed
- **Provide `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`** (`sb_secret_…`) in `.env` and paste `supabase/migrations/0001_init.sql` into the SQL editor; then `cli db-check` and `pytest -m live tests/live/test_supabase_live.py`.
- **Pick a refresh lever** (none applied; default 40 loads / all booking visits → 1a cells every ≈ 17 days): A `max_page_loads_per_run: 120`, B `booking_visits: best_only`, C trim `+90` or `1a2c`, D pax-derive (see Blockers).
- **Confirm the seed watch-list** and that `price_total_cad` = cheapest provider (often an OTA) rather than the airline's own price (both are stored; the website can prefer `raw.booking.providers[is_airline]`).
- **Return-leg rule** (Best → first returning row, Cheapest → min price, Fastest → min duration, taking the cheapest return within 10 min of the shortest after a YQB-YYZ run chose a CA$1,758 return 1 min faster than a CA$562 one) and **block handling** (abort after 2 consecutive blocks, consent page = block) are implemented as planned — confirm.
- **Merge `implement-003` into `main`** (branch left unmerged).

## Blockers
- No Supabase credentials → Phase 3 live path untested (fake-client tests only).
- systemd is offline in this WSL2 distro (`systemctl is-system-running` → offline): set `[boot] systemd=true`, `wsl --shutdown`, then run `scripts/install_systemd.sh` (needs sudo) and the Windows keep-alive task.
- **Lever D works** (live 2026-09-06, YUL-CDG Best pick TS 110/111, 1a booking total CA$716 by Adam Vacations): the booking `tfs` re-encoded for `2a` → CA$1,431 (note "for 2 adults"), `1a1c` → CA$1,411 ("for 2 passengers"), `1a2c` → CA$2,107 ("for 3 passengers"), all accepted by Google in 1 load each. Not the default: it prices only the *same itinerary* for other pax configs (a family's cheapest flight may differ), so it needs your review before replacing full searches — it would cut a route-date from 4 searches (≈ 28 loads) to 1 search + 9 derived loads.

## Next Step
Fill `.env`, apply the migration, run `python -m flight_scraper.cli db-check`, then `scripts/run_daily.sh --limit 2` once by hand and `cli health`; enable systemd and run `scripts/install_systemd.sh`.

---
*Confidence: high for the Google flow, parsers and CLI (live-verified 5× today, fixtures captured); medium for Supabase (offline tests only) and for markup stability over weeks; medium-low for the systemd-on-WSL2 recipe (not exercised: systemd offline).* *Iterations: 1*
