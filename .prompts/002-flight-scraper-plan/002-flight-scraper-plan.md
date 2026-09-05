<objective>
Create an implementation roadmap and data design for **flight-scraper**: a scheduled Python + Playwright scraper that, for a fixed watch-list of round-trip routes departing YQB and YUL, extracts from each feasible source the **cheapest**, **fastest**, and **best** itinerary — with final checkout price, luggage (cabin/checked) pricing, and deep-link URL — across passenger configurations, and upserts everything into **Supabase** for consumption by the user's website.

Purpose: Give prompt 003 an unambiguous, phase-by-phase build order plus a finalized Supabase schema, watch-list config, and per-source adapter contract.
Input: @.prompts/001-flight-scraper-research/flight-scraper-research.md
Output: `.prompts/002-flight-scraper-plan/flight-scraper-plan.md`
</objective>

<context>
Research findings: @.prompts/001-flight-scraper-research/flight-scraper-research.md

Fixed requirements from the user (do not relax):
- Origins: YQB and YUL only. Round-trip.
- Sources requested: Google Flights, Kayak, Expedia, Skyscanner, Air Canada, Air Transat, WestJet, Porter, Flair. Free scraping only — no paid APIs, proxies, or CAPTCHA services. If research marks a source red, include it as a **disabled adapter with a documented reason**, not silently dropped.
- Per source × route × date × pax config, capture 3 picks: cheapest, fastest, best. "Same companies" for every route — every enabled source runs for every watch-list row.
- Passenger matrix: 1 adult; 2 adults; 1 adult + 1 child; 1 adult + 2 children (children need an accompanying adult; default child age from research, else 8).
- Luggage: whether a cabin bag (carry-on) is included in the quoted fare, carry-on fee if not, and 1st checked bag fee — each as CAD amounts or NULL with a `luggage_source` note (results page / fare-family page / airline policy table).
- Price = "end of transaction" total incl. taxes/fees at the deepest reachable step without paying or logging in; record `price_stage` (results | fare_select | review) so the website can show what the number means.
- Stack: Python 3.12+, Playwright (+ stealth layer chosen by research), supabase-py. Runs on the user's WSL2 Linux box (headed via xvfb if needed).
- Supabase host: NOT yet provided — use `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` env vars; the website reads with the anon key under RLS.
- Watch-list: the user said "as you think is best". Propose a seed list in the plan (see planning_requirements).
</context>

<planning_requirements>
Thoroughly analyze the research and consider multiple approaches before committing; carefully evaluate trade-offs where the research is medium/low confidence.

1. **Source decisions**: For each of the 9 sources, choose DOM / XHR / disabled, citing the research finding. Order adapters by build priority (highest-confidence first).
2. **Seed watch-list** (`config/watchlist.yaml`): both origins × ~6 destinations covering domestic (YYZ, YVR), US sun (FLL, MCO), Caribbean/Mexico (CUN), Europe (CDG). Departures at +30, +60, +90 days from run date; 7-night stay. Justify the choice briefly and make dates relative so the list never goes stale.
3. **Supabase schema** (SQL migration text, ready to paste into the SQL editor):
   - `sources` (id, name, kind: ota|airline|meta, enabled, disabled_reason)
   - `routes` (origin, destination, active)
   - `search_runs` (run_id, started_at, finished_at, git_sha, status)
   - `searches` (run_id, source_id, route_id, depart_date, return_date, adults, children, child_ages, status, error, blocked bool, page_url)
   - `itineraries` (search_id, pick: cheapest|fastest|best, airline(s), flight numbers, depart/arrive times, duration_min, stops, fare_family, price_total_cad, price_stage, currency_raw, carry_on_included bool, carry_on_fee_cad, checked_bag_fee_cad, luggage_source, deep_link_url, raw jsonb, scraped_at)
   - a `latest_prices` view for the website (one row per source/route/dates/pax/pick from the most recent successful run)
   - Idempotency: unique key so re-running the same day upserts instead of duplicating; index for website queries.
   - RLS: anon = SELECT on `latest_prices`/`itineraries` only; service role = all.
