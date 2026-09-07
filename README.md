# flight-scraper

Scheduled Python + Playwright scraper for round-trip flights departing **YQB** and **YUL**.
For every watch-list cell (route × departure offset × passenger configuration) it records the **cheapest**,
**fastest** and **best** itinerary with the booking-page total (taxes + fees, all passengers), carry-on /
checked-bag information and a deep-link URL, then upserts everything into **PostgreSQL** (a local docker
compose database, or a Supabase project) for the website.

Only **Google Flights** is enabled in v1. The other eight requested sources (Kayak, Expedia, Skyscanner,
Air Canada, Air Transat, WestJet, Porter, Flair) ship as disabled adapter stubs carrying the research reason
(`python -m flight_scraper.cli sources`). See `.prompts/` for the research → plan → implement chain.

## How one search works (Google Flights)

| step | page loads | what is read |
|---|---|---|
| default load (`tfs` deep link) | 1 | every `li.pIav2d` row's aria-label sentence; row 0 = Google's **Best** |
| Cheapest tab (`tfu=EgoIABAAGAAgAigB`) | 1 | min round-trip total = **Cheapest** |
| Duration sort (`tfu=EgYIBRAAGAA`) | 1 | min total duration = **Fastest** |
| per pick: click outbound → returning list → click return → `/travel/flights/booking` | 2 | per-provider totals incl. taxes, bag text, price insight, booking URL |

A search costs **≤ 9 page loads**; a booking visit is skipped when a pick's outbound was already visited
(5–7 loads is typical). The nightly budget is 40 loads (`config/watchlist.yaml`), so a run does 4–5 searches
and a weighted oldest-first rotation walks the 144-cell matrix. Blocks (403/429, `/sorry/`, consent page,
captcha) are recorded as data (`blocked=true`, screenshot + HTML in `artifacts/`), never bypassed.

## Install

```bash
uv venv && uv pip install -e .[dev]          # or: python -m venv .venv && .venv/bin/pip install -e .[dev]
playwright install chromium                  # add --with-deps on a fresh Ubuntu/WSL2
cp .env.example .env                         # DATABASE_URL (local Postgres) or SUPABASE_URL / SUPABASE_SERVICE_KEY
just up                                      # local PostgreSQL 16 in docker compose, migration applied on first start
pytest -q                                    # unit + fixture tests; live tests are skipped
```

`just` lists every recipe (`up`, `down`, `migrate`, `psql`, `db-check`, `health`, `run`, `dry-run`, `test`,
`test-live-db`). Docker and `just` are only needed for the local database; with Supabase (below) skip `just up`.

Optional: `uv pip install -e .[stealth]` + `sudo apt install xvfb` for the patchright engine
(`FS_BROWSER_ENGINE=patchright FS_HEADED=1`), only if Google starts serving `/sorry/` or 429 pages.

## Configuration

Environment (`.env`, git-ignored; `.env.example` documents it):

| variable | meaning |
|---|---|
| `DATABASE_URL` | plain PostgreSQL DSN (`postgres://postgres:postgres@localhost:5433/flights` with `just up`); wins over Supabase when both are set |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | server-side project URL + `sb_secret_…` key; neither backend set → dry-run only |
| `FS_BROWSER_ENGINE` | `playwright` (default, live-verified) or `patchright` |
| `FS_HEADED` | `1` shows the browser (needs a display or `xvfb-run`) |
| `FS_MAX_PAGE_LOADS` | one-off override of the nightly page-load budget |
| `FS_LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` |

Watch-list (`config/watchlist.yaml`): `origins` × `destinations` (or an explicit `routes` list),
`defaults.offsets_days` (+30/+60/+90, snapped to the **next Saturday**, 7-night stay), `passenger_configs`
(`1a`, `2a`, `1a1c`, `1a2c`; `priority` weights the rotation), `budget` (page loads, searches, booking
visits, jittered delays, retries, block breaker) and `rotation`.

**Refresh-cycle levers** (all config-only). At 40 loads/day with all three booking visits, 1-adult cells
refresh every ≈ 17 days, 2-adult ≈ 25, child configs ≈ 50:

- **A** `budget.max_page_loads_per_run: 120` → ≈ 6 days (research saw ~30 loads in 15 min without a 429).
- **B** `budget.booking_visits: best_only` → 5 loads/search, 8 searches/run → ≈ 10 days
  (Cheapest/Fastest then keep `price_stage='results'`, the results-row round-trip total).
- **C** drop the `+90` offset or the `1a2c` config (−36 cells each).
- **D** passenger-derived booking loads (Phase 5 experiment, not implemented).

## Running

```bash
python -m flight_scraper.cli sources                 # the nine sources, enabled/disabled + reason
python -m flight_scraper.cli watchlist               # 144 cells with today's concrete dates
python -m flight_scraper.cli plan [--explain]        # tonight's rotation order and load estimate
python -m flight_scraper.cli run                     # nightly run → database (+ out/<run_id>.json)
python -m flight_scraper.cli run --dry-run --source google_flights --route YUL-CDG --pax 1a --offset 60
python -m flight_scraper.cli run --depart 2026-12-19 --route YQB-CUN --pax 2a     # ad-hoc dates
python -m flight_scraper.cli show out/<run_id>.json  # picks of a run
python -m flight_scraper.cli capture --route YQB-CDG --pax 1a --offset 60          # refresh test fixtures
python -m flight_scraper.cli health                  # last run age/status, stale cells, drift alarm (exit 1)
python -m flight_scraper.cli db-check                # database connectivity, counts, last 3 runs
python -m flight_scraper.cli prune-artifacts --days 14
```

Exit codes of `run` (and `scripts/run_daily.sh`): `0` ok/partial, `2` blocked, `3` failed.
Without a database or with `--dry-run` the run writes `out/<run_id>.json` only; with one configured the JSON
file is still written next to the upserts so a failed night can be replayed later.

Filters: `--source`, `--route YUL-CDG`, `--pax 1a`, `--offset 60`, `--limit N`, `--budget N`, `--headed`.

## Scheduling on WSL2

```bash
scripts/install_systemd.sh      # copies the units, daemon-reload, enable --now (needs sudo once)
systemctl list-timers flight-scraper.timer
journalctl -u flight-scraper -f
FS_DRY_RUN=1 scripts/run_daily.sh --route YUL-CDG --pax 1a    # manual dry run through the wrapper
```

`flight-scraper.timer` fires daily at **06:30 ± 45 min** (`RandomizedDelaySec`, `Persistent=true` so a
missed run fires when WSL wakes). The service runs as your user (browser profile ownership), with
`TZ=America/Toronto`, `EnvironmentFile=.env`, `TimeoutStartSec=45min`. Prerequisites printed by the
installer: `[boot] systemd=true` in `/etc/wsl.conf` (then `wsl --shutdown`), a Windows Task Scheduler
keep-alive (`wsl.exe -d <distro> -- sleep infinity`), and `sudo hwclock -s` after Windows sleep.
Logs rotate in-process: `logs/flight-scraper.log` (5 MB × 5) plus journald.

## Debugging

- `artifacts/<run_id>/<search_key>/{page.html,page.png,url.txt,reason.txt}` are saved on blocks, zero rows
  and failed booking visits; pruned automatically after 14 days.
- `tests/fixtures/google_flights/<route>/` holds captured aria-labels (`*_rows.json`), booking page texts
  (`booking_<pick>.txt`) and gzipped HTML. Never edit them by hand — re-run `cli capture`.
- `cli health` fails when the last run is older than 48 h, failed/blocked, or when ≥ 3 searches parsed
  0 rows (selector drift: compare `artifacts/` with the fixtures and update `parse_results.py`).
- Rows saying "Total price is unavailable" are skipped (counted in `raw.rows_unpriced`), not errors.

## Database: local PostgreSQL or Supabase

One migration, `supabase/migrations/0001_init.sql`, serves both backends (idempotent; it seeds the nine
`sources` and the 12 `routes`). The scraper picks the backend from `.env`: `DATABASE_URL` → plain
PostgreSQL through psycopg; otherwise `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` → Supabase through its SDK;
neither → dry-run. Same upserts, same rotation view, same `db-check` / `health` either way.

