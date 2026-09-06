<plan>
  <summary>
flight-scraper v1 is a Google-Flights-only, Playwright-driven scraper that runs once a day from the user's home WSL2 box (residential IP, systemd timer with randomized jitter, single persistent browser context, headless Chromium as live-verified in research). For every watch-list cell (12 round-trip routes from YQB/YUL × departures at +30/+60/+90 days snapped to the next Saturday, 7-night stay × 4 passenger configurations) it builds a protobuf `tfs` deep link, loads the default results page (Google's #1 "Top departing flight" = Best), the Cheapest tab (`tfu=EgoIABAAGAAgAigB`) and the Duration sort (`tfu=EgYIBRAAGAA`), parses each `li.pIav2d` row's aria-label sentence, then for each of the three picks clicks outbound → return to reach the `/travel/flights/booking?tfs=…` page, where it records the per-provider totals (taxes and fees included, all passengers), the cheapest provider as `price_total_cad` with `price_stage='booking'`, the bag text ("1 free carry-on per passenger", "1st checked bag per passenger: CA$150–170") as `carry_on_included` / `checked_bag_fee_cad` with `luggage_source='google_booking_page'`, and the booking URL as `deep_link_url`. One search costs at most 9 page loads (3 results loads + 3 × (return list + booking page)), so a 40-load daily budget covers 4–5 searches; a weighted oldest-first rotation (stored in Supabase, or a local state file in `--dry-run`) walks the 144-cell matrix so nothing is ever skipped permanently, and the plan spells out the three levers (budget, booking visits, matrix size) that shorten the refresh cycle. Data lands in Supabase via idempotent upserts keyed on the natural search key + scrape date, with RLS giving the website anonymous read access to `itineraries` and a `latest_prices` view only. The other eight requested sources are shipped as disabled adapter stubs (each raising `SourceDisabled(reason)` with the research finding), the adapter contract stays generic, and five sequential one-prompt phases take the project from scaffold → Google adapter → Supabase ingestion → scheduler/CLI/README → optional hardening (RPC interception, patchright, passenger-derived booking loads, enabling a second source).
  </summary>

  <source_decisions>
    <!-- approach: dom = Playwright DOM/aria-label parsing; xhr = response interception; disabled = stub adapter raising SourceDisabled(reason). priority = build/enable order (1 = first). -->
    <source name="google_flights" approach="dom" priority="1" reason="GREEN, live-verified 2026-09-04 from this WSL2 host: tfs deep link with children loads 18–26 CAD itineraries in plain headless Chromium (no stealth, no captcha in 11 loads); Best = default load's first 'Top departing' row, Cheapest/Fastest are tfu URL states; booking page exposes per-provider totals incl. taxes for all pax + carry-on/checked-bag text; no Akamai/PX/DataDome/Cloudflare, only Google WAF + rate limiting. robots.txt disallows the search path → keep volume ≤ 40 loads/day, human-paced. v1 parses aria-labels (human-facing, locale-pinned en-US); RPC JSON interception (GetShoppingResults/GetBookingResults) is a Phase-5 hardening option." research_ref="source_matrix row 'Google Flights'; findings category=google-flights ('LIVE VERIFICATION', 'Library assessment', 'deep link via protobuf tfs'); recommendations priority=high #1–#4"/>
    <source name="westjet" approach="disabled" priority="2" reason="No confirmed deep link (booking is a Vue SPA at /shop/*; query-string contract unknown, must be recorded by form-driving /en-ca/flights); no checkout verified; ToS page 404 (stance unknown); robots disallows /*/search. It has the weakest visible anti-bot of the five carriers (no PX/Akamai/DataDome markers), so it is the first non-Google source to enable after a headed probe from the home IP." research_ref="source_matrix row 'WestJet'; finding category=westjet"/>
    <source name="air_canada" approach="disabled" priority="3" reason="Deep link confirmed (org0/dest0/departureDate0/ADT/YTH/CHD/INF/INS params, 200 app shell) but Akamai Bot Manager is confirmed (_abck, bm_sz, akamai-grn, sensor script), ToS explicitly forbids automated access/screen scraping, and reaching the review-trip total requires typing dummy passenger data (ethics/ToS decision deferred). Enable only after a headed patchright + persistent-profile probe succeeds." research_ref="source_matrix row 'Air Canada'; finding category=air-canada; finding category=stealth"/>
    <source name="kayak" approach="disabled" priority="4" reason="Deep link and native sort params verified (sort=bestflight_a|price_a|duration_a) but results arrive only via a session-bound poll XHR, PerimeterX/HUMAN 'Press &amp; Hold' (or Akamai — contradictory 2026 reports) protects it, robots.txt disallows /flights/ and ToS §4 forbids scraping/automated tools without written permission; metasearch handoff means no checkout total (price_stage would be 'results')." research_ref="source_matrix row 'Kayak'; finding category=kayak; finding category=terms-of-service"/>
    <source name="air_transat" approach="disabled" priority="5" reason="No public deep link (Kentico site + Softvoyage/TSOnline engine; search form posts via JS, results URL params not exposed); Imperva/Incapsula confirmed; ToS forbids screen-scraping/data mining; checkout reachability unverified. Form-drive + XHR capture is the only path." research_ref="source_matrix row 'Air Transat'; finding category=air-transat"/>
    <source name="skyscanner" approach="disabled" priority="6" reason="Official referral URL format works (adultsv2/childrenv2 with ages) but PerimeterX is confirmed (_pxhd) with a Feb-2026 open issue reporting persistent 403 'Access banned. CAPTCHA challenge' across IPs; robots disallows /transport/*; deep links are partner-programme only; no bag data on results and no checkout." research_ref="source_matrix row 'Skyscanner'; finding category=skyscanner"/>
    <source name="porter" approach="disabled" priority="7" reason="Booking host (booking.flyporter.com) timed out from the probe host and www.flyporter.com serves a Cloudflare managed challenge; no deep link; robots disallows booking paths and ClaudeBot entirely; ToS forbids spiders/robots. Needs a headed probe from the home IP before any planning." research_ref="source_matrix row 'Porter'; finding category=porter"/>
    <source name="flair" approach="disabled" priority="8" reason="Cloudflare 403 block page to non-browser clients (not just a JS challenge), booking subdomain does not resolve, no deep link, ToS forbids screen-scraping/crawling. Bag pricing is a-la-carte and only modellable as ranges without site access." research_ref="source_matrix row 'Flair'; finding category=flair"/>
    <source name="expedia" approach="disabled" priority="9" reason="Official deep link exists, but Akamai Bot Manager returned HTTP 429 on the very first request (most aggressive of the nine), robots.txt disallows /Flights-Search and /Checkout, ToS forbids scrapers and bypassing access controls, and the checkout total needs 5+ unverified JS steps. Revisit last, only after a headed patchright probe succeeds." research_ref="source_matrix row 'Expedia'; finding category=expedia"/>
  </source_decisions>

  <watchlist_seed>
Why these cells: both origins × six destinations cover the four markets the user's site needs — domestic (YYZ, YVR), US sun (FLL, MCO), Caribbean/Mexico (CUN), Europe (CDG, the research's live-verified route) — and every one of them is served from YUL by ≥ 3 of the five Canadian carriers, so Best/Cheapest/Fastest actually diverge. Departures are relative to the run date (+30/+60/+90 days) and snapped to the **next Saturday** with a 7-night Saturday-to-Saturday stay: the list never goes stale, and because the concrete dates only move once a week, up to seven consecutive runs of the same cell hit identical dates and produce comparable price history instead of a moving target. Google has no child age, so `child_ages` is recorded for provenance only and is `[]` in v1; no infant configs (they change the result set — research finding google-flights §8).

