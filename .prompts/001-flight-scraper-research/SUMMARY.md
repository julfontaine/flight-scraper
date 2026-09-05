# Flight Scraper Research Summary

**Google Flights alone delivers everything required — live-verified today from your WSL2 box: a `tfs` deep link with 2 adults + 1 child loads Best/Other itineraries in CAD in plain headless Chromium (no stealth, no proxy, no captcha in 11 loads), Cheapest and Fastest are one-parameter URL states (`tfu=EgoIABAAGAAgAigB` / `tfu=EgYIBRAAGAA`), and the booking page shows per-provider totals incl. taxes for all passengers plus "1 free carry-on / 1st checked bag CA$150–170" text — while both Python libraries (fast-flights 3.1.0, faster-flights 3.8.0) are unusable as the data path (1 "lure" row; child passengers and round-trip step broken).**

## Version — v1

## Key Findings

Scope was re-focused on Google Flights (Google Vols) mid-research at your request; the other 8 sources remain in the full report as an appendix.

**Google Flights (GREEN — in scope)**
- Deep link: `https://www.google.com/travel/flights/search?tfs=<protobuf>&hl=en-US&curr=CAD&gl=CA`; `tfs` built by `faster-flights`/`fast-flights` `create_query(...).params()["tfs"]` (legs, ADULT/CHILD/INFANT enums, cabin, max_stops, bag counts, exclude-basic). Google's child has no age (2–11).
- Best / Cheapest / Fastest: default load = "Top departing flights" (Best) + "Other departing flights" in one page; Cheapest tab = `&tfu=EgoIABAAGAAgAigB`; Duration sort = `&tfu=EgYIBRAAGAA` (or sort the Best load locally — rows already carry total price and total duration). ~3 s per load, 18–26 rows for YUL→CDG, 2–4 for YQB→CDG.
- Extraction: each `li.pIav2d` row's first `aria-label` is a full sentence ("From 2173 Canadian dollars round trip total. 1 stop flight with Porter Airlines and Air Transat … Total duration 11 hr 30 min …"). Headings vary by locale/route, so parse aria-labels, and wait for the second group / "more flights" button (rows stream in). Underlying JSON RPCs (`GetShoppingResults`, `GetBookingResults`) are interceptable.
- Final price + luggage: click outbound → return → `/travel/flights/booking?tfs=…` (stable deep link) lists "Book with Air Transat CA$2,173 / FlightHub CA$2,254 / …", "Prices include required taxes + fees for 3 passengers", and per-itinerary bag text ("1 free carry-on per passenger", "1st checked bag per passenger: CA$150–170"), plus price-insight low/typical/high. No login. Actual payment stays on the airline/OTA.
- Anti-bot: Google WAF + rate limiting only (no Akamai/PX/DataDome/Cloudflare); ~30 requests in 15 min from the residential IP drew no 429. robots.txt disallows `/travel/flights/search`; Google ToS ties automated access to robots.txt — keep volume low and human-paced.
- Libraries: `fast-flights` 3.1.0 fails to import (missing `typing_extensions`) and returns 1 server-rendered "lure" itinerary; `faster-flights` 3.8.0 `rpc-first` returns 9 grouped itineraries in 0.5 s for adults only, falls back to 1 row with a child, return-leg step broken (issue #3), hard-coded March-2026 build label + pending BotGuard requirement (issue #4). Use them only as `tfs` builders.

**Recommended stack**: Playwright 1.62 headless Chromium (patchright + persistent profile kept as insurance), `faster-flights` for URL building, home WSL2 + systemd timer (residential IP; GitHub Actions runners are datacenter IPs), Supabase upsert on `(source, origin, destination, depart_date, return_date, adults, child_ages, cabin, variant)` with `sb_secret_` server-side and `sb_publishable_` + RLS public-read on the site.

**Appendix (out of scope, reference only)**: Kayak (deep link works, PerimeterX/HUMAN, ToS/robots forbid), Skyscanner (official params incl. child ages, PerimeterX confirmed), Expedia (official deep link, Akamai → 429 on first request), Air Canada (deep link confirmed, Akamai), Air Transat (no deep link, Imperva), WestJet (Vue app, no confirmed deep link, no vendor markers), Porter (Cloudflare challenge, booking host unreachable), Flair (Cloudflare 403). Fare families and 2026 bag rules for all five Canadian carriers are documented in the report.

## Decisions Needed
- Accept the Google booking-page total (taxes + fees, all passengers) as the stored "final price", with bags/seats as separate fields, instead of following the "Continue" handoff to the airline checkout?
- Best = Google's #1 "Top departing flight" (native), Cheapest/Fastest = min price / min total duration over the same load — or dedicated Cheapest-tab and Duration-sort loads (adds 2 page loads, may surface extra OTA fares)?
- Passenger configs to schedule (adults × child ages × infants; infants change the result set) and default child age 8 (Google stores only "child")?
- Run volume/frequency given robots.txt disallow (e.g., ≤ 40 page loads per run, once daily, jittered)?
- DOM aria-label parsing (recommended v1) vs RPC JSON interception (richer, less stable) — or both with cross-checks?

## Blockers
None for Google Flights. (Library data paths are broken but not needed; only their URL builders are used.)

## Next Step
Create flight-scraper-plan.md (prompt 002) for a Google-Flights-only scraper: URL builder, Playwright flow (Best → Cheapest → Duration → booking page), aria-label parser + smoke test, Supabase schema/upsert, systemd scheduling and rate limits.

---
*Confidence: high for Google Flights (executed end-to-end today); medium-high for appendix sources* *Iterations: 1* *Full output: flight-scraper-research.md*