4. **Adapter contract**: one `BaseAdapter` with `build_url(query) -> str`, `search(page, query) -> list[Itinerary]`, `enrich_luggage(page, itinerary) -> Itinerary`, `select_picks(itineraries) -> dict[pick, Itinerary]`. Define the shared **"best" scoring rule** for sources without a native best sort (from research §12), and state that native Best/Cheapest/Fastest tabs are used when present.
5. **Politeness & resilience**: per-source concurrency = 1, randomized delays, max searches per run per source, retry policy, block detection (HTTP 403/429, captcha page markers) → mark search `blocked=true` and continue; never attempt captcha solving. Persist HTML/screenshot of failures to `artifacts/` for selector repair.
6. **Scheduling**: pick cron vs systemd timer for WSL2 per research; daily run; log rotation; a `--dry-run` and `--source X --route YUL-CDG` CLI for debugging.
7. **Testing strategy**: unit tests for URL builders and pick selection (pure functions), fixture-based parser tests from saved HTML/JSON, one opt-in live smoke test per adapter.
8. **Phases** sized for one prompt each (prompt 003 will execute Phase 1 → N sequentially). Suggested shape: (1) scaffold + config + Supabase schema + models; (2) Google Flights adapter end-to-end into Supabase; (3) airline adapters (AC, Transat, WestJet, Porter, Flair) with luggage enrichment; (4) OTA adapters (Kayak, Expedia, Skyscanner) or disabled stubs; (5) scheduler, CLI, `latest_prices` view, README for the website consumer. Adjust to research.
</planning_requirements>

<output_structure>
Save to: `.prompts/002-flight-scraper-plan/flight-scraper-plan.md`

Write incrementally (skeleton first, then append each phase/section).

```xml
<plan>
  <summary>{One paragraph overview}</summary>

  <source_decisions>
    <source name="" approach="dom|xhr|disabled" priority="1..9" reason="" research_ref=""/>
  </source_decisions>

  <watchlist_seed>{YAML block for config/watchlist.yaml + passenger matrix}</watchlist_seed>

  <schema>{Full SQL migration incl. RLS policies and latest_prices view}</schema>

  <adapter_contract>{Python interface sketch + Itinerary dataclass + best-scoring rule}</adapter_contract>

  <phases>
    <phase number="1" name="">
      <objective/>
      <tasks><task priority="high"/></tasks>
      <deliverables><deliverable>{file paths}</deliverable></deliverables>
      <dependencies/>
      <execution_notes>{hints for the implementing Claude: what to test, what to avoid and why}</execution_notes>
    </phase>
  </phases>

  <metadata>
    <confidence level=""/>
    <dependencies/>
    <open_questions/>
    <assumptions/>
  </metadata>
</plan>
```
</output_structure>

<summary_requirements>
Create `.prompts/002-flight-scraper-plan/SUMMARY.md`:

# Flight Scraper Plan Summary
**{One-liner, e.g., "5-phase build: scaffold+schema → Google Flights → 5 airlines → OTAs → scheduler; 6 sources enabled, 3 disabled"}**
## Version — v1
## Key Findings — phase list with objectives; enabled/disabled sources; schema highlights
## Decisions Needed — specific: e.g., "Approve seed watch-list destinations", "Approve default child age 8", "Accept results-page price for OTAs"
## Blockers — "Supabase project URL/keys not yet provided" if still true
## Next Step — "Execute Phase 1 via prompt 003"
---
*Confidence: …* *Iterations: 1* *Full output: flight-scraper-plan.md*
</summary_requirements>

<verification>
1. Every one of the 9 sources appears in `<source_decisions>` with a research reference
2. Schema SQL is syntactically valid Postgres (mentally check: types, PK/FK, unique constraints, policies reference existing tables)
3. Phases are sequential; each has concrete file deliverables; each is one-prompt sized
4. Passenger matrix and luggage fields are present end-to-end (config → adapter → schema → view)
5. Metadata captures every assumption made where research was medium/low confidence
</verification>

<success_criteria>
- Plan addresses all planning_requirements 1–8
- Prompt 003 can execute Phase 1 with zero further design decisions
- Schema is paste-ready for the Supabase SQL editor
- SUMMARY.md lists concrete decisions for the user
</success_criteria>