```yaml
# config/watchlist.yaml — flight-scraper v1 seed watch-list
# All dates are RELATIVE to the run date; nothing in this file expires.
version: 1

defaults:
  cabin: economy
  currency: CAD
  stay_nights: 7
  # depart_date = first Saturday on/after (run_date + offset_days); return_date = depart_date + stay_nights.
  date_rule: next_saturday
  offsets_days: [30, 60, 90]

origins: [YQB, YUL]

destinations:
  - {code: YYZ, region: domestic,          why: "highest-frequency domestic pair from both origins; AC/Porter/WestJet/Flair compete"}
  - {code: YVR, region: domestic,          why: "long-haul domestic; nonstop vs 1-stop makes Fastest != Cheapest"}
  - {code: FLL, region: us_sun,            why: "Florida sun market: AC, Transat, WestJet, Porter, Flair"}
  - {code: MCO, region: us_sun,            why: "Orlando family market — the child configs matter most here"}
  - {code: CUN, region: caribbean_mexico,  why: "top sun/package destination; Transat and WestJet pricing"}
  - {code: CDG, region: europe,            why: "largest transatlantic market from YUL; research golden route (YUL-CDG)"}

# routes = every origin x every destination (12 round-trip routes).
# Replace with an explicit list of {origin, destination, active} entries to skip a pair.
routes: all

passenger_configs:
  # key is used in CLI filters (--pax 1a) and in out/ file names. priority weights the rotation (higher = fresher).
  - {key: 1a,   adults: 1, children: 0, child_ages: [],     priority: 3}
  - {key: 2a,   adults: 2, children: 0, child_ages: [],     priority: 2}
  - {key: 1a1c, adults: 1, children: 1, child_ages: [],     priority: 1}   # Google: child = 2–11, no age
  - {key: 1a2c, adults: 1, children: 2, child_ages: [],     priority: 1}

budget:
  max_page_loads_per_run: 40         # hard cap; a search starts only if remaining >= est_page_loads_per_search
  est_page_loads_per_search: 9       # 3 results loads + 3 x (return-list render + booking page)
  max_searches_per_run: 8            # secondary cap even when dedup makes searches cheaper
  booking_visits: all                # all | best_only | none   (lever B below)
  delays_s:                          # uniform random, seconds
    between_actions: [2, 5]          # clicks inside one page (expand list, select outbound/return)
    between_loads: [4, 9]            # between navigations
    between_searches: [20, 45]
  retry:
    per_search_attempts: 2           # 1 retry on timeout / zero rows without block markers
    retry_pause_s: [15, 30]
  block_pause_s: [60, 120]
  abort_after_consecutive_blocks: 2

rotation:
  strategy: weighted_oldest_first    # score = priority x days_since_last_ok (never-scraped cells first, then by score desc)
  state: supabase                    # supabase | file  (file = out/rotation_state.json, used automatically in --dry-run)

sources:
  - google_flights                   # the only enabled adapter in v1; disabled stubs are listed by `cli sources`
```

**Page-load estimate per search (route × dates × pax):**

| step | loads | notes |
|---|---|---|
| default load (Best) | 1 | first `li.pIav2d` row = Google's #1 Top departing flight |
| Cheapest tab load (`tfu=EgoIABAAGAAgAigB`) | 1 | expand "more flights", take min price |
| Duration sort load (`tfu=EgYIBRAAGAA`) | 1 | single list sorted by duration, take min duration |
| per pick: click outbound → return list renders | 1 each | in-page GetShoppingResults; counted as a load |
| per pick: click return → `/booking` page | 1 each | GetBookingResults; totals + bag text + deep link |
| **total** | **9 max** | 7–8 typical: a booking visit is skipped when a pick's outbound+return equal an already-visited pick (frequent on thin routes such as YQB-CDG with 2–4 rows) |

Run sizing at the agreed `max_page_loads_per_run: 40`: **4 searches guaranteed, 5 typical**, ≈ 90 s per search including jitter → a run takes 8–10 minutes. The matrix has 12 routes × 3 offsets × 4 pax = **144 cells**. With priorities 3/2/1/1 the weighted rotation refreshes 1-adult cells every ≈ 17 days, 2-adult every ≈ 25 days and the two child configs every ≈ 50 days (derivation: 36/T + 36/1.5T + 72/3T = 5 searches/day → T ≈ 17). That is honest but slow; the levers, all config-only, are:
- **A. Budget** `max_page_loads_per_run: 120` (research saw ~30 loads in 15 min with no 429; 120 loads spread over ~40 min at the same pace is still human-scale) → T ≈ 6 days.
- **B. Booking visits** `booking_visits: best_only` → 5 loads/search → 8 searches/run at 40 loads → T ≈ 10 days (Cheapest/Fastest then carry `price_stage='results'` with the results-row round-trip total, which research observed equal to the booking-page airline total in its one sample).
- **C. Matrix** drop the +90 offset or the `1a2c` config (each removes 36 cells).
- **D. (Phase 5, optional)** passenger-derived booking loads: re-encode the passengers field of a pick's booking `tfs` for the other three pax configs (3 loads each instead of 9) → a full route-date costs 18 loads instead of 36; needs verification that Google accepts a re-encoded booking `tfs`.
The default ships as the user decided (40 / all); SUMMARY.md asks which lever(s) to pull.
  </watchlist_seed>

  <schema>
Paste-ready for the Supabase SQL editor (Postgres 15+; runs as the `postgres` role, which owns the view). Design notes: (1) `searches` carries the natural key **plus `scrape_date`** so a second run on the same day upserts onto the same row while different days accumulate price history; (2) `itineraries` is unique on `(search_id, pick)`; (3) `child_ages` is a NOT NULL `smallint[]` (`'{}'` for Google, which has no child age) so it can sit inside the unique constraint; (4) `latest_prices` is a `security_invoker = false` view, so anon can read the joined route/source names without any SELECT policy on those tables — the Supabase docs note that owner-privilege views bypass RLS, which is exactly what we want here; (5) the service role (`sb_secret_` key) bypasses RLS, so no INSERT/UPDATE policies are needed.

