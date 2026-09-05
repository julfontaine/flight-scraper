<session_initialization>
Before beginning research, verify today's date:
!`date +%Y-%m-%d`

Use this date when searching for "current" or "latest" information (search "2026", not "2024").
</session_initialization>

<research_objective>
Research the feasibility, URL formats, page structures, anti-bot posture, and extraction strategy for scraping flight prices from 9 sources, for round-trip flights departing YQB (Québec City) and YUL (Montréal), using **Python + Playwright and free tooling only** (no paid flight APIs, no paid proxy or CAPTCHA services).

Purpose: Inform the architecture plan (002) and implementation (003) of a scheduled scraper that stores, in Supabase, the **cheapest / fastest / best** itinerary per source, per route, per date, per passenger configuration, with **final checkout price** and **luggage (cabin + checked bag) pricing**, and a deep-link URL. The data is later read by the user's website.
Scope: Sources, extraction feasibility, luggage/fare-rule data availability, passenger-configuration URL parameters, anti-bot mitigation, Supabase ingestion patterns, scheduling on WSL2/Linux.
Output: `.prompts/001-flight-scraper-research/flight-scraper-research.md` with structured findings.
</research_objective>

<research_scope>
<include>
**A. Per-source feasibility (enumerate ALL 9 — see verification checklist):**
For each source answer:
1. Deep-link / search URL format encoding: origin, destination, outbound date, return date, adults, children (with child age), cabin class. Give a concrete working URL example for YUL→CDG round trip, 2 adults + 1 child.
2. Does the results page expose "Best", "Cheapest", "Fastest" sorts/tabs natively? What are the URL params or UI selectors to switch between them?
3. Is the data available without JS rendering (embedded JSON / XHR API called by the page) or only via rendered DOM? Identify the XHR endpoint if one exists and whether it is callable with Playwright's request context (cookies/tokens needed).
4. **Final price at end of transaction**: can we reach a checkout/review page with the total incl. taxes & fees WITHOUT paying and WITHOUT logging in? On OTAs, does the flow hand off to the airline? Document how far Playwright can go.
5. **Luggage**: does the site show whether a carry-on (cabin bag) is included in the displayed fare, and the price of the 1st checked bag? At which step (results / fare-family picker / extras page)? For the 5 Canadian carriers, list current fare families (e.g., Air Canada Basic/Standard/Flex, Transat Eco Budget/Eco Standard, WestJet UltraBasic/Basic/Econo, Porter Basic/Standard, Flair Bundles) and which include a carry-on.
6. Anti-bot protection in place (Akamai Bot Manager, PerimeterX/HUMAN, DataDome, Cloudflare, reCAPTCHA/hCaptcha) and observed tolerance for low-volume headless Playwright. Evidence from recent (2025–2026) open-source projects and issue trackers.
7. Terms-of-service stance on automated access, and robots.txt entries for the search paths — report factually; the plan will decide rate limits and which sources to keep.

**B. Cross-cutting:**
8. Best free Python stealth options for Playwright in 2026: `patchright`, `camoufox`, `playwright-stealth`, `nodriver`, `scrapling`. Compare maintenance status, detection results, headless vs headed on Linux/WSL2 (xvfb), and how they integrate with sync/async Playwright.
9. Existing open-source Google Flights scrapers (e.g., `fast-flights` by AWeirdDev and its `tfs` protobuf URL encoding; others) — do they still work as of today, and do they support children/child ages and returning "best/cheapest/fastest"?
10. Supabase ingestion from Python: `supabase-py` upsert patterns, batch size limits, using service-role key server-side vs anon key on the website, RLS policy shape for "public read-only, scraper write". Note Postgres `on conflict` idempotency keys for repeated daily runs.
11. Scheduling on WSL2/Linux: cron vs systemd timers vs GitHub Actions (free tier limits, Playwright browser install in Actions, IP reputation of GitHub runners vs residential IP at home).
12. Definition of "best" when a site has no native "best" sort (airline sites): survey how Google Flights/Kayak/Skyscanner define it (price × duration × stops heuristics) so the plan can define a comparable local scoring rule.
</include>

<exclude>
- Writing production code (implementation is prompt 003) — short snippets to prove a URL format or selector are fine.
- Paid APIs (Amadeus, Duffel, Kiwi Tequila, SerpAPI, Skyscanner partner API) — mention only if a **free tier** is genuinely usable, as a fallback note.
- CAPTCHA-solving services or any bypass of explicit access controls — out of scope; if a source hard-blocks, report it as blocked.
- Website/front-end design consuming the data.
</exclude>

