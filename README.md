# flight-scraper

Scheduled Python + Playwright scraper for round-trip flights departing **YQB** and **YUL**.
For each watch-list cell (route × departure offset × passenger configuration) it records the **cheapest**,
**fastest** and **best** itinerary with the booking-page total (taxes + fees, all passengers), carry-on /
checked-bag information and a deep-link URL, then upserts everything into **Supabase** for the website.

Only **Google Flights** is enabled in v1; the other eight sources (Kayak, Expedia, Skyscanner, Air Canada,
Air Transat, WestJet, Porter, Flair) ship as disabled adapter stubs with the research reason
(`python -m flight_scraper.cli sources`).

## Layout

```
flight_scraper/            package (config, dates, models, picks, scheduler, db, runner, cli)
flight_scraper/adapters/   one module per source; google_flights/ is the live adapter (tfs URL encoder)
config/watchlist.yaml      routes, offsets, passenger configs, budget, rotation
supabase/migrations/       0001_init.sql — paste into the Supabase SQL editor
tests/                     unit tests (fixtures under tests/fixtures/<source>/; live tests behind -m live)
```

## Quick start

```bash
uv venv && uv pip install -e .[dev]        # or: python -m venv .venv && .venv/bin/pip install -e .[dev]
playwright install chromium
cp .env.example .env                        # fill SUPABASE_URL / SUPABASE_SERVICE_KEY when available
pytest -q                                   # live tests are skipped by default
python -m flight_scraper.cli sources        # the nine sources
python -m flight_scraper.cli plan           # what the next run would scrape
python -m flight_scraper.cli run --dry-run --source google_flights --route YUL-CDG --pax 1a --offset 60
```

`--dry-run` (or missing Supabase credentials) writes `out/<run_id>.json` instead of touching the database.

Full documentation (scheduling on WSL2, schema, website queries, adding routes) lands with Phase 4 of
`.prompts/002-flight-scraper-plan/flight-scraper-plan.md`.