```sql
-- supabase/migrations/0001_init.sql  —  flight-scraper v1
-- Idempotent where practical (create table if not exists / on conflict) so it can be re-pasted.

-- ---------------------------------------------------------------- sources
create table if not exists public.sources (
  id              text primary key,                                    -- 'google_flights', 'kayak', ...
  name            text not null,
  kind            text not null check (kind in ('ota', 'airline', 'meta')),
  enabled         boolean not null default false,
  disabled_reason text,
  created_at      timestamptz not null default now()
);

insert into public.sources (id, name, kind, enabled, disabled_reason) values
  ('google_flights', 'Google Flights',        'meta',    true,  null),
  ('westjet',        'WestJet',               'airline', false, 'v1 disabled: no confirmed deep link (Vue SPA /shop/*, query contract unknown); checkout unverified; weakest anti-bot of the airlines, first candidate to enable after a headed probe. Research: finding category=westjet'),
  ('air_canada',     'Air Canada',            'airline', false, 'v1 disabled: Akamai Bot Manager confirmed; ToS forbids automated access; review page needs dummy passenger data (unverified). Deep link exists. Research: finding category=air-canada'),
  ('kayak',          'Kayak (ca.kayak.com)',  'meta',    false, 'v1 disabled: PerimeterX/HUMAN (or Akamai) reported; robots.txt disallows /flights/; ToS s.4 forbids automated tools; metasearch handoff = no checkout total. Research: finding category=kayak'),
  ('air_transat',    'Air Transat',           'airline', false, 'v1 disabled: no deep link (Softvoyage engine, form-drive only); Imperva/Incapsula; ToS forbids screen-scraping. Research: finding category=air-transat'),
  ('skyscanner',     'Skyscanner.ca',         'meta',    false, 'v1 disabled: PerimeterX confirmed (_pxhd), 2026 reports of persistent 403 captcha; robots disallows /transport/*; partner-only deep links; no bag data. Research: finding category=skyscanner'),
  ('porter',         'Porter Airlines',       'airline', false, 'v1 disabled: booking host unreachable from probe, www behind Cloudflare challenge; no deep link; robots disallows booking paths; ToS forbids robots. Research: finding category=porter'),
  ('flair',          'Flair Airlines',        'airline', false, 'v1 disabled: Cloudflare 403 block page to non-browser clients; no deep link; ToS forbids screen-scraping. Research: finding category=flair'),
  ('expedia',        'Expedia.ca',            'ota',     false, 'v1 disabled: Akamai Bot Manager returned HTTP 429 on first request; robots disallows /Flights-Search and /Checkout; ToS forbids scrapers; checkout needs 5+ unverified JS steps. Research: finding category=expedia')
on conflict (id) do update
  set name = excluded.name, kind = excluded.kind, enabled = excluded.enabled, disabled_reason = excluded.disabled_reason;

-- ---------------------------------------------------------------- routes
create table if not exists public.routes (
  id          smallint generated always as identity primary key,
  origin      text not null check (origin ~ '^[A-Z]{3}$'),
  destination text not null check (destination ~ '^[A-Z]{3}$'),
  active      boolean not null default true,
  created_at  timestamptz not null default now(),
  constraint routes_pair_key unique (origin, destination)
);

insert into public.routes (origin, destination)
select o, d
from unnest(array['YQB', 'YUL']) as o
cross join unnest(array['YYZ', 'YVR', 'FLL', 'MCO', 'CUN', 'CDG']) as d
on conflict (origin, destination) do nothing;

-- ---------------------------------------------------------------- search_runs
create table if not exists public.search_runs (
  run_id           uuid primary key default gen_random_uuid(),
  started_at       timestamptz not null default now(),
  finished_at      timestamptz,
  git_sha          text,
  status           text not null default 'running'
                   check (status in ('running', 'ok', 'partial', 'blocked', 'failed')),
  page_loads       integer not null default 0,
  searches_total   integer not null default 0,
  searches_ok      integer not null default 0,
  searches_blocked integer not null default 0,
  host             text,
  notes            text
);

-- ---------------------------------------------------------------- searches
create table if not exists public.searches (
  id           bigint generated always as identity primary key,
  run_id       uuid not null references public.search_runs (run_id) on delete cascade,
  source_id    text not null references public.sources (id),
  route_id     smallint not null references public.routes (id),
  depart_date  date not null,
  return_date  date not null,
  offset_days  smallint,                                               -- watch-list offset that produced depart_date (30/60/90); null for ad-hoc CLI searches
  adults       smallint not null check (adults between 1 and 9),
  children     smallint not null default 0 check (children between 0 and 8),
  child_ages   smallint[] not null default '{}',                       -- '{}' for Google (no child age); ages for future sources
  cabin        text not null default 'economy',
  scrape_date  date not null default current_date,                     -- scraper sets it explicitly to the America/Toronto run date
  status       text not null default 'pending'
               check (status in ('pending', 'ok', 'partial', 'blocked', 'error', 'skipped')),
  error        text,
  blocked      boolean not null default false,
  page_url     text,                                                   -- results deep link (tfs URL, default load)
  page_loads   smallint not null default 0,
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  constraint searches_natural_key unique
    (source_id, route_id, depart_date, return_date, adults, children, child_ages, cabin, scrape_date)
);

create index if not exists searches_route_dates_idx   on public.searches (route_id, depart_date, return_date);
create index if not exists searches_scrape_date_idx   on public.searches (scrape_date desc);
create index if not exists searches_cell_idx          on public.searches (source_id, route_id, offset_days, adults, children, finished_at desc);
create index if not exists searches_run_idx           on public.searches (run_id);

-- ---------------------------------------------------------------- itineraries
create table if not exists public.itineraries (
  id                     bigint generated always as identity primary key,
  search_id              bigint not null references public.searches (id) on delete cascade,
  pick                   text not null check (pick in ('cheapest', 'fastest', 'best')),
  pick_rule              text not null default 'native' check (pick_rule in ('native', 'local-v1')),
  airlines               text[] not null default '{}',                 -- marketing carriers, both legs, deduplicated
  flight_numbers         text[] not null default '{}',                 -- may be empty on Google (see open questions)
  outbound_depart_local  timestamp,                                    -- airport-local wall time (Google shows no tz)
  outbound_arrive_local  timestamp,
  return_depart_local    timestamp,
  return_arrive_local    timestamp,
  outbound_duration_min  integer,
  return_duration_min    integer,
  duration_min           integer,                                      -- outbound + return
  stops                  smallint,                                     -- outbound leg
  return_stops           smallint,
  fare_family            text,                                         -- null on Google unless the booking page names one
  price_total_cad        numeric(10, 2),                               -- cheapest provider total, taxes+fees, all passengers
  price_results_cad      numeric(10, 2),                               -- results-row "round trip total" for cross-check
  price_provider         text,                                         -- provider behind price_total_cad ('Air Transat', 'FlightHub', ...)
  price_stage            text not null check (price_stage in ('results', 'fare_select', 'review', 'booking')),
  currency_raw           text,                                         -- e.g. 'CA$' / 'Canadian dollars' as seen on the page
  carry_on_included      boolean,
  carry_on_fee_cad       numeric(10, 2),
  checked_bag_fee_cad    numeric(10, 2),                               -- low end of a range; raw keeps the range and text
  luggage_source         text,                                         -- 'google_booking_page' | null
  price_insight          text,                                         -- Google's "CA$2,173 is low for Economy ..." sentence
  deep_link_url          text,                                         -- /travel/flights/booking?tfs=... (stable, itinerary-specific)
  raw                    jsonb not null default '{}'::jsonb,           -- aria-labels, providers[], luggage_text[], urls, parser_version
  scraped_at             timestamptz not null default now(),
  constraint itineraries_search_pick_key unique (search_id, pick)
);

create index if not exists itineraries_search_idx     on public.itineraries (search_id);
create index if not exists itineraries_scraped_at_idx on public.itineraries (scraped_at desc);

-- ---------------------------------------------------------------- views
-- One row per source/route/dates/pax/cabin/pick from the most recent successful search of that exact cell.
create or replace view public.latest_prices
  with (security_invoker = false) as
select distinct on (s.source_id, s.route_id, s.depart_date, s.return_date, s.adults, s.children, s.child_ages, s.cabin, i.pick)
  i.id                    as itinerary_id,
  s.id                    as search_id,
  s.run_id,
  s.source_id,
  src.name                as source_name,
  src.kind                as source_kind,
  r.origin,
  r.destination,
  s.depart_date,
  s.return_date,
  s.offset_days,
  s.adults,
  s.children,
  s.child_ages,
  s.cabin,
  i.pick,
  i.pick_rule,
  i.airlines,
  i.flight_numbers,
  i.outbound_depart_local,
  i.outbound_arrive_local,
  i.return_depart_local,
  i.return_arrive_local,
  i.outbound_duration_min,
  i.return_duration_min,
  i.duration_min,
  i.stops,
  i.return_stops,
  i.fare_family,
  i.price_total_cad,
  i.price_results_cad,
  i.price_provider,
  i.price_stage,
  i.currency_raw,
  i.carry_on_included,
  i.carry_on_fee_cad,
  i.checked_bag_fee_cad,
  i.luggage_source,
  i.price_insight,
  i.deep_link_url,
  s.page_url              as results_url,
  s.scrape_date,
  i.scraped_at
from public.itineraries i
join public.searches s   on s.id = i.search_id
join public.routes r     on r.id = s.route_id
join public.sources src  on src.id = s.source_id
where s.status in ('ok', 'partial')
  and s.blocked = false
order by s.source_id, s.route_id, s.depart_date, s.return_date, s.adults, s.children, s.child_ages, s.cabin, i.pick,
         s.finished_at desc nulls last, i.scraped_at desc;

-- Convenience for the website: "about 30/60/90 days out" regardless of which concrete Saturday was scraped last.
create or replace view public.latest_prices_by_offset
  with (security_invoker = false) as
select distinct on (lp.source_id, lp.origin, lp.destination, lp.offset_days, lp.adults, lp.children, lp.child_ages, lp.cabin, lp.pick)
  lp.*
from public.latest_prices lp
where lp.offset_days is not null
order by lp.source_id, lp.origin, lp.destination, lp.offset_days, lp.adults, lp.children, lp.child_ages, lp.cabin, lp.pick,
         lp.scraped_at desc;

-- Rotation state for the scraper (service role only; not granted to anon).
create or replace view public.cell_last_scraped
  with (security_invoker = false) as
select s.source_id, s.route_id, r.origin, r.destination, s.offset_days, s.adults, s.children, s.cabin,
       max(s.finished_at) filter (where s.status in ('ok', 'partial')) as last_ok_at,
       max(s.finished_at)                                               as last_attempt_at,
       bool_or(s.blocked) filter (where s.finished_at > now() - interval '2 days') as blocked_recently
from public.searches s
join public.routes r on r.id = s.route_id
group by s.source_id, s.route_id, r.origin, r.destination, s.offset_days, s.adults, s.children, s.cabin;

-- ---------------------------------------------------------------- RLS
alter table public.sources     enable row level security;
alter table public.routes      enable row level security;
alter table public.search_runs enable row level security;
alter table public.searches    enable row level security;
alter table public.itineraries enable row level security;

-- anon/authenticated: SELECT on itineraries only (plus the views below). No policy on the other tables = zero rows.
drop policy if exists "public read itineraries" on public.itineraries;
create policy "public read itineraries"
  on public.itineraries for select
  to anon, authenticated
  using (true);

-- Service role (sb_secret_ key) bypasses RLS: no insert/update/delete policies are required for the scraper.

-- Views: owner-privilege views (security_invoker = false) read the joined tables as `postgres`; grant SELECT to the website roles.
grant select on public.latest_prices           to anon, authenticated;
grant select on public.latest_prices_by_offset to anon, authenticated;
revoke all   on public.cell_last_scraped      from anon, authenticated;

-- Belt and braces: even though RLS already returns no rows, do not expose raw run/search tables to the public API roles.
revoke all on public.search_runs from anon, authenticated;
revoke all on public.searches    from anon, authenticated;
revoke all on public.sources     from anon, authenticated;
revoke all on public.routes      from anon, authenticated;
```

Website query examples (publishable key, RLS-honouring):
- `select * from latest_prices_by_offset where origin = 'YUL' and adults = 2 and children = 0 order by destination, offset_days, pick;`
- `select pick, price_total_cad, price_provider, carry_on_included, checked_bag_fee_cad, deep_link_url from latest_prices where origin = 'YQB' and destination = 'CDG' and depart_date = '2026-10-17' and adults = 1 and children = 1;`
- Price history for a cell: `select scrape_date, pick, price_total_cad from itineraries i join searches s on s.id = i.search_id ...` is **not** available to anon (searches is not readable); expose it later via another security-definer view if the site needs it.