<sources>
Official / primary (use WebFetch with exact URLs):
- https://playwright.dev/python/docs/intro
- https://playwright.dev/python/docs/network (route/response interception)
- https://github.com/AWeirdDev/flights (fast-flights, Google Flights `tfs` encoding)
- https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python
- https://github.com/daijro/camoufox and https://camoufox.com/python/
- https://github.com/AtuboDad/playwright_stealth
- https://github.com/D4Vinci/Scrapling
- https://supabase.com/docs/reference/python/upsert
- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://supabase.com/docs/guides/api/api-keys
- https://www.aircanada.com/ca/en/aco/home/book/travel-news-and-updates/fare-options.html (fare families) — or current equivalent
- https://www.airtransat.com/en-CA/travel-information/baggage (and fare options page)
- https://www.westjet.com/en-ca/fares (fare bundles) and baggage fees page
- https://www.flyporter.com/en-ca/travel-information/fares
- https://www.flyflair.com/travel-info/baggage (and bundles)
- robots.txt for: google.com, kayak.com, expedia.ca, skyscanner.ca, aircanada.com, airtransat.com, westjet.com, flyporter.com, flyflair.com

Search queries (use WebSearch, include the current year):
- "google flights scraper python playwright 2026"
- "fast-flights tfs protobuf children age"
- "kayak flights url parameters adults children sort bestflight"
- "skyscanner url format adults children cabinclass 2026"
- "expedia flights url parameters scraping 2026"
- "aircanada.com booking deep link url parameters"
- "airtransat booking url parameters org dest depDate retDate"
- "westjet.com flights url parameters adults children"
- "flyporter deep link booking url"
- "flyflair booking url parameters"
- "playwright stealth detection 2026 patchright vs camoufox"
- "Akamai bot manager playwright headless 2026" / "PerimeterX kayak scraping 2026" / "expedia datadome scraping"
- "supabase python upsert on_conflict batch"
- "GitHub Actions playwright chromium install ubuntu 2026"

Prefer sources dated 2025–2026; flag anything older as possibly stale.
</sources>
</research_scope>

<verification_checklist>
**CRITICAL — enumerate ALL 9 sources; each must be documented or explicitly marked "not found / blocked":**
□ Google Flights (google.com/travel/flights) — URL/tfs encoding, Best/Cheapest tabs, "duration" sort, luggage icons on fare rows, child age param
□ Kayak (kayak.com or ca.kayak.com) — URL format, `sort=bestflight_a|price_a|duration_a`, fee assistant (bag toggles), handoff to airline
□ Expedia (expedia.ca) — URL format, sort options, checkout reachability, bag fee display
□ Skyscanner (skyscanner.ca) — URL format, Best/Cheapest/Fastest tabs, handoff behaviour, anti-bot
□ Air Canada — booking URL, fare families, carry-on inclusion, 1st bag fee, review-page total
□ Air Transat — booking URL, fare options, carry-on inclusion, bag fee, review-page total
□ WestJet — booking URL, fare bundles (UltraBasic excludes carry-on?), bag fee, review-page total
□ Porter — booking URL, fare classes, carry-on inclusion, bag fee, review-page total
□ Flair — booking URL, bundles, carry-on fee (Flair charges for carry-on on base fare), bag fee, review-page total

For each: existence of a working deep link (confirmed / not found / unclear), official URL, protection vendor, confidence.

□ Verify child-age handling per source (what ages count as "child" vs "infant"; default age to use, e.g. 8)
□ Verify that "cheapest / fastest / best" can be obtained from ONE results page load per (route, date, pax config) or requires multiple loads
□ Verify negative claims ("cannot reach checkout without login") with a concrete attempt description or a 2025–2026 source
□ Check both current docs AND recent GitHub issues for breakage of the libraries recommended
□ Check Canadian-site variants (.ca) vs .com — pricing in CAD, French/English locale effects on selectors
</verification_checklist>

