# Flight Scraper Plan Summary

**5-phase build: scaffold+schema → Google Flights adapter → Supabase ingestion → systemd scheduler/CLI/README → optional hardening; 1 source enabled (Google Flights, DOM aria-label parsing, booking-page final price + luggage), 8 disabled stubs with research reasons; 144-cell watch-list walked by a budget-aware rotation at ≤ 40 page loads/day.**

## Version — v1

## Key Findings

**Phases (one prompt each, sequential):**
1. **Scaffold, config, schema, models, pure functions** — `pyproject.toml`, `config/watchlist.yaml`, `config.py`/`dates.py`/`models.py`/`picks.py`/`scheduler.py`/`db.py` (dry-run sink)/`cli.py`, in-repo `tfs` protobuf encoder golden-tested against the research string, 9 adapter modules (8 stubs raising `SourceDisabled`), `supabase/migrations/0001_init.sql` + `pglast` syntax test. `run --dry-run` already produces `out/<run_id>.json`.
2. **Google Flights adapter end-to-end** — `browser.py` (headless Chromium, persistent profile, block detection, artifacts, page-load budget, jitter), aria-label results parser, booking-page parser (providers, "taxes + fees for N passengers", bag text), 3 loads (default/Best, Cheapest `tfu`, Duration `tfu`) + up to 3 booking visits with dedup, runner with retries/breaker, captured fixtures, one opt-in live smoke test.
3. **Supabase ingestion + rotation state** — `SupabaseSink` upserts (`searches` on natural key + `scrape_date`, `itineraries` on `(search_id, pick)`), rotation state from the `cell_last_scraped` view, idempotency tests with a fake client, `db-check`, README section for the website.
4. **Scheduler, CLI polish, ops, README** — `run_daily.sh`, `flight-scraper.service/.timer` (06:30 ± 45 min, `Persistent=true`), install script with WSL2 prerequisites, rotating logs, `health`, artifact pruning, complete README.
5. **Hardening (optional)** — RPC JSON cross-check (`GetShoppingResults`/`GetBookingResults`), patchright path verified, passenger-derived booking-load experiment, manual `probe` command + playbook for enabling WestJet/Air Canada, selector-drift alarm.

**Sources:** enabled = `google_flights` (DOM, priority 1). Disabled with reasons in `sources.disabled_reason` and in each stub: `westjet` (no confirmed deep link; first to enable), `air_canada` (Akamai + ToS + dummy-passenger review step), `kayak` (PerimeterX/HUMAN, robots/ToS, no checkout), `air_transat` (no deep link, Imperva), `skyscanner` (PerimeterX, partner-only links), `porter` (Cloudflare, booking host unreachable), `flair` (Cloudflare 403), `expedia` (Akamai 429 on first request).

**Schema highlights:** `sources`, `routes` (12 seeded pairs), `search_runs`, `searches` (natural key + `offset_days` + `scrape_date`; unique key includes `child_ages smallint[]` and `scrape_date` so same-day re-runs upsert and other days accumulate history), `itineraries` (pick, pick_rule, both legs' local times/durations/stops, `price_total_cad` = cheapest booking-page provider, `price_results_cad`, `price_provider`, `price_stage`, `carry_on_included`, `carry_on_fee_cad`, `checked_bag_fee_cad` (low end; range in `raw`), `luggage_source`, `price_insight`, `deep_link_url` = booking URL, `raw jsonb`), views `latest_prices` (per exact dates/pax/pick), `latest_prices_by_offset` (per ≈30/60/90-day bucket), `cell_last_scraped` (scraper only). RLS on all tables; anon/authenticated = SELECT on `itineraries` + the two public views only; service role writes.

**Budget math:** one search = 3 results loads + 3 × (return list + booking page) = 9 loads max (7–8 typical with dedup) → 4–5 searches per 40-load run (~10 min). 144 cells with priorities 3/2/1/1 → 1-adult cells refresh every ≈ 17 days, 2-adult ≈ 25, child configs ≈ 50. Levers (config-only): A budget 120/day → ≈ 6 days; B `booking_visits: best_only` → ≈ 10 days; C drop +90 or `1a2c`; D Phase-5 passenger-derived booking loads.

## Decisions Needed
- **Approve the seed watch-list**: YQB + YUL × {YYZ, YVR, FLL, MCO, CUN, CDG}, +30/+60/+90 days snapped to the next Saturday, 7-night stay, pax `1a`/`2a`/`1a1c`/`1a2c`.
- **Pick a refresh lever** (or accept ≈ 17/25/50-day refresh): raise `max_page_loads_per_run` to 120, and/or set `booking_visits: best_only` (Cheapest/Fastest then carry `price_stage='results'`), and/or trim the matrix.
- **Confirm the return-leg rule** for booking visits: Best → Google's first return row; Cheapest → min-price return; Fastest → min-duration return.
- **Confirm block handling**: abort the nightly run after 2 consecutive blocks (no captcha/consent automation); treat a `consent.google.com` page as a block rather than clicking "Reject all".
- **Confirm the in-repo `tfs` encoder** (golden-tested) instead of a runtime dependency on `faster-flights`.
- **Default child age 8** is irrelevant for Google (no age) — confirm `child_ages = []` is acceptable for the website.

## Blockers
- Supabase project URL and keys (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY` = `sb_secret_…`) not yet provided — blocks only the live parts of Phase 3 (everything else runs offline / `--dry-run`).
- systemd in WSL2 (`[boot] systemd=true`) and a Windows keep-alive task must be set up by the user before the Phase-4 timer can fire; unit install needs sudo once.

## Next Step
Execute Phase 1 via prompt 003 (`.prompts/003-flight-scraper-implement/003-flight-scraper-implement.md`), then Phases 2–5 sequentially, marking each phase `status="done"` in `flight-scraper-plan.md`.

---
*Confidence: medium-high (Google flow, URL encoder, schema high; markup stability, refresh math and WSL2 keep-alive medium)* *Iterations: 1* *Full output: flight-scraper-plan.md*
