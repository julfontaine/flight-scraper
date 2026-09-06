# Enabling a second source

v1 scrapes Google Flights only. The other eight adapters are stubs whose `disabled_reason` (also in the
`sources` table) summarises the research finding. Recommended order from the research: **WestJet** (weakest
visible anti-bot, no confirmed deep link), then **Air Canada** (deep link confirmed, Akamai + ToS + dummy
passenger data on the review step), then Kayak, Air Transat, Skyscanner, Porter, Flair, Expedia.

## Step 0 — decide whether you may

Several sites forbid automated access in their terms (Kayak §4, Air Canada, Air Transat, Porter, Flair,
Expedia) and/or in robots.txt. The stub's reason quotes the research; enabling is your call, and a block
must always stay a data point (`blocked=true`), never something to defeat.

## Step 1 — record the site by hand: `cli probe <source>`

```bash
python -m flight_scraper.cli probe westjet        # opens a HEADED browser on the entry page
```

Drive one search manually (origin, dates, passengers, choose a fare, reach the review/summary page).
When you close the window the probe writes `artifacts/probe/<source>/` with `final_url.txt`, `requests.txt`
(request URLs matching `/graphql|/shop|/api/`), and a screenshot. Nothing is automated: the probe never
types or clicks for you.

## Step 2 — implement the adapter

In `flight_scraper/adapters/<source>.py` (subclass `BaseAdapter`, set `enabled = True`):

| method | what it must do |
|---|---|
| `build_url(query, variant)` | pure function → results deep link (kayak, skyscanner, expedia, air_canada already have tested builders) |
| `search(page, query)` | load the results, `self.budget.consume(1)` per page load, `check_block` after every navigation (raise `BlockedError`), return **all** candidates as `Itinerary` with `price_results_cad`, `duration_min`, `stops`, `airlines`, `candidate_source` (`single_load` when the site has one list), `row_index`, `results_url`; set `native_picks` only for sorts the site ranks itself (Kayak: Best/Cheapest/Quickest tabs) |
| `enrich_luggage(page, query, itinerary, pick)` | airlines: fare-family page → `fare_family`, `carry_on_included`, `checked_bag_fee_cad`, `luggage_source='<source>_fare_select'`, `price_stage='fare_select'`; then the review page total → `price_total_cad`, `price_stage='review'`. OTAs: keep `price_stage='results'`, do **not** follow the handoff to the airline. Always `self.budget.consume(1)` per step and set `deep_link_url` |

Picks without a native sort fall back to `picks.local_v1` (price/duration/stops score; self-transfer
excluded from Best) and are stored with `pick_rule='local-v1'`.

## Step 3 — fixtures and tests

Capture the pages you parse into `tests/fixtures/<source>/` (sanitised: no cookies, no personal data) and
write parser tests against them; add a `-m live` smoke test. Update `budget.est_page_loads_per_search` if
the flow is longer than 9 loads, and add the source to `sources:` in `config/watchlist.yaml`.

## Step 4 — watch the first nights

`cli health` and `artifacts/` will show blocks. Two consecutive blocks abort the run; if the source blocks
consistently, disable it again — the schema keeps whatever it collected.