<research_quality_assurance>
<completeness_check>
- [ ] All 9 sources documented with evidence, or marked blocked/not found with reason
- [ ] Each source evaluated against ALL 7 per-source questions
- [ ] Official documentation cited for library and Supabase claims
- [ ] Contradictory information resolved or flagged
</completeness_check>
<source_verification>
- [ ] Primary claims backed by official/authoritative sources with URLs
- [ ] Library version numbers and dates included
- [ ] Distinguish verified facts from assumptions (e.g., "URL format inferred from a 2024 repo, untested")
</source_verification>
<blind_spots_review>
- [ ] Did I check whether an XHR/JSON endpoint exists before assuming DOM scraping?
- [ ] Did I check French-locale (fr-CA) vs English rendering differences?
- [ ] Did I verify definitive claims ("cannot", "only", "always blocks")?
- [ ] Did I look for 2025–2026 breakage reports of fast-flights / patchright / camoufox?
</blind_spots_review>
<critical_claims_audit>
For any "X is not possible" or "Y is the only way": verified by official docs or recent reproducible report? Alternative approaches considered?
</critical_claims_audit>
</research_quality_assurance>

<efficiency>
For maximum efficiency, invoke independent WebFetch/WebSearch calls in parallel (e.g., fetch all robots.txt files in one batch; all airline fare-family pages in one batch).
</efficiency>

<output_requirements>
Save to: `.prompts/001-flight-scraper-research/flight-scraper-research.md`

**Write incrementally** — create the file first with this skeleton, then append each `<finding>` immediately after investigating each source/topic. Never hold the full report in memory until the end.

```xml
<research>
  <summary>[Complete at end]</summary>
  <source_matrix>
    <!-- One row per source: feasibility (green/yellow/red), URL deep link (yes/no), native best/cheapest/fastest (yes/no), checkout total reachable (yes/no/partial), carry-on info (yes/no), checked-bag fee (yes/no), protection vendor, recommended approach (DOM / XHR / skip) -->
  </source_matrix>
  <findings>
    <finding category="{source-name | stealth | supabase | scheduling | best-definition}">
      <title/>
      <detail/>
      <example_url/>           <!-- concrete, for per-source findings -->
      <selectors_or_endpoints/><!-- CSS/ARIA selectors or XHR endpoints observed/reported -->
      <source/>
      <relevance/>
      <confidence>high|medium|low — why</confidence>
    </finding>
  </findings>
  <recommendations>
    <recommendation priority="high|medium|low"><action/><rationale/></recommendation>
  </recommendations>
  <code_examples>
    <!-- URL builders per source, fast-flights usage, patchright launch snippet, supabase-py upsert with on_conflict, Playwright response interception -->
  </code_examples>
  <metadata>
    <confidence level=""/>
    <dependencies/>
    <open_questions/>
    <assumptions/>
    <quality_report>
      <sources_consulted/><claims_verified/><claims_assumed/><contradictions_encountered/><confidence_by_finding/>
    </quality_report>
  </metadata>
</research>
```
</output_requirements>

<summary_requirements>
Create `.prompts/001-flight-scraper-research/SUMMARY.md`:

# Flight Scraper Research Summary
**{Substantive one-liner: e.g., "Google Flights + 4 airline sites feasible via Playwright; Kayak/Expedia/Skyscanner likely blocked without residential proxy"}**
## Version — v1
## Key Findings — the source matrix condensed (green/yellow/red per source), recommended stealth stack, best/cheapest/fastest strategy, luggage data availability
## Decisions Needed — e.g., "Drop Skyscanner?", "Accept results-page price instead of checkout price for OTAs?", "Default child age 8?"
## Blockers — or "None"
## Next Step — "Create flight-scraper-plan.md (prompt 002)"
---
*Confidence: …* *Iterations: 1* *Full output: flight-scraper-research.md*
</summary_requirements>

<pre_submission_checklist>
- [ ] All 9 sources covered in source_matrix and findings
- [ ] Every per-source finding has a concrete example URL or is marked "no deep link found"
- [ ] Negative claims cite a source or a described attempt
- [ ] Library versions + dates listed
- [ ] Quality report filled honestly; confidence per finding
- [ ] SUMMARY.md created with substantive one-liner and Decisions Needed
</pre_submission_checklist>

<success_criteria>
- Plan author (002) can decide, per source, DOM vs XHR vs skip, without further research
- Concrete URL builders exist for every feasible source, including passenger params
- Luggage data availability per source is explicit
- A defensible definition of "best" is proposed for sources lacking a native one
- Supabase upsert + RLS pattern documented with official citations
- Metadata and quality report distinguish verified from assumed
</success_criteria>