Upsert contract for `db.py` (supabase-py ≥ 2.31): `table("searches").upsert(row, on_conflict="source_id,route_id,depart_date,return_date,adults,children,child_ages,cabin,scrape_date", returning="representation")` → read back `id`; then `table("itineraries").upsert(rows, on_conflict="search_id,pick", returning="minimal")`. `search_runs` is inserted at start and updated at the end (`status`, `finished_at`, counters).
  </schema>

  <adapter_contract>
The contract is generic (nine adapters register against it; only `google_flights` is enabled). Signatures follow the prompt; the only additions are an optional `variant` argument on `build_url` (Google's picks are URL states) and a `run_search` template method in the base class so the runner never knows source specifics.

```python
# flight_scraper/models.py  (pydantic v2)
from datetime import date, datetime
from enum import StrEnum
from pydantic import BaseModel, Field


class Pick(StrEnum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    BEST = "best"


class PriceStage(StrEnum):
    RESULTS = "results"          # results-row total (what Google shows in the list)
    FARE_SELECT = "fare_select"  # airline fare-family page (future sources)
    REVIEW = "review"            # airline/OTA review page (future sources)
    BOOKING = "booking"          # Google /travel/flights/booking per-provider total incl. taxes + fees


class PaxConfig(BaseModel):
    key: str                                  # '1a', '2a', '1a1c', '1a2c'
    adults: int = Field(ge=1, le=9)
    children: int = Field(ge=0, le=8)
    child_ages: list[int] = []                # [] for Google (no age); real ages for future sources
    priority: int = 1


class SearchQuery(BaseModel):
    source_id: str
    origin: str                               # IATA, upper-case
    destination: str
    depart_date: date
    return_date: date
    offset_days: int | None = None            # None for ad-hoc CLI searches
    pax: PaxConfig
    cabin: str = "economy"
    currency: str = "CAD"

    @property
    def cell_key(self) -> str:                # rotation identity, independent of concrete dates
        return f"{self.source_id}:{self.origin}-{self.destination}:+{self.offset_days}:{self.pax.key}"


class Leg(BaseModel):
    depart_local: datetime | None = None      # airport-local wall time; Google exposes no tz
    arrive_local: datetime | None = None
    duration_min: int | None = None
    stops: int | None = None
    airlines: list[str] = []
    flight_numbers: list[str] = []
    aria_label: str | None = None             # verbatim source sentence, for fixtures and debugging


class Provider(BaseModel):
    name: str
    total_cad: float | None                   # None when Google hides the price ("Visit site for price")
    is_airline: bool = False
    note: str | None = None


class Itinerary(BaseModel):
    outbound: Leg
    inbound: Leg | None = None                # filled after the return-leg click (booking-visit picks)
    airlines: list[str] = []
    flight_numbers: list[str] = []
    duration_min: int | None = None           # outbound + inbound when both known, else outbound
    stops: int | None = None                  # outbound
    return_stops: int | None = None
    fare_family: str | None = None
    price_results_cad: float | None = None    # results-row "round trip total" (all passengers)
    price_total_cad: float | None = None      # cheapest provider total from the booking page
    price_provider: str | None = None
    providers: list[Provider] = []
    price_stage: PriceStage = PriceStage.RESULTS
    currency_raw: str | None = None
    carry_on_included: bool | None = None
    carry_on_fee_cad: float | None = None
    checked_bag_fee_cad: float | None = None  # low end of a range
    luggage_source: str | None = None         # 'google_booking_page' | None
    price_insight: str | None = None
    deep_link_url: str | None = None          # booking URL when visited, else results URL
    results_url: str | None = None
    candidate_source: str = "best_load"       # 'best_load' | 'cheapest_load' | 'duration_load' | 'single_load'
    row_index: int = 0                        # position in its load, 0 = first row
    pick_rule: str = "native"                 # 'native' | 'local-v1'
    raw: dict = {}

    def identity(self) -> tuple:              # used to skip duplicate booking visits
        return (tuple(self.outbound.airlines), self.outbound.depart_local, self.outbound.arrive_local,
                self.inbound.depart_local if self.inbound else None,
                self.inbound.arrive_local if self.inbound else None)


class SearchResult(BaseModel):
    query: SearchQuery
    status: str = "pending"                   # ok | partial | blocked | error | skipped
    error: str | None = None
    blocked: bool = False
    page_url: str | None = None
    page_loads: int = 0
    picks: dict[Pick, Itinerary] = {}
    candidates: int = 0
```

```python
# flight_scraper/adapters/base.py
from abc import ABC, abstractmethod
from typing import ClassVar
from playwright.sync_api import Page
from ..models import Itinerary, Pick, SearchQuery, SearchResult
from .. import picks as pick_rules


class SourceDisabled(RuntimeError):
    """Raised by stub adapters; the runner records status='skipped' with the reason and moves on."""


class BlockedError(RuntimeError):
    """Raised when block markers are detected (403/429, /sorry/, 'unusual traffic', captcha iframe)."""


class BaseAdapter(ABC):
    source_id: ClassVar[str]
    kind: ClassVar[str]                        # 'meta' | 'ota' | 'airline'
    enabled: ClassVar[bool] = False
    disabled_reason: ClassVar[str | None] = None
    native_picks: ClassVar[frozenset[Pick]] = frozenset()   # picks the site ranks itself
    default_price_stage: ClassVar[str] = "results"

    def __init__(self, settings, budget, sleeper, artifacts):
        self.settings, self.budget, self.sleep, self.artifacts = settings, budget, sleeper, artifacts

    @abstractmethod
    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        """Pure function. variant=None → default/Best load; Pick.CHEAPEST / Pick.FASTEST → site-specific sort state."""

    @abstractmethod
    def search(self, page: Page, query: SearchQuery) -> list[Itinerary]:
        """Load the results view(s) and return ALL parsed candidates, each tagged with candidate_source + row_index.
        Must call self.budget.consume(1) per page load and raise BlockedError on block markers."""

    def select_picks(self, itineraries: list[Itinerary]) -> dict[Pick, Itinerary]:
        """Native tabs/sorts when the site has them (self.native_picks), local-v1 scoring otherwise."""
        return pick_rules.select_picks(itineraries, native=self.native_picks)

    def enrich_luggage(self, page: Page, itinerary: Itinerary) -> Itinerary:
        """Deepest reachable step without paying/logging in: final price, luggage, deep link. Default: no-op."""
        return itinerary

    def run_search(self, page: Page, query: SearchQuery) -> SearchResult:   # template method used by runner.py
        if not self.enabled:
            raise SourceDisabled(self.disabled_reason or "disabled")
        candidates = self.search(page, query)
        picks = self.select_picks(candidates)
        visited: dict[tuple, Itinerary] = {}
        for pick, it in picks.items():
            if self.settings.budget.booking_visits == "none" or (
                self.settings.budget.booking_visits == "best_only" and pick is not Pick.BEST):
                continue
            key = it.identity()
            picks[pick] = visited[key] if key in visited else visited.setdefault(key, self.enrich_luggage(page, it))
        return SearchResult(query=query, picks=picks, candidates=len(candidates), status="ok",
                            page_url=self.build_url(query), page_loads=self.budget.used_in_current_search)
```

```python
# flight_scraper/picks.py — pure functions, unit-tested

def select_picks(cands: list[Itinerary], native: frozenset[Pick]) -> dict[Pick, Itinerary]:
    out: dict[Pick, Itinerary] = {}
    if Pick.BEST in native:      # Google: first row of the default load = "Top departing flights" #1
        out[Pick.BEST] = next(c for c in cands if c.candidate_source == "best_load" and c.row_index == 0)
    if Pick.CHEAPEST in native:  # Google: min price over the Cheapest-tab load (OTA fares included); tie → shorter
        pool = [c for c in cands if c.candidate_source == "cheapest_load"] or cands
        out[Pick.CHEAPEST] = min(pool, key=lambda c: (c.price_results_cad, c.duration_min or 10**6))
    if Pick.FASTEST in native:   # Google: min total duration over the Duration-sort load; tie → cheaper
        pool = [c for c in cands if c.candidate_source == "duration_load"] or cands
        out[Pick.FASTEST] = min(pool, key=lambda c: (c.duration_min or 10**6, c.price_results_cad))
    for pick in Pick:            # anything the site cannot rank natively → local rule
        if pick not in out:
            out[pick] = local_v1(cands, pick)
            out[pick].pick_rule = "local-v1"
    return out


def local_v1(cands: list[Itinerary], pick: Pick) -> Itinerary:
    """Shared 'best' rule (research §best-definition) for sources without a native Best; also the
    fallback for cheapest/fastest. Computed on ONE candidate set; self-transfer / separate-ticket
    itineraries are excluded from BEST. Lowest score wins; ties → cheaper."""
    if pick is Pick.CHEAPEST:
        return min(cands, key=lambda c: (c.price_results_cad, c.duration_min or 10**6))
    if pick is Pick.FASTEST:
        return min(cands, key=lambda c: (c.duration_min or 10**6, c.price_results_cad))
    pool = [c for c in cands if not c.raw.get("self_transfer")] or cands
    min_price = min(c.price_results_cad for c in pool)
    min_dur = min(c.duration_min for c in pool if c.duration_min) or 1
    def score(c):
        stop_penalty = 1 + 0.5 * (c.stops or 0) + 0.25 * bool(c.raw.get("long_layover")) + 0.25 * bool(c.raw.get("airport_change"))
        return 0.50 * c.price_results_cad / min_price + 0.35 * (c.duration_min or min_dur) / min_dur + 0.15 * stop_penalty
    return min(pool, key=lambda c: (score(c), c.price_results_cad))
```

**Google Flights adapter behaviour (the one live implementation):**
- `build_url(query, variant)` → `https://www.google.com/travel/flights/search?tfs=<b64url protobuf>&hl=en-US&curr=CAD&gl=CA` + `&tfu=EgoIABAAGAAgAigB` (CHEAPEST) or `&tfu=EgYIBRAAGAA` (FASTEST). The `tfs` message is built by an in-repo encoder (`tfs.py`, ~60 lines: varint + length-delimited fields): field 3 = repeated leg {2: "YYYY-MM-DD", 13: {2: origin}, 14: {2: destination}}, field 8 = packed passengers (ADULT=1 per adult, CHILD=2 per child), field 9 = cabin (ECONOMY=1), field 19 = trip type (ROUND_TRIP=1). Golden test: YUL→CDG 2026-10-15 / 2026-10-22, 2 adults + 1 child must encode to `GhoSCjIwMjYtMTAtMTVqBRIDWVVMcgUSA0NERxoaEgoyMDI2LTEwLTIyagUSA0NER3IFEgNZVUxCAwEBAkgBmAEB` (decoded and verified while writing this plan). `faster-flights` is an optional dev dependency used only to cross-check the encoder in a test.
- `search(page, query)` → three loads in order: default (candidates tagged `best_load`), Cheapest tab (`cheapest_load`), Duration sort (`duration_load`). For each load: `goto(wait_until="domcontentloaded")`, `wait_for_selector("li.pIav2d", 45 s)`, wait for `text=/Other departing|Departing flights|more flights/` (20 s, soft), click the "more flights" button when present, then read the first `[aria-label]` of every `li.pIav2d` and parse with the results regex (price "From N Canadian dollars round trip total", "Nonstop|N stop(s) flight with A and B", "Leaves … at H:MM AM/PM on Weekday, Month D and arrives at … at …", "Total duration H hr M min", layovers). Rows that do not match are kept in `raw.unparsed` and counted; 0 parsed rows after the wait triggers one retry then `error='no_results_parsed'` + artifacts.
- `select_picks` → native for all three (`native_picks = {BEST, CHEAPEST, FASTEST}`).
- `enrich_luggage(page, it)` → the booking visit: navigate to the load the pick came from, click its `li.pIav2d` (row_index), wait for the returning list, choose the return row by pick rule (BEST → first row; CHEAPEST → min price; FASTEST → min duration; ties as above), click it, `wait_for_url(/\/travel\/flights\/booking/)`, wait 3–5 s, read `body.inner_text()`; parse providers (`Book with <name>\n(Airline\n)?CA$<total>`; "Price hidden … Visit site for price" → `total_cad=None`), passengers note ("Prices include required taxes + fees for N passengers" → assert N == adults + children, else `raw.pax_mismatch=true` and keep `price_stage='results'`), bag text (`1 free carry-on per passenger` → `carry_on_included=True`; `No carry-on` → `False`; `1st checked bag per passenger: CA$150–170` → `checked_bag_fee_cad=150`, `raw.checked_bag_fee_max_cad=170`, `raw.checked_bag_fee_raw`; "checked bag included"/"free checked bag" → `0`), price insight sentence, flight numbers if printed. Sets `price_total_cad = min(provider totals)`, `price_provider`, `price_stage='booking'`, `luggage_source='google_booking_page'` (only when at least one bag sentence parsed), `deep_link_url = page.url`, `inbound` leg from the return row's aria-label, `duration_min = outbound + inbound`. Budget: 2 loads per visit (return list + booking page); a visit is skipped when `identity()` matches an already-visited pick.
- Every page transition calls `browser.check_block(page)` (status 403/429 on the main response, URL contains `/sorry/`, body matches `unusual traffic|not a robot`, or `iframe[src*="recaptcha"]` present) → `BlockedError` → search `blocked=True`, artifacts saved, no captcha interaction ever.
  </adapter_contract>

  <phases>
    <!-- Prompt 003 executes these in order, one prompt each, and sets status="done" on completion. -->

    <phase number="1" name="Scaffold, config, schema, models and pure functions" status="done">
      <objective>Produce an installable package whose non-browser core is complete and unit-tested: watch-list loading and cell expansion, relative-date resolution, the Google `tfs` URL builder (golden-tested), pick selection, the rotation scheduler, the dry-run sink, a CLI that lists all nine sources, one adapter module per source (eight disabled stubs), and the paste-ready Supabase migration — with zero network or browser use.</objective>
      <tasks>
        <task priority="high">Create `pyproject.toml` (Python ≥ 3.12; deps: `playwright==1.62.*`, `supabase>=2.31`, `pydantic>=2.7`, `pyyaml`, `typer`, `python-dotenv`; dev: `pytest`, `ruff`, `pglast` (SQL syntax test), `faster-flights` (optional encoder cross-check); `[tool.pytest.ini_options] markers = ["live: hits real sites/DB, opt-in"]`, `addopts = "-m 'not live'"`; ruff line-length 110, target py312).</task>
        <task priority="high">Write `config/watchlist.yaml` verbatim from `<watchlist_seed>` and `flight_scraper/config.py`: `Settings` (env: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `FS_BROWSER_ENGINE=playwright|patchright`, `FS_HEADED=0|1`, `FS_MAX_PAGE_LOADS` override, `FS_LOG_LEVEL`), `WatchList` pydantic model with validation (IATA regex, offsets > 0, pax bounds, `routes: all` expansion to 12 pairs), `expand_cells(watchlist) -> list[Cell]` (route × offset × pax × source).</task>
        <task priority="high">Write `flight_scraper/dates.py`: `resolve_dates(run_date, offset_days, stay_nights, rule="next_saturday") -> (depart, return)`; `run_local_date()` in America/Toronto. Tests: run_date on a Saturday, Friday, Sunday; +30/+60/+90; return = depart + 7; year rollover.</task>
        <task priority="high">Write `flight_scraper/models.py` exactly as in `<adapter_contract>` (Pick, PriceStage, PaxConfig, SearchQuery, Leg, Provider, Itinerary, SearchResult).</task>
        <task priority="high">Write `flight_scraper/adapters/google_flights/tfs.py` (minimal protobuf encoder: varint, length-delimited, packed repeated) and `build_search_url(query, variant)` + `TFU = {"cheapest": "EgoIABAAGAAgAigB", "fastest": "EgYIBRAAGAA"}`. Golden test against `GhoSCjIwMjYtMTAtMTVqBRIDWVVMcgUSA0NERxoaEgoyMDI2LTEwLTIyagUSA0NER3IFEgNZVUxCAwEBAkgBmAEB` (YUL-CDG 2026-10-15/22, 2 adults + 1 child) plus a decode round-trip test; skip-if-missing cross-check against `fast_flights.create_query(...).params()["tfs"]`.</task>
        <task priority="high">Write `flight_scraper/adapters/base.py` (BaseAdapter, SourceDisabled, BlockedError, template `run_search`) and `flight_scraper/adapters/__init__.py` registry `REGISTRY: dict[str, type[BaseAdapter]]` ordered by priority. Create the Google adapter package skeleton (`adapters/google_flights/__init__.py`, `adapter.py` with `build_url` implemented and `search` raising `NotImplementedError("phase 2")`) and eight stubs `kayak.py, expedia.py, skyscanner.py, air_canada.py, air_transat.py, westjet.py, porter.py, flair.py` with `enabled=False`, `disabled_reason` copied from `<source_decisions>`, `search()` raising `SourceDisabled`; where research documented a URL format (kayak, skyscanner, expedia, air_canada) implement `build_url` as a pure function with a unit test so a future enablement starts from something tested.</task>
        <task priority="high">Write `flight_scraper/picks.py` (`select_picks`, `local_v1`) with tests: native Google picks from tagged candidates, tie-breaks, local-v1 ordering on a synthetic 5-itinerary set, self-transfer exclusion from BEST.</task>
        <task priority="high">Write `flight_scraper/scheduler.py`: `RotationState` protocol (`last_ok_at(cell_key)`, `mark(cell_key, ok: bool, at)`), `FileRotationState` (`out/rotation_state.json`), `plan_run(cells, state, budget, now, filters) -> list[SearchQuery]` = never-scraped first, then `priority × days_since_last_ok` descending, capped by `max_searches_per_run` and `floor(max_page_loads / est_page_loads_per_search)`; CLI filters (`--route`, `--pax`, `--offset`, `--source`) narrow the cell set before ranking. Tests: cold start, steady state over a simulated 60-day loop asserting every cell is scraped and 1a cells more often than 1a2c, filter behaviour.</task>
        <task priority="medium">Write `flight_scraper/db.py` with the `Sink` protocol (`start_run`, `write_search(result) -> search_id`, `finish_run`) and `DryRunSink` (accumulates and writes `out/<run_id>.json` with run header + searches + picks; also updates `FileRotationState`). `SupabaseSink` is a Phase-3 deliverable — leave a clearly named stub raising `NotImplementedError`.</task>
        <task priority="medium">Write `flight_scraper/runner.py` skeleton and `flight_scraper/cli.py` (typer): `sources` (table of 9: id, kind, enabled, reason), `watchlist` (resolved cells and concrete dates for today), `plan` (what the next run would scrape and its load estimate), `run [--dry-run] [--source] [--route YUL-CDG] [--pax 1a] [--offset 60] [--budget N] [--headed]`. In Phase 1 `run --dry-run` must complete end-to-end with each search recorded as `status='error', error='adapter not implemented (phase 2)'` — this proves the pipeline shape before any browser code exists.</task>
        <task priority="high">Write `supabase/migrations/0001_init.sql` verbatim from `<schema>` and a test that parses it with `pglast` (syntax only). Update `.env.example` (note `SUPABASE_SERVICE_KEY` is the `sb_secret_...` key) and `.gitignore` (add `logs/`, `profiles/`).</task>
        <task priority="low">README skeleton: purpose, layout, `uv venv && uv pip install -e .[dev]`, `playwright install chromium`, running tests, dry-run example. Full README lands in Phase 4.</task>
      </tasks>
      <deliverables>
        <deliverable>/home/jfontaine/Projects/flight-scraper/pyproject.toml</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/config/watchlist.yaml</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/__init__.py, config.py, dates.py, models.py, picks.py, scheduler.py, db.py, runner.py, cli.py</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/adapters/__init__.py, base.py, kayak.py, expedia.py, skyscanner.py, air_canada.py, air_transat.py, westjet.py, porter.py, flair.py</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/adapters/google_flights/__init__.py, tfs.py, adapter.py</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/supabase/migrations/0001_init.sql</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/tests/test_tfs.py, test_dates.py, test_config.py, test_picks.py, test_scheduler.py, test_stubs.py, test_cli.py, test_migration_sql.py</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/.env.example, .gitignore, README.md (skeleton)</deliverable>
      </deliverables>
      <dependencies>None. No Supabase credentials, no browser download required (document `playwright install chromium` only).</dependencies>
      <execution_notes>Everything in this phase is a pure function or a file writer — keep it that way (no Playwright import outside `browser.py`, which does not exist yet). Verify the golden `tfs` string byte-for-byte; if it differs, decode both with a tiny varint reader before changing field numbers (the decoded structure is: field 3 legs {2 date, 13 {2 origin}, 14 {2 destination}}, field 8 packed [1,1,2], field 9 = 1, field 19 = 1 — no entity_type is needed even though Google re-canonicalises the URL). `child_ages` must serialise as `[]`, never `null`, so the DB unique constraint holds. The rotation state file is the only mutable local state; write it atomically (tmp + rename). Do not add retries/sleeps here — they belong to the runner in Phase 2. Run `ruff check .` and `pytest -q` once at the end; `python -m flight_scraper.cli sources` must list all nine with reasons, `python -m flight_scraper.cli plan` must print ≤ 5 searches with a 40-load budget.</execution_notes>
    </phase>

    <phase number="2" name="Google Flights adapter end-to-end (dry-run JSON)" status="pending">
      <objective>Implement the live Google Flights flow — three results loads, native picks, booking-page visits with final price + luggage + deep link — behind the adapter contract, with block detection, artifacts, jittered pacing and a page-load budget; produce `out/<run_id>.json` from `run --dry-run --source google_flights --route YUL-CDG`, fixture-based parser tests from captured pages, and one opt-in live smoke test.</objective>
      <tasks>
        <task priority="high">Write `flight_scraper/browser.py`: `open_context(settings)` (Playwright Chromium headless by default; `launch_persistent_context(user_data_dir="profiles/google_flights", locale="en-CA", timezone_id="America/Toronto", viewport=1366×900)`; `FS_BROWSER_ENGINE=patchright` swaps the import, `FS_HEADED=1` sets headless=False); `page.route` to abort images/fonts/media (never scripts/XHR); `check_block(page, response)` per the contract; `save_artifacts(page, run_id, search_key, reason)` → `artifacts/<run_id>/<search_key>/{page.html, page.png, url.txt, reason.txt}`; `PageLoadBudget` (`consume(n)`, `remaining`, `used_in_current_search`, raises `BudgetExhausted`); `Sleeper` with uniform jitter from `budget.delays_s`.</task>
        <task priority="high">Write `adapters/google_flights/parse_results.py`: `parse_row_aria(text, query) -> Leg + price` using the research regex family (price, stops, carriers, "Leaves X at 5:00 PM on Thursday, October 15", "arrives at Y at 9:30 AM on Friday, October 16", "Total duration 11 hr 30 min", layover sentences → `raw.layovers`, "Self transfer"/"separate tickets" → `raw.self_transfer`, layover > 4 h or overnight → `raw.long_layover`, "airport change" → `raw.airport_change`); year inference from the query dates; `read_rows(page)` (wait `li.pIav2d` 45 s → soft-wait `text=/Other departing|Departing flights|more flights/` 20 s → click `get_by_role("button", name=/more flights/)` if present → read the first `[aria-label]` of each row). Unmatched rows go to `raw.unparsed` with a warning.</task>
        <task priority="high">Write `adapters/google_flights/parse_booking.py`: `parse_booking_text(body_text) -> BookingInfo` (providers with `is_airline`, hidden-price handling, passengers note + count, luggage sentences → `carry_on_included`, `checked_bag_fee_cad` low/high/raw, `price_insight`, flight numbers via `\b[A-Z0-9]{2}\s?\d{2,4}\b` restricted to the itinerary block if identifiable). Pure function over `inner_text`.</task>
        <task priority="high">Implement `adapters/google_flights/adapter.py`: `search()` (default → Cheapest → Duration loads, candidates tagged and indexed, `budget.consume(1)` per goto), `select_picks()` (native), `enrich_luggage()` (goto the pick's load URL, click row, wait for the returning list — detect by row aria-labels changing or `text=/Returning flights/` — choose return row by pick rule, click, `wait_for_url(/\/travel\/flights\/booking/)`, settle 3–5 s, parse, fill fields per the contract; `budget.consume(2)`), dedup via `identity()`, `check_block` on every transition.</task>
        <task priority="high">Complete `flight_scraper/runner.py`: for each planned query → `adapter.run_search` with `per_search_attempts` (retry only on timeout / `no_results_parsed`, never on `BlockedError`), sleeps between actions/loads/searches, block handling (mark `blocked=True`, artifacts, `block_pause_s`, abort run after `abort_after_consecutive_blocks`), budget guard before each search, error capture into `SearchResult.error` (exception class + message + first traceback line), sink writes, rotation marks, run summary log line (searches ok/error/blocked, loads used, elapsed).</task>
        <task priority="medium">Add `cli capture --route YUL-CDG --pax 1a --offset 60` that runs one search and saves sanitised fixtures: `tests/fixtures/google_flights/{best,cheapest,duration}_rows.json` (list of aria-labels), `booking_<pick>.txt` (body inner_text), `results_<load>.html`. Write fixture tests: ≥ 15 parsed rows for YUL-CDG best load, price/duration/stops/times asserted for row 0, booking parser yields providers + bag fields + passengers count, YQB-CDG thin-route fixture (2–4 rows) where cheapest == best triggers dedup.</task>
        <task priority="medium">Live smoke test `tests/live/test_google_live.py` (`@pytest.mark.live`): YUL-CDG 1a +60 → 3 picks, `best.price_total_cad > 0`, `best.deep_link_url` contains `/travel/flights/booking`, `luggage_source == 'google_booking_page'` or a logged reason, page loads ≤ 9.</task>
      </tasks>
      <deliverables>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/browser.py, runner.py (complete)</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/adapters/google_flights/adapter.py, parse_results.py, parse_booking.py</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/tests/fixtures/google_flights/* (captured pages), tests/test_google_parse_results.py, tests/test_google_parse_booking.py, tests/test_runner.py (fake adapter: budget, retries, block breaker), tests/live/test_google_live.py</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/out/&lt;run_id&gt;.json produced by `python -m flight_scraper.cli run --dry-run --source google_flights --route YUL-CDG --pax 1a --offset 60` (verify, do not commit)</deliverable>
      </deliverables>
      <dependencies>Phase 1. `playwright install chromium` on the WSL2 host. Internet access from the home IP (residential). No Supabase credentials.</dependencies>
      <execution_notes>Ground truth is the research's live-verification finding: rows stream in for 2–4 s, so never read immediately after the first row; headings vary by route ("Top departing options") and locale — never key on heading text, only on `li.pIav2d` + the first `[aria-label]`. Keep `hl=en-US&curr=CAD&gl=CA` pinned and assert "Canadian dollars" in every parsed aria-label (else `currency_raw` = what was seen and the row is excluded). The Duration-sort load renders a single "Departing flights" list; the Cheapest tab keeps top/other groups — both are handled by "expand then read everything". After a booking page, navigate with `goto(load_url)` rather than `go_back()` (history state is unreliable and Google re-canonicalises `tfs`). Never click "Continue"/"Visit site" on the booking page. If `consent.google.com` or `/sorry/` appears, save artifacts and treat as a block — do not automate consent or captcha. Budget accounting must be exact: 1 per goto, 1 per outbound click, 1 per return click; a search must not start unless `remaining ≥ est_page_loads_per_search`. Test the runner with a fake adapter (no browser) for retries, breaker and budget. Capture fixtures from a real run so parser tests reflect today's markup; never edit fixtures by hand. Expect YQB-CDG to have 2–4 rows — that is normal, not a parse failure. Run pytest (live skipped) and one real `--dry-run` before marking done.</execution_notes>
    </phase>

    <phase number="3" name="Supabase ingestion, rotation state and idempotency" status="pending">
      <objective>Persist runs, searches and itineraries into Supabase with idempotent upserts, read rotation state from the database, keep the JSON dry-run path as a fallback, and document how the website queries `latest_prices`.</objective>
      <tasks>
        <task priority="high">Implement `SupabaseSink` in `db.py`: `create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)`; `start_run` inserts `search_runs` (git_sha via `git rev-parse --short HEAD`, host); `write_search` upserts `searches` on the natural key with `returning="representation"` → id, then upserts ≤ 500 `itineraries` rows on `(search_id, pick)`; `finish_run` updates status/counters/finished_at. Serialise: dates ISO, `child_ages` list, numerics as floats, `raw` dict, `scrape_date` from `dates.run_local_date()`.</task>
        <task priority="high">Implement `SupabaseRotationState` reading `cell_last_scraped` (filter by source, map to cell keys via route/offset/adults/children) and skipping cells with `blocked_recently` for one run; sink/state selection in `runner.py`: credentials present and not `--dry-run` → Supabase (still also writes `out/<run_id>.json`); otherwise dry-run with a clear warning.</task>
        <task priority="high">Idempotency tests without network: `FakeSupabase` recording `upsert(table, rows, on_conflict)` calls; assert the two `on_conflict` strings verbatim, that a second write of the same search on the same day reuses the search id and produces 3 itinerary upserts (not inserts), and that DB errors are logged and do not abort the run (the JSON file is still written).</task>
        <task priority="medium">`cli db-check`: connects, selects counts from `sources`/`routes`/`latest_prices`, prints the last 3 runs; exit 1 on failure. Live DB test (`-m live`, requires `.env`): write one search twice, assert one `searches` row and three `itineraries` rows; `select * from latest_prices` returns them.</task>
        <task priority="medium">README: "Apply the migration" (paste `0001_init.sql` in the SQL editor), keys (`sb_secret_` server / `sb_publishable_` website), the three website query examples from `<schema>`, and what `price_stage`, `pick_rule`, `luggage_source`, `checked_bag_fee_cad` (low end of range; range in `raw`) mean.</task>
      </tasks>
      <deliverables>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/db.py (SupabaseSink, SupabaseRotationState), runner.py (sink selection)</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/tests/test_db_sink.py, tests/test_rotation_state.py, tests/live/test_supabase_live.py</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/README.md (schema + website section)</deliverable>
      </deliverables>
      <dependencies>Phases 1–2. For live verification only: `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (`sb_secret_…`) in `.env` and the migration applied — not yet provided; everything else is testable offline.</dependencies>
      <execution_notes>PostgREST needs the exact UNIQUE constraint columns in `on_conflict`, including `child_ages` and `scrape_date`; a 42P10 error means the migration was not applied or the string differs. Use `returning="representation"` only on `searches` (need the id); `returning="minimal"` on itineraries. Keep `scrape_date` explicit (the DB default is UTC-based). Never swallow DB exceptions silently — log, set `run.status='partial'`, keep going, and always write the JSON file so a failed night can be replayed with a future `cli replay out/<run_id>.json` (not required in v1 but keep the JSON complete enough). Do not store secrets anywhere but `.env`; `db-check` must print the project ref only, never the key.</execution_notes>
    </phase>

    <phase number="4" name="Scheduler, CLI polish, operations and README" status="pending">
      <objective>Make the daily run unattended and observable on WSL2: systemd timer with jitter, wrapper script with exit codes, rotating logs, a health command, artifact pruning, and a complete README covering setup, scheduling, debugging, the schema and how to add routes or enable a source.</objective>
      <tasks>
        <task priority="high">`scripts/run_daily.sh`: `cd` to the project, activate `.venv`, `exec python -m flight_scraper.cli run` (wrapped in `xvfb-run -a` only when `FS_HEADED=1`); exit codes 0 = ok/partial, 2 = blocked, 3 = failed or zero itineraries across ≥ 3 searches.</task>
        <task priority="high">`scripts/flight-scraper.service` (`Type=oneshot`, `User=jfontaine`, `WorkingDirectory`, `EnvironmentFile=/home/jfontaine/Projects/flight-scraper/.env`, `Environment=TZ=America/Toronto`, `TimeoutStartSec=45min`, `ExecStart=…/scripts/run_daily.sh`) and `scripts/flight-scraper.timer` (`OnCalendar=*-*-* 06:30:00`, `RandomizedDelaySec=45m`, `Persistent=true`, `WantedBy=timers.target`); `scripts/install_systemd.sh` (copy units, `daemon-reload`, `enable --now`, print WSL prerequisites: `[boot] systemd=true` in `/etc/wsl.conf`, Windows Task Scheduler keep-alive `wsl.exe -d <distro> -- sleep infinity`, `hwclock -s` note for clock drift after sleep).</task>
        <task priority="high">`flight_scraper/logging_setup.py`: console + `RotatingFileHandler("logs/flight-scraper.log", maxBytes=5 MB, backupCount=5)`, run_id in every record; journald gets stdout. `cli health`: last run status/age, cells with `last_ok_at` older than 45 days, itineraries written in the last run; exit 1 when unhealthy (usable from a future notifier).</task>
        <task priority="medium">`cli prune-artifacts --days 14` and automatic pruning at the end of each run; `cli plan --explain` shows each selected cell's score.</task>
        <task priority="medium">README (complete): install (uv/pip, `playwright install chromium`, optional `patchright install chromium` + `apt install xvfb`), configuration (env vars, watch-list fields, budget levers A–D with the refresh-cycle math), running (`run`, `--dry-run`, filters, `capture`, `plan`, `health`, `db-check`), scheduling on WSL2, debugging (artifacts, fixtures, log), schema and website queries, adding a route/destination, enabling a source (what the stub needs), ethics/politeness statement (robots.txt awareness, ≤ 40 loads/day, no captcha solving).</task>
        <task priority="low">Test `run_daily.sh` once manually (`bash scripts/run_daily.sh` with `--dry-run` via `FS_DRY_RUN=1` passthrough) and `systemctl list-timers` shows the timer after install.</task>
      </tasks>
      <deliverables>
        <deliverable>/home/jfontaine/Projects/flight-scraper/scripts/run_daily.sh, flight-scraper.service, flight-scraper.timer, install_systemd.sh</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/logging_setup.py, cli.py (health, prune-artifacts, plan --explain)</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/README.md (complete)</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/tests/test_cli_health.py</deliverable>
      </deliverables>
      <dependencies>Phases 1–3. systemd enabled in WSL2 (user action). Installing units needs sudo — provide the script, do not run it unattended.</dependencies>
      <execution_notes>systemd `OnCalendar` uses the machine's local time zone; set `TZ` explicitly in the unit and document it. Do not run the service as root (browser profile ownership). `Persistent=true` makes a missed 06:30 run fire when WSL wakes — combined with `RandomizedDelaySec` this is the intended jitter; do not add a second sleep in the script. The log rotation is in-process (no logrotate dependency). `health` must not hit Google — it reads Supabase or `out/`. Keep the README's website section in sync with the view columns.</execution_notes>
    </phase>

    <phase number="5" name="Hardening and extension (optional)" status="pending">
      <objective>Reduce breakage risk and prepare the next source without changing v1 behaviour by default: RPC JSON cross-checks, the patchright engine path, the passenger-derived booking-load experiment, a headed probe command for WestJet/Air Canada, and a selector-drift alarm.</objective>
      <tasks>
        <task priority="medium">RPC interception: `page.on("response")` capture of `GetShoppingResults` / `GetBookingResults` (strip the `)]}'` prefix, JSON-decode) behind `--capture-rpc`; save to artifacts and log a discrepancy warning when the RPC row count or the min price differs from the DOM parse. DOM stays the source of truth; RPC parsing is not promoted in this phase.</task>
        <task priority="medium">Verify the `FS_BROWSER_ENGINE=patchright` path end-to-end under `xvfb-run` (channel `chrome` if installed, persistent profile, no custom UA/headers per the patchright README) and document when to switch (first `/sorry/` or 429 from Google).</task>
        <task priority="low">Experiment (lever D): decode a pick's booking `tfs`, replace the passengers field for `2a`/`1a1c`/`1a2c`, load the booking page, and compare totals with a full search of the same cell; report in the phase summary whether Google accepts re-encoded booking links. Keep behind `--experimental-pax-derive`; only make it the default after the user reviews the comparison.</task>
        <task priority="low">`cli probe <source>`: opens a headed browser on the source's entry page (WestJet `/en-ca/flights`, Air Canada deep link), waits for the user to drive one search manually, records the final URL, request URLs matching `/graphql|/shop|/api/`, and a screenshot into `artifacts/probe/<source>/` — no automated searching; a written playbook `docs/enabling-a-source.md` explains what the stub must implement (`build_url`, `search`, `enrich_luggage` for fare-family + review page, `price_stage` values) and the ToS/robots posture from research.</task>
        <task priority="low">Selector-drift alarm: `health` fails when the last run parsed 0 rows in ≥ 3 searches; optional carry-on fee experiment via the "Add carry-on bag" filter diff (research google-flights finding §5a).</task>
      </tasks>
      <deliverables>
        <deliverable>/home/jfontaine/Projects/flight-scraper/flight_scraper/adapters/google_flights/rpc.py, browser.py (patchright path verified), cli.py (probe, --capture-rpc, --experimental-pax-derive)</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/docs/enabling-a-source.md</deliverable>
        <deliverable>/home/jfontaine/Projects/flight-scraper/tests/test_rpc_parse.py (fixture from a captured RPC body), tests/test_tfs_rewrite.py</deliverable>
      </deliverables>
      <dependencies>Phases 1–4 in production for at least a few runs (to have artifacts and a baseline). User decisions on levers A–D and on enabling WestJet/Air Canada.</dependencies>
      <execution_notes>Nothing here may change default behaviour or add page loads to the nightly run without an explicit flag. The probe command is manual-only by design (a human drives the site) — do not turn it into a scraper. If the RPC structure is parsed, reuse faster-flights' documented index map (top/other groups; amenity flag [9] = checked bag) but treat it as fragile. Keep the 40-load budget unless the user changed it in `watchlist.yaml`.</execution_notes>
    </phase>
  </phases>

  <metadata>
    <confidence level="medium-high">High for the Google Flights flow, URL builder (golden string decoded and verified during planning), schema and Supabase mechanics — all grounded in the research's live-verified findings and official docs. Medium for stability-dependent parts (li.pIav2d, aria-label phrasing, tfu constants, bag-text coverage on carriers other than the Transat/Porter sample), for the rotation/refresh math (assumes 7–9 loads per search and no throttling at 40 loads/day), and for the systemd-on-WSL2 keep-alive recipe (blog-sourced). Low for anything about the eight disabled sources beyond "keep them disabled".</confidence>
    <dependencies>
      - Python ≥ 3.12, playwright 1.62.x + `playwright install chromium`, supabase-py ≥ 2.31, pydantic v2, pyyaml, typer, python-dotenv; dev: pytest, ruff, pglast; optional: faster-flights 3.8.0 (encoder cross-check only), patchright 1.62.x + xvfb (Phase 5 / insurance).
      - Supabase project on Postgres 15+ with new-style keys: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` = `sb_secret_…` (server), `sb_publishable_…` for the website — NOT YET PROVIDED (blocks only the live parts of Phase 3).
      - Home WSL2 box with residential IP; systemd enabled (`[boot] systemd=true`) and a Windows Task Scheduler keep-alive so the 06:30 timer fires; sudo once to install units.
      - Internet access to google.com from the home IP; no proxies, no captcha services, no paid APIs.
    </dependencies>
    <open_questions>
      - Which page-load lever(s) to pull: at 40 loads/day and 3 booking visits per search, 1-adult cells refresh every ~17 days and child configs every ~50 days. Options A (budget 120), B (booking visits best_only), C (drop +90 or 1a2c), D (pax-derived booking loads, Phase 5 experiment).
      - Booking-page bag text coverage: observed on one Transat/Porter itinerary; wording for AC Basic ("No carry-on"?), WestJet UltraBasic and OTA-priced options is unknown until the first runs — parser must tolerate absence (NULL + luggage_source NULL).
      - Are flight numbers printed on the booking page? If not, `flight_numbers` stays empty in v1 (they may require expanding the row detail panel — an extra in-page action, not a page load).
      - Return-leg selection rule (BEST → first return row; CHEAPEST → min price; FASTEST → min duration) is a plan decision, not a Google-native "best return" — acceptable?
      - Stability of `li.pIav2d`, the aria-label sentence format and the `tfu` constants across Google front-end builds (health check + fixtures mitigate; RPC interception is the fallback path).
      - Google 429 threshold from this IP is unknown (30 loads/15 min were fine); the breaker aborts after 2 consecutive blocks — is one aborted night acceptable, or should blocks page/notify the user?
      - Does the results-row "round trip total" always equal the booking-page airline total (one sample observed equal)? `price_results_cad` is stored to measure this.
      - Consent page (`consent.google.com`) never appeared with `gl=CA`; if it does, v1 treats it as a block — should a single "Reject all" click be allowed instead?
      - Should anon also be allowed to read price history (a `searches`-joined view)? Not in v1 per the RLS requirement.
    </open_questions>
    <assumptions>
      - Google Flights is the ONLY live adapter in v1; the other eight are disabled stubs with research reasons (user decision; research: all blocked, no deep link, or ToS/robots forbid).
      - Final price = Google booking-page total incl. taxes/fees for all passengers, `price_stage='booking'`; the "Continue" handoff is never followed; per-provider offers are stored in `raw.booking.providers` and the cheapest provider becomes `price_total_cad` / `price_provider` (user decision; research assumption that the booking total is a faithful proxy for checkout).
      - Luggage comes only from the booking-page text; `checked_bag_fee_cad` stores the low end of a range with the raw string and high end in `raw`; `carry_on_fee_cad` is NULL in v1 (Google shows no carry-on fee); `luggage_source='google_booking_page'` only when a bag sentence was parsed.
      - Picks: Best = first row of the default load; Cheapest and Fastest from dedicated `tfu` loads (user decision) — so one search = 3 results loads + up to 3 booking visits (2 loads each) = 9 loads max, with dedup when picks coincide.
      - Passenger matrix = 1a, 2a, 1a1c, 1a2c; no infants; Google has no child age → `child_ages = []` (NOT NULL empty array so the unique key works); the research's default age 8 is irrelevant for Google and only documented for future sources.
      - Volume: ≤ 40 page loads per run, once daily at 06:30 ± 45 min, single persistent browser context, residential IP, systemd timer (user decision). Rotation = weighted oldest-first with priorities 3/2/1/1; refresh math assumes ~5 searches/run.
      - Departure dates snap to the next Saturday on/after run_date + offset, 7-night Saturday-to-Saturday stay (plan decision so consecutive runs of a cell share concrete dates).
      - v1 extraction = DOM aria-label parsing with `hl=en-US&curr=CAD&gl=CA` pinned; RPC JSON interception is Phase-5 hardening only (user decision; research recommendation).
      - Browser: Playwright headless Chromium (live-verified); patchright + headed xvfb kept as a config switch, not the default (research: medium confidence on detection claims).
      - The `tfs` protobuf is encoded in-repo (fields 3/8/9/19 as decoded from the research golden string) instead of depending on faster-flights at runtime; the library is only a test cross-check.
      - Supabase keys: `sb_secret_` server-side via `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`; website uses `sb_publishable_` + RLS; owner-privilege views (`security_invoker = false`) expose joined names to anon without policies on the joined tables; Postgres ≥ 15.
      - Timestamps: `outbound_*_local` / `return_*_local` are airport-local wall times (no tz on Google); `scraped_at` is UTC; `scrape_date` is the America/Toronto run date.
      - Disabled-source enable order (WestJet → Air Canada → Kayak → Transat → Skyscanner → Porter → Flair → Expedia) is a plan judgement from research feasibility colours and anti-bot vendors, not a commitment.
      - A block is a data point: searches are marked `blocked=true`, artifacts saved, and the run aborts after two consecutive blocks; no captcha solving or consent automation ever.
    </assumptions>
  </metadata>
</plan>