**Local PostgreSQL (no Supabase account needed).** `docker-compose.yml` runs `postgres:16-alpine` on host
port **5433** (so it never clashes with another Postgres on 5432) with a named data volume.
`docker/postgres/initdb/01_roles.sql` creates the `anon` / `authenticated` roles as no-login roles so the
migration's grants apply unchanged; both scripts run automatically on the first `just up`. `just migrate`
re-applies the migration after a schema change, `just psql` opens a shell, `just clean` deletes the volume.
The scraper itself keeps running on the host (residential IP) and connects over `DATABASE_URL`.
There is no auto-generated REST API in this mode: a website needs a small read-only API in front of
`latest_prices` (the Supabase publishable-key queries below map 1:1 onto SQL).

**Supabase.** Paste the migration into the SQL editor. Keys: the scraper uses the **`sb_secret_…`** key
server-side (`SUPABASE_SERVICE_KEY`, bypasses RLS); the website uses the **`sb_publishable_…`** key and,
through RLS, can only read `itineraries` plus the two public views.

Tables: `sources`, `routes`, `search_runs`, `searches` (natural key + `scrape_date`: a same-day re-run
overwrites, other days accumulate history), `itineraries` (unique on `(search_id, pick)`).
Views: `latest_prices` (one row per source/route/dates/pax/cabin/pick from the most recent successful
search), `latest_prices_by_offset` ("about 30/60/90 days out" regardless of the concrete Saturday), and
`cell_last_scraped` (scraper only; drives the rotation).

Website queries (publishable key):

```sql
select * from latest_prices_by_offset
 where origin = 'YUL' and adults = 2 and children = 0 order by destination, offset_days, pick;

select pick, price_total_cad, price_provider, carry_on_included, checked_bag_fee_cad, deep_link_url
  from latest_prices
 where origin = 'YQB' and destination = 'CDG' and depart_date = '2026-11-07' and adults = 1 and children = 1;
```

Column meanings:

| column | meaning |
|---|---|
| `pick` / `pick_rule` | `best` / `cheapest` / `fastest`; `native` = Google's own tab/sort, `local-v1` = our scoring rule |
| `price_results_cad` | round-trip total shown in the results list (all passengers) |
| `price_total_cad`, `price_provider` | cheapest provider on the booking page, taxes + fees included (`raw.booking.providers` has all of them, airline first) |
| `price_stage` | `booking` when the booking page was read; `results` when it was skipped or failed (see `raw.booking_error`) |
| `carry_on_included` | from "1 free carry-on" / "No carry-on" on the booking page; `null` when Google shows no bag text |
| `checked_bag_fee_cad` | low end of "1st checked bag: CA$150–170"; high end in `raw.booking.checked_bag_fee_max_cad`, `0` when included |
| `luggage_source` | `google_booking_page` when a bag sentence was parsed, else `null` |
| `deep_link_url` | `/travel/flights/booking?tfs=…` (itinerary-specific) or the results URL |
| `child_ages` | always `{}` for Google (no child age); `children` carries the count |
| `outbound_*_local`, `return_*_local` | airport-local wall times (Google shows no timezone) |

Price history is not exposed to the website in v1 (`searches` is not readable by anon).

## Adding a route or destination

Add a code to `destinations` (or `origins`) in `config/watchlist.yaml`; `routes: all` expands the product.
Unknown routes are inserted into `routes` on first write. Run `cli watchlist` to see the new cells and
`cli plan --explain` to see where they land in the rotation.

## Enabling another source

Each stub in `flight_scraper/adapters/` documents why it is disabled. To enable one: implement
`build_url` (pure), `search` (results → candidates tagged `candidate_source` / `row_index`, calling
`self.budget.consume(1)` per page load and raising `BlockedError` on block markers), optionally
`enrich_luggage` (fare-family / review page → `price_stage='fare_select'|'review'`), set
`enabled = True` and add fixtures + tests. The research recommends WestJet first, then Air Canada;
several sites forbid scraping in their terms, so read the stub's reason before enabling.

## Politeness

robots.txt disallows Google's search path, so the scraper stays small and human-paced: ≤ 40 page loads a day
from a residential IP, jittered delays between actions/loads/searches, one persistent browser context,
a breaker after two consecutive blocks, and no captcha solving, consent automation or access-control bypass.
