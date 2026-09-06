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
