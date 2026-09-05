<research>
  <summary>
Research date: 2026-09-04. SCOPE (re-focused mid-research at the user's request): Google Flights ("Google Vols") only. The other eight sources were investigated before the re-scope and are kept below as a reference appendix (rows in the source matrix + findings), but recommendations, code and the summary target Google Flights.

Headline (live-verified from this WSL2 host, no proxies, no stealth): Google Flights is fully workable for YQB/YUL round trips with children via a plain headless Playwright/Chromium session — one URL built from the protobuf `tfs` parameter loads 18–26 outbound itineraries in CAD, split natively into "Top departing flights" (= Best) and "Other departing flights"; the Cheapest tab and the sort menu (Price / Duration / …) are URL states in a companion `tfu` parameter (Cheapest = `tfu=EgoIABAAGAAgAigB`, Duration = `tfu=EgYIBRAAGAA`); clicking an outbound then a return reaches `/travel/flights/booking?tfs=…`, which lists per-provider totals "including required taxes + fees for N passengers" (airline first, then OTAs) AND per-itinerary luggage text ("1 free carry-on per passenger", "1st checked bag per passenger: CA$150–170"). Eleven back-to-back page loads and ~20 HTTP fetches drew no 429/captcha. All data also arrives as interceptable JSON RPCs (`GetShoppingResults`, `GetBookingResults`).

Library status: `fast-flights` 3.1.0 (2026-08-18) installs broken (missing `typing_extensions`) and, once patched, returns only ONE itinerary — Google now server-renders a single "lure" itinerary and loads the rest via RPC, so HTML-only scrapers are effectively dead for real use. The fork `faster-flights` 3.8.0 (2026-07-09) adds an `rpc-first` mode that returned 9 itineraries with Google's own top/other grouping in ~0.5 s for adult-only searches, but it falls back to the single SSR result whenever a child is in the passenger mix, its round-trip second step returns the outbound list again (open issue #3), and it relies on a hard-coded March-2026 build label (`used_default_rpc_params=True`) with an open issue (#4, 2026-07-30) about Google now requiring a live bootstrap token + BotGuard signature. Verdict: use Playwright (headless Chromium is enough today; patchright + persistent profile as insurance) driving the `tfs` URL and capturing the RPC responses / DOM; keep `faster-flights` only for its `tfs`/`tfu` builders and as an adult-only fast path.

Constraints to carry into the plan: Google's child passenger has no age (CHILD = 2–11, no age param); infants change the result set; robots.txt disallows /travel/flights/search and Google's ToS ties automated access to robots.txt — keep volume low and human-paced; headings vary by locale and even by route ("Top departing options"), so use ARIA/aria-label based extraction, not text.
  </summary>

  <source_matrix>
    <!-- feasibility: green = build in v1, yellow = feasible with caveats, red = defer/skip -->
    <row source="Google Flights (PRIMARY — in scope)" feasibility="green (live-verified 2026-09-04)" deep_link="yes: /travel/flights/search?tfs=&lt;protobuf&gt;&amp;hl=en-US&amp;curr=CAD&amp;gl=CA — passengers as ADULT/CHILD/INFANT enums (no child age); example YUL-CDG 2A+1C works" native_best_cheapest_fastest="yes: Best = 'Top departing flights' group in default load; Cheapest tab = tfu=EgoIABAAGAAgAigB; Fastest = sort menu 'Duration' = tfu=EgYIBRAAGAA (one load each, or one load + local sort)" checkout_total="partial-but-sufficient: /travel/flights/booking page lists per-provider totals incl. taxes+fees for all passengers (airline + OTAs), no login; actual payment happens on the airline/OTA" carry_on_info="yes: booking page text '1 free carry-on per passenger' / 'No carry-on' per itinerary; results filter 'Bags' offers carry-on count only on this route" checked_bag_fee="yes: booking page text '1st checked bag per passenger: CA$150–170' (range per itinerary); checked-bag filter absent for YUL-CDG" protection="Google WAF + rate limiting only; no Akamai/PX/DataDome/Cloudflare; headless Chromium not challenged in 11 consecutive loads from residential IP; robots.txt disallows the search path" approach="Playwright headless Chromium: build tfs URL (faster-flights/fast-flights builders), load Best, read li.pIav2d aria-labels or intercept GetShoppingResults; switch tfu for Cheapest/Duration; click outbound+return, read booking page totals + bag text (or GetBookingResults)"/>
    <row source="Kayak (ca.kayak.com)" feasibility="yellow" deep_link="yes (/flights/YUL-CDG/2026-10-15/2026-10-22/2adults/children-8?sort=bestflight_a) — verified 200 + title 'YUL to CDG, 15/10 – 22/10'" native_best_cheapest_fastest="yes (sort=bestflight_a|price_a|duration_a)" checkout_total="no (metasearch handoff 'View Deal'; 'Book on KAYAK' only for some airlines incl. Air Canada)" carry_on_info="yes (Fee Assistant panel; re-prices results)" checked_bag_fee="yes (Fee Assistant estimate)" protection="PerimeterX/HUMAN 'Press &amp; Hold' reported (Zenrows/Scrapfly 2026); Scraperly 2026 says Akamai; plain curl probe got 200 shell with no _abck/_px cookies; robots.txt disallows /flights/, ToS forbids scraping" approach="XHR capture of /i/api/search/dynamic/flights/poll via Playwright page.on('response'); DOM fallback; very low volume"/>
    <row source="Expedia (expedia.ca)" feasibility="red" deep_link="yes (official: /go/flight/search/Roundtrip/{d1}/{d2}?FromAirport=YUL&amp;ToAirport=CDG&amp;NumAdult=2&amp;NumChild=1&amp;Child1Age=8&amp;Class=3)" native_best_cheapest_fastest="partial (UI sort: price/duration/times; 'Recommended' default; URL sort param unverified)" checkout_total="partial (OTA; guest checkout exists; review page shows total; 5+ JS steps; not verified)" carry_on_info="partial (fare-selection step lists inclusions; bag-fee link)" checked_bag_fee="partial" protection="Akamai Bot Manager CONFIRMED (_abck, bm_sz, x-akamai-reference-id); probe returned HTTP 429 immediately; robots.txt disallows /Flights-Search and /Checkout; ToS forbids scraping" approach="skip in v1; revisit only after headed patchright probe from home IP succeeds"/>
    <row source="Skyscanner (skyscanner.ca)" feasibility="yellow-red" deep_link="yes (official referral params: /transport/flights/yul/cdg/261015/261022/?adultsv2=2&amp;childrenv2=8&amp;cabinclass=economy&amp;rtn=1) — verified 200, market CA / currency CAD / locale en-CA in page JSON" native_best_cheapest_fastest="yes (Best default; sortby=cheapest|fastest)" checkout_total="no (handoff via /transport_deeplink; occasional 'Book on Skyscanner')" carry_on_info="no (not verified on results; fare details are on partner site)" checked_bag_fee="no" protection="PerimeterX CONFIRMED (_pxhd cookie set on probe); Feb-2026 GitHub issue: 403 'Access banned. CAPTCHA challenge' persists across IPs; robots.txt disallows /transport/*; ToS not retrievable (page JS-only)" approach="XHR capture of /g/radar/api/v2/web-unified-search/ via Playwright; expect blocks; keep as optional source"/>
    <row source="Air Canada" feasibility="yellow" deep_link="yes (https://www.aircanada.com/booking/ca/en/aco/availability/rt/outbound?org0=YUL&amp;dest0=CDG&amp;departureDate0=2026-10-15&amp;org1=CDG&amp;dest1=YUL&amp;departureDate1=2026-10-22&amp;ADT=2&amp;YTH=0&amp;CHD=1&amp;INF=0&amp;INS=0&amp;lang=en-CA&amp;tripType=R&amp;marketCode=INT) — 200 app shell; param names confirmed in app bundle" native_best_cheapest_fastest="no (no 'best'; UI sorts exist, unverified)" checkout_total="partial (app routes availability → fare → passengers → seats → review-trip → payment; guest booking allowed; review-trip shows total incl. taxes; not verified end-to-end)" carry_on_info="yes (fare-family picker Basic/Standard/Flex/Comfort/Latitude; Basic = personal item only on NA routes since 2025-01-03)" checked_bag_fee="partial (Basic/Standard 1st bag CA$45 NA from 2026-04-13 per aggregators; in-flow via extras/bag calculator)" protection="Akamai Bot Manager CONFIRMED (_abck, bm_sz, bm_so, akamai-grn header, sensor script); no robots.txt (404); ToS explicitly forbids automated access" approach="patchright headed (xvfb) + response interception of GraphQL LFS endpoint (ak-lfs-appsync-api-ecom.digital.aircanada.com/graphql); DOM fallback"/>
    <row source="Air Transat" feasibility="yellow" deep_link="not found (www is Kentico CMS; booking engine = Softvoyage/TSOnline at bookings.airtransat.com + reservations.transat.com; search-form params not exposed in HTML)" native_best_cheapest_fastest="no" checkout_total="unclear (not verified)" carry_on_info="yes (fare picker: Eco Budget = personal item only on Sun/US/Canada since Feb 2025, carry-on included to Europe; Eco Standard adds carry-on everywhere + 1 checked bag on Europe)" checked_bag_fee="partial (fees 'shown during booking'; aggregator: CA$55–67.50 1st bag within 24h, CA$100 at airport, 2026-06-01)" protection="Imperva/Incapsula CONFIRMED (x-cdn: Imperva, incap_ses/visid_incap cookies); robots.txt only blocks legacy */FlightSearch/; ToS forbids scraping/screen-scraping" approach="Playwright form-drive from /en-CA/book/book-a-flight; capture XHR to api.transat.com / bookings.airtransat.com; medium priority"/>
    <row source="WestJet" feasibility="yellow" deep_link="unclear (booking app https://www.westjet.com/shop/summary is a Vue SPA; state keys origin/destination/departureDate/returnDate/adults/children/infants/tripType/cabin found in bundle but query-string format unconfirmed)" native_best_cheapest_fastest="no (unverified UI sorts)" checkout_total="unclear (guest booking exists; review step before payment; not verified)" carry_on_info="yes (official fare table: UltraBasic = personal item only in NA, carry-on to/from Europe/Asia; Econo+ include carry-on)" checked_bag_fee="partial (official fees page is JS; aggregators: UltraBasic CA$55–65, Econo CA$45–53 prepaid 1st bag, from 2026-04-23)" protection="none detected on /shop shell (Azure-hosted, only tlcookie); marketing pages load reCAPTCHA; robots.txt disallows /*/search; ToS page at /en-ca/legal/terms-of-use returned 404" approach="Playwright form-drive on /en-ca/flights → /shop/*; capture XHR JSON; medium-high priority (weakest visible anti-bot)"/>
    <row source="Porter" feasibility="yellow-red" deep_link="not found (booking.flyporter.com timed out from probe host; www.flyporter.com serves Cloudflare managed challenge 'Just a moment...')" native_best_cheapest_fastest="no" checkout_total="unclear" carry_on_info="yes (fare picker: Basic = personal item only on Canada/US, carry-on included to Europe/Africa; Standard+ include carry-on)" checked_bag_fee="partial (aggregators: from CA$40–52 prepaid, CA$50–69 airport, from 2026-05-07; Flexible/Freedom include 1 bag)" protection="Cloudflare (JS challenge on www); robots.txt disallows /Flight/Tickets/Book-Your-Travel, /tickets/select, /fares; ClaudeBot/GPTBot disallowed; ToS forbids robots/spiders" approach="defer; probe booking.flyporter.com with headed browser from home IP first"/>
    <row source="Flair" feasibility="yellow-red" deep_link="not found (www.flyflair.com returns Cloudflare 403 'Attention Required!' block page to curl; /booking path exists but blocked; booking.flyflair.com does not resolve)" native_best_cheapest_fastest="no" checkout_total="unclear" carry_on_info="yes (a-la-carte: carry-on CA$49–109 at booking; bundles Basic (personal item only) / Lite / Plus / Pro-or-MAX include carry-on from Lite up)" checked_bag_fee="partial (aggregator: CA$69–119 at booking, CA$109–164 at gate; Plus bundle includes 1 checked bag)" protection="Cloudflare CONFIRMED (cf-ray, __cf_bm, 403 block for non-browser TLS); robots.txt Allow: / for *, AI-training bots disallowed; ToS forbids screen-scraping/crawling" approach="defer; headed browser probe first; if accessible, form-drive"/>
  </source_matrix>

  <findings>

    <finding category="robots-txt">
      <title>robots.txt posture for all 9 domains (fetched 2026-09-04)</title>
      <detail>
- google.com: Disallow /travel/flights/search, /travel/flights/s/, /travel/flights/booking, /travel/search (User-agent: *).
- kayak.com: User-agent * → Disallow /flights/, /hotels/, /s/, /book. Allow carve-outs only for Facebot, Twitterbot, AdsBot-Google, ChatGPT-User.
- expedia.ca: User-agent * → disallow /Flights-Search, /Flight-SearchResults, /Flights-BagFees, /FlightCheckout, /Checkout. AI search bots (OAI-SearchBot, ChatGPT-User, PerplexityBot, Claude-User, Claude-SearchBot) "allow: /" except auth.
- skyscanner.ca: User-agent * → Disallow /transport/*, /transport_deeplink*, /g/* (except /g/banana/api/context).
- aircanada.com: /robots.txt returned HTTP 404 (no robots.txt). ToS governs instead.
- airtransat.com: Disallow */FlightSearch/ (legacy path), */Tests/, */Internal/ etc.; no Allow lines; current /en-CA/book paths not listed (ambiguous).
- westjet.com: Disallow /*/search and /*/rechercher; Allow: / otherwise. The Vue booking app lives at /shop/* which is NOT disallowed; the marketing "search" page is.
- flyporter.com: Disallow /Flight/Tickets/Book-Your-Travel, /tickets/select, /fares, /Rebook, /Reschedule; "Content-Signal: search=yes,ai-train=no,use=reference"; ClaudeBot and GPTBot → Disallow: /.
- flyflair.com: Allow: / for *, Content-Signal ai-train=no; ClaudeBot, GPTBot, CCBot, Bytespider, Amazonbot, Google-Extended, meta-externalagent → Disallow: /.
      </detail>
      <example_url>https://www.kayak.com/robots.txt ; https://www.expedia.ca/robots.txt ; https://www.skyscanner.ca/robots.txt ; https://www.westjet.com/robots.txt ; https://www.flyporter.com/robots.txt ; https://www.flyflair.com/robots.txt ; https://www.airtransat.com/robots.txt ; https://www.google.com/robots.txt ; https://www.aircanada.com/robots.txt (404)</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>Direct WebFetch of each robots.txt, 2026-09-04</source>
      <relevance>Google Flights, Kayak, Expedia, Skyscanner, Porter (booking paths) and WestJet (/search) are explicitly disallowed for generic crawlers; Flair permits; Air Canada has no robots.txt; Transat ambiguous. robots.txt is advisory, not an access control; it feeds the rate-limit / keep-or-drop decision in 002.</relevance>
      <confidence>high — direct fetch, exact lines quoted; aircanada.com 404 should be re-checked from the home IP</confidence>
    </finding>

    <finding category="terms-of-service">
      <title>ToS stance on automated access, per source</title>
      <detail>
- Google ToS (policies.google.com/terms): prohibits "using automated means to access content from any of our services in violation of the machine-readable instructions on our web pages (for example, robots.txt files that disallow crawling...)" — and robots.txt disallows /travel/flights/search.
- Kayak ToS (kayak.com/terms-of-use §4): "Scrape, harvest, deep-link to, train AI on, or otherwise use automated tools on our Site without our written permission" is prohibited.
- Expedia ToS (expedia.com/lp/b/terms-of-service; expedia.ca returned 429 to the fetcher): prohibits accessing, monitoring or copying content "using any robot, spider, scraper or other automated means or any manual process", violating robot exclusion headers, or bypassing access-limiting measures.
- Skyscanner ToS: page is JS-rendered; text not retrievable by fetch. Partner docs make deep links available only under the referral programme. Treat as prohibited absent partnership.
- Air Canada ToS (aircanada.com/ca/en/aco/home/legal/terms-of-use.html): prohibits access "through any manual process or any automatic, electronic or technical device, including ... automated scripts, robots, crawls, screen scrapers, web 'bots', deep-links, indexes, spiders ..." and "data mine", "screen scrape".
- Air Transat ToS (airtransat.com/en-US/legal-notice-en-us/terms-of-use-of-the-air-transat-sites): prohibits "software, applications, computer programs, automated scripts, macros, spiders or other 'screen scraping' software, robots, 'bot' ... to copy, extract, aggregate, store, distribute or manipulate the Content ... data mining or processing".
- WestJet: /en-ca/legal/terms-of-use returned 404; no ToS text retrieved (not found).
- Porter ToS (flyporter.com/en-us/terms-of-use): "You may not use any spider, robot or other automated or electronic agent to monitor or copy web pages or any Site Content".
- Flair ToS (flyflair.com/website-terms-conditions, via search snippet — page itself is Cloudflare-blocked to fetchers): prohibits automated robots, scripts, screen scrapers, crawlers to access/copy/extract/aggregate information.
      </detail>
      <example_url>https://policies.google.com/terms ; https://www.kayak.com/terms-of-use ; https://www.expedia.com/lp/b/terms-of-service ; https://www.aircanada.com/ca/en/aco/home/legal/terms-of-use.html ; https://www.airtransat.com/en-US/legal-notice-en-us/terms-of-use-of-the-air-transat-sites ; https://www.flyporter.com/en-us/terms-of-use ; https://www.flyflair.com/website-terms-conditions</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>WebFetch of ToS pages (Google, Kayak, Air Canada verbatim); WebSearch snippets for Expedia, Transat, Porter, Flair (2026-09-04)</source>
      <relevance>Every source that could be read forbids automated access; the plan must treat this as a personal, low-volume, non-commercial scraper with conservative rate limits and accept the possibility of blocks. Report only; the decision belongs to 002.</relevance>
      <confidence>high for Google/Kayak/Air Canada (quoted), medium for Expedia/Transat/Porter/Flair (search snippets), low/not found for WestJet and Skyscanner</confidence>
    </finding>


    <finding category="google-flights">
      <title>LIVE VERIFICATION (2026-09-04, headless Chromium 151 via Playwright 1.62, no stealth, residential WSL2 IP): what the Google Flights page exposes and how to drive it</title>
      <detail>
Search URL used: https://www.google.com/travel/flights/search?tfs=GhoSCjIwMjYtMTAtMTVqBRIDWVVMcgUSA0NERxoaEgoyMDI2LTEwLTIyagUSA0NER3IFEgNZVUxCAwEBAkgBmAEB&amp;hl=en-US&amp;curr=CAD&amp;gl=CA (YUL→CDG 2026-10-15, CDG→YUL 2026-10-22, 2 adults + 1 child, economy; tfs produced by fast-flights/faster-flights `create_query(...).params()`).
1. Load: HTTP 200, title "Montreal to Paris | Google Flights", 3.1 s to first row; no consent page (gl=CA), no "unusual traffic" page. Footer confirms Location: Canada, Currency: CAD.
2. Results DOM: rows are `li.pIav2d` (18 initially; a button "N more flights" expands to 26). Headings (h3): "Top departing flights", "Price insights", "Other departing flights" — i.e., Best and the rest in ONE load. Heading text varies ("Top departing options" on YQB→YYZ) and by locale (fr-CA: "Principaux vols de départ" / "Autres vols de départ"; tabs "Meilleurs vols" / "Le moins cher à partir de 2 173 $"), so do not key on text: take the first `[aria-label]` inside each row. Row aria-label (en): "From 2173 Canadian dollars round trip total. 1 stop flight with Porter Airlines and Air Transat. Leaves Montréal-Pierre Elliott Trudeau International Airport at 5:00 PM on Thursday, October 15 and arrives at … Total duration 11 hr 30 min. Layover (1 of 1) is a 2 hr 37 min layover at Toronto Pearson … " — price (round-trip TOTAL for all passengers), stops, carriers, times, total duration and layovers are all parseable from this one string; row inner text adds "CA$2,173 round trip", emissions, airport codes. fr-CA aria: "Aller-retour à partir de 2173 dollars canadiens (total). Vol …".
3. Tabs: role=tab "Best" and "Cheapest\nfrom CA$2,173". Clicking Cheapest sets `tfu=EgoIABAAGAAgAigB` (URL param; TfuState.search_mode = CHEAPEST) — 9 rows before expansion; same Top/Other headings. Sort control: button aria-label "Sorted by top flights, Change sort order." opens `menuitemradio` items [Top flights, Price, Departure time, Arrival time, Duration, Emissions]; choosing Duration sets `tfu=EgYIBRAAGAA` (sort=5) and re-renders as a single "Departing flights" list (first row = nonstop CA$2,884 for this search); Google also re-canonicalises `tfs` (adds entity types) — harmless. Both `tfu` strings are static and can be appended directly to the deep link, so cheapest/fastest are ONE page load each (or derive locally from the Best load's rows, which already carry price and total duration).
4. Bags: chip "Bags, Not selected" and a "bag fees" chip exist; the "All filters" dialog exposes only "Total carry-on bags: Remove/Add carry-on bag" for YUL→CDG (no checked-bag stepper on this route/market). So bag-inclusive re-pricing on the results page is carry-on-only here; checked-bag information comes from the booking page (below).
5. Round trip: clicking an outbound row → "Returning flights" list (2 rows for the Porter/Transat combo) with the same aria-label format; clicking a return → `https://www.google.com/travel/flights/booking?tfs=CBwQAhpgEgoy…` (stable deep link to the selected itinerary).
6. Booking page (no login): section "Booking options": "Book with Air Transat — Airline — CA$2,173 — Continue", "Book with FlightHub CA$2,254", "Book with Justfly.com CA$2,254", "Book with Gotogate CA$2,359", "Book with Porter Airlines — Price hidden because it might be incorrect — Visit site for price", "2 more booking options", then "Prices include required taxes + fees for 3 passengers. Optional charges and bag fees may apply." Itinerary block carries luggage text: "1 free carry-on per passenger | First checked bag costs between 150 Canadian dollars and 170 Canadian dollars per passenger | 1st checked bag per passenger: CA$150–170 | Fare non-refundable, taxes may be refundable". "Price insights": "CA$2,173 is low for Economy — CA$1,403 cheaper than usual; usually CA$2,700–5,600" (usable as Google's low/typical/high flag). The "Continue" link is the handoff to the airline/OTA (the airline URL is generated by Google on click; it was not followed in this research).
7. Network: the page POSTs `/_/FlightsFrontendUi/data/travel.frontend.flights.FlightsFrontendService/GetShoppingResults` (3× per search: initial, best, more) and `…/GetBookingResults` on the booking page. Bodies are batchexecute style (`)]}'` prefix then JSON; 38–57 KB for shopping, 93 KB for booking). The request `f.req` embeds the passenger counts `[2,1,0,0]` (adults, children, infants-in-seat, infants-on-lap) and the leg/airport arrays, so response interception (page.on("response")) is a viable parse path with a JSON structure documented by faster-flights (top group / other group, per-flight amenity flags: index [9] = checked bag included, [5] = carry-on/power, per-airline baggage URLs at payload[11]).
8. Burst test (5 different searches back-to-back, ~2–4 s each, then 3 more loads): all HTTP 200, no captcha/"unusual traffic". Caveat observed: row counts fluctuate (4 → 2 for the same YQB→CDG query) when the DOM is read ~1.5 s after the first row appears — results stream in; wait for the "Other departing flights" group / "more flights" button or for the 2nd–3rd GetShoppingResults response before reading. Infants change the candidate set drastically (2A+1C+1 lap infant → 2 rows at CA$6,808), and YQB→CDG returns few itineraries (2–4) vs YUL→CDG (18–26).
9. Timing: ~3 s per results load, ~5 s per click step; a full cheapest/fastest/best + booking-page pass for one (route, dates, pax) is ~6 page loads ≈ 30–40 s headless.
      </detail>
      <example_url>https://www.google.com/travel/flights/search?tfs=GhoSCjIwMjYtMTAtMTVqBRIDWVVMcgUSA0NERxoaEgoyMDI2LTEwLTIyagUSA0NER3IFEgNZVUxCAwEBAkgBmAEB&amp;hl=en-US&amp;curr=CAD&amp;gl=CA (Best); append &amp;tfu=EgoIABAAGAAgAigB (Cheapest) or &amp;tfu=EgYIBRAAGAA (sorted by Duration)</example_url>
      <selectors_or_endpoints>rows: li.pIav2d (first [aria-label] descendant = full itinerary sentence; text contains "CA$2,173 round trip"); groups: h3 headings (locale-dependent) or faster-flights RPC groups top/other; tabs: get_by_role("tab", name=/^Best|^Cheapest/); sort: get_by_role("button", name=/Sorted by/) → get_by_role("menuitemradio", name="Duration"); expand: get_by_role("button", name=/more flights/); filters: get_by_role("button", name="All filters") → dialog buttons "Add carry-on bag"; booking page: body text section "Booking options" (lines "Book with &lt;provider&gt;" + "CA$…"), bag text "1st checked bag per passenger: CA$…", "free carry-on"; RPC: POST …/GetShoppingResults, …/GetBookingResults (batchexecute JSON)</selectors_or_endpoints>
      <source>Own Playwright runs (scripts in session scratchpad) on 2026-09-04 from the user's WSL2 host; Playwright 1.62.0 + chromium-headless-shell 151.0.7922.34</source>
      <relevance>This is the ground truth for prompt 002/003: everything the user asked for (cheapest/fastest/best, total price incl. taxes for the pax config, carry-on inclusion, first-bag fee, deep link) is obtainable from Google Flights alone with ≤6 headless page loads per search.</relevance>
      <confidence>high — directly observed; medium for stability of class names (li.pIav2d has been stable since at least 2024 per third-party guides but is obfuscated) and for bag-text coverage on other carriers/routes (observed on a Transat/Porter itinerary only)</confidence>
    </finding>

    <finding category="google-flights">
      <title>Library assessment (installed and executed 2026-09-04): fast-flights 3.1.0 vs faster-flights 3.8.0 vs raw Playwright</title>
      <detail>
- fast-flights 3.1.0 (PyPI 2026-08-18, AWeirdDev, deps primp/protobuf/selectolax): `pip install fast-flights` then `import fast_flights` fails with ModuleNotFoundError: typing_extensions (missing runtime dependency; workaround `pip install typing_extensions`). After the fix, `get_flights(create_query(flights=[YUL→CDG, CDG→YUL], trip="round-trip", passengers=Passengers(adults=2, children=1), language="en-US", currency="CAD"))` returned ResultList len=1: a single WestJet+Condor 3-leg itinerary at 5106 — Google's server-rendered "lure" (its ranking token literally says "comprehensiveness_lure"); the real list only arrives via the GetShoppingResults RPC. The model (`Flights`) has no `is_best`, `select_token` or deep-link field. Fetcher: primp `Client(impersonate="chrome_145", impersonate_os="macos")`, no retries. Open issues #101 (best flights not parsed), #109 (fallback endpoint 401), #60 (round-trip return leg). Verdict: not usable as the data path; its `create_query().params()` remains a correct `tfs` builder (supports max_stops, airlines, time windows, max_price, carry_on_bags, checked_bags, hide_separate_and_self_transfer, exclude_basic_economy).
- faster-flights 3.8.0 (PyPI 2026-07-09, fork by jamexhuang; 0 stars, 3 open issues; docs in repo /docs): same builders + `ShoppingOptions(ranking_mode="best"|"cheapest", result_sort="top_flights"|"price"|"departure_time"|"arrival_time"|"duration"|"emissions")`, `SearchSession(mode="rpc-first"|"ssr-first", browser_fallback=…, browser_provider=PlaywrightBrowserProvider(headless=True))`, `select_flight()/get_return_flights()`, `build_booking_url()`, `MetaList` with `diagnostics` and `metadata.shopping.groups` (top/other with flight indices) and `Flights.rank/group_key/group_title/select_token`. Observed: rpc-first with adults=1 → 9 itineraries in 0.5 s, groups top=[0,1,2] other=[3..8], prices 732/740/…; adults=2 → 1463/1480 (= 2× → RPC price is the TOTAL for the requested passengers, matching the browser's "round trip total"); adults=2+children=1 → falls back to the single SSR itinerary (5106) — the RPC path does not work with children (every shopping mode returned len=1). Return step: `session.select(outbound[0]); session.results()` returned the same outbound list (issue #3, 2026-03-10: "get_return_flights() always falls back to one-way … bundled RT price is lost"); `is_complete` stayed False, so `booking_url()` is unusable. `diagnostics.used_default_rpc_params=True` on every call: the client sends a hard-coded `bl=boq_travel-frontend-flights-ui_20260303.06_p0` and `f.sid`; issue #4 (2026-07-30) says Google now requires a live `ds:1` bootstrap token + request-bound BotGuard (BGR) signature for GetShoppingResults and that type-13 error frames are misreported as empty — it still worked from this residential IP today but should be considered fragile. Docs (docs/baggage.md) document the RPC payload's baggage signals: `payload[11]` = per-airline baggage-policy URLs; `single_flight[12]` amenity flags where [9]=checked bag included (high confidence), [5]=power/carry-on (ambiguous), [1]=Wi-Fi. `PlaywrightBrowserProvider` only captures the next-leg GetShoppingResults after HTTP paths fail; it does not replay cookies.
- Raw Playwright (headless Chromium, no stealth): worked for every test (see live-verification finding). hugoglvs/google-flights-scraper (Playwright + Firefox, French locale, 3 commits) shows an alternative selector set (`.pIav2d`, `.yR1fYc`, price `.U3gSDe .FpEdX span`, duration `.AdWm1c.gvkrdb`, stops `.EfT7Ae .ogfYpf`, airline `.Ir0Voe .sSHqwe`, category sections `.zBTtmb`/`.Rk10dc`) but is unmaintained; Scrapfly's 2026-08-10 guide uses `li.pIav2d`, `div[jsname='XxAJue']` detail panels, `div[aria-label^='Total duration']`, aria-label price regex. Scraperly (2026-06) rates Google Flights "Hard 4/5": Google WAF + 429 rate limiting, TLS/JS/canvas fingerprinting; residential IP "required", exponential backoff on 429, "10–30 requests per IP before rotating" (proxy-vendor framing; our residential burst saw no throttling).
Recommendation: Playwright-first (DOM aria-labels + optional RPC interception) with faster-flights used only as the `tfs`/`tfu` builder and a fast adult-only pre-check; watch jamexhuang/flights #3/#4 and AWeirdDev/flights #101 before relying on either library's data path.
      </detail>
      <example_url>https://pypi.org/project/faster-flights/ (3.8.0, 2026-07-09); https://github.com/jamexhuang/flights (docs/return-flights.md, docs/baggage.md, docs/local.md; issues #3, #4); https://pypi.org/project/fast-flights/ (3.1.0, 2026-08-18); https://github.com/AWeirdDev/flights/issues/101</example_url>
      <selectors_or_endpoints>faster-flights: create_query(flights, seat, trip, passengers, language, currency, max_stops) → Query.url()/params(); get_flights(q, shopping=ShoppingOptions(...)); SearchSession(q, mode, browser_fallback, browser_provider); shopping.py builds f.req with passenger_counts tuple; RPC path: /_/FlightsFrontendUi/data/travel.frontend.flights.FlightsFrontendService/GetShoppingResults?f.sid=…&amp;bl=…</selectors_or_endpoints>
      <source>Installed both packages with uv in scratch venvs and ran them against YUL/YQB routes on 2026-09-04; PyPI JSON; GitHub API contents of jamexhuang/flights docs; issue pages</source>
      <relevance>Prevents 003 from building on a library whose data path is broken; gives exact API names for the builder functions that still work.</relevance>
      <confidence>high — executed locally today; library internals may change quickly (both projects are single-maintainer)</confidence>
    </finding>
    <finding category="google-flights">
      <title>Google Flights: deep link via protobuf `tfs`, Best/Cheapest tabs, sort in `tfu`, bag-fee filter; fast-flights 3.1.0 works without a browser</title>
      <detail>
1. URL format: https://www.google.com/travel/flights/search?tfs={urlsafe-b64 protobuf, no padding}&amp;hl=en&amp;gl=CA&amp;curr=CAD (curr and hl/gl are plain query params). The tfs message (community spec, gist by MomoDeve): `repeated FlightLeg legs = 3` (FlightLeg: `departure_date = 2` "YYYY-MM-DD", `max_stops = 5`, `origin = 13`, `destination = 14`; Place: `entity_type = 1` (1 = airport), `entity_id = 2` IATA), `repeated PassengerType passengers = 8` (ADULT=1, CHILD=2, INFANT_ON_LAP=3, INFANT_IN_SEAT=4 — one enum entry per traveller; NO child age is encoded, Google's "child" = 2–11), `Cabin cabin = 9` (ECONOMY=1 ...), `BaggageFilter baggage = 13` (field_2 = carry-on count), `TripType trip_type = 19` (ROUND_TRIP=1, ONE_WAY=2). Round trip = two legs (YUL→CDG date1, CDG→YUL date2) + trip_type=1. fast-flights ships an equivalent `flights.proto` (enums Seat/Trip/Passenger; message Info/FlightData/Airport) and builds this for you.
2. Tabs/sorts: the results page shows "Top departing flights" (= Best) and "Other departing flights" in ONE load. The Cheapest tab and the sort menu (Price, Departure time, Arrival time, Duration, Emissions) change a companion `tfu` protobuf param: `TfuState { SortMode sort = 1 }` with SORT_TOP_FLIGHTS=1, SORT_PRICE=2, SORT_DEPARTURE_TIME=3, SORT_ARRIVAL_TIME=4, SORT_DURATION=5, SORT_EMISSIONS=6. Google's help page: Best = "best trade-offs between price, convenience, and ease of booking" using "duration, number of stops and airport changes during layovers"; Cheapest "prioritizes low prices, and includes additional itineraries and prices from online travel agents" (so Cheapest can surface OTA fares absent from Best). Practical rule: one load (Best) yields best + a full list that can be locally re-sorted for cheapest/fastest among the SAME candidate set; a second load with sort=PRICE is needed only to capture extra OTA itineraries.
3. Rendering: results are embedded in the HTML as JS data; fast-flights v3 "switched from HTML parsing to JavaScript data extraction" and needs "No Playwright by default (there's an optional fallback for edge cases)". A plain curl of /travel/flights with a Chrome UA returned HTTP 200 (server: ESF, only NID cookie) from the probe host, so no bot-manager challenge on the landing page. XHR: the page also calls internal batchexecute RPCs (`/_/FlightsFrontendUi/data/...`) — these are not documented and not needed when using fast-flights.
4. Final price: Google never checks out; clicking an itinerary opens "Booking options" listing airline/OTA links with a per-provider total for all passengers (incl. taxes) and a "Book on Google" for some. The deep link to that itinerary page is a stable URL (tfs + selected flights). Handoff to the airline is a redirect with the airline's own search params (e.g., Air Canada URL above).
5. Luggage: (a) BaggageFilter (tfs field 13, field_2 = carry-on count) and the "Filter prices by bag fees" feature ("show flight prices that include the cost of checked bags or carry-on bags"; prices update, flights are not removed; coverage/airlines not published; fees "may be subject to additional government taxes") — running the same search with carry-on=1 and, separately, checked=1 and diffing against the base price gives per-itinerary bag surcharges where Google has partner data; (b) a crossed-out suitcase icon marks Basic-economy fares without carry-on; (c) "Basic economy" is exposed as a separate class in the fare-class filter (2025) and "exclude basic economy" is a fast-flights filter.
6. Anti-bot: no Akamai/PX/DataDome; reCAPTCHA scripts present in the page bundle (4 refs) but no challenge served. fast-flights open issues: #101 (2026-03-05) "Best flights / results not getting parsed" (only "other results" parsed; open, no maintainer reply), #109 (2026-05-22) 401 from try.playwright.tech fallback endpoint on v2.2, #60 (2025-05-17) round-trip return leg not returned, #86 (2025-10-30) empty-result detection. Releases: 3.0 (2026-06-13), 3.0.1/3.0.2 (June 2026), 3.1.0 (2026-08-18), requires Python ≥3.10, 2.0k stars, 19 open issues. Treat "is_best" from fast-flights as unreliable until #101 is confirmed fixed in 3.1.0; recompute best locally.
7. robots.txt disallows /travel/flights/search; ToS ties automated access to robots.txt. Locale: hl=fr-CA changes all visible strings (e.g., "Meilleurs vols") — pin hl=en and gl=CA, curr=CAD; selectors should be ARIA/role-based, not text-based.
      </detail>
      <example_url>https://www.google.com/travel/flights/search?tfs=&lt;build with fast_flights.create_query(FlightQuery(...), Passengers(adults=2, children=1), trip="round-trip", seat="economy", currency="CAD")&gt;&amp;hl=en&amp;gl=CA&amp;curr=CAD — YUL→CDG 2026-10-15 / CDG→YUL 2026-10-22, 2 adults + 1 child (child age not encodable; Google child = 2–11)</example_url>
      <selectors_or_endpoints>Results list: role="list" items under headings "Top departing flights" / "Other departing flights" (classes such as li.pIav2d, span.YMlIz for price are obfuscated and rotate — use aria-labels: each row has aria-label containing "From CA$..." price, duration, stops); Cheapest tab: role="tab" name "Cheapest"; sort menu: button aria-label "Sort by"; bag filter: button "Bags"; tfu param SortMode as above. fast-flights internals: fast_flights.flights_pb2 (Info/FlightData/Passenger enums).</selectors_or_endpoints>
      <source>https://github.com/AWeirdDev/flights (README, issues #60 #86 #101 #109); https://pypi.org/pypi/fast-flights/json (3.1.0, 2026-08-18); https://gist.github.com/MomoDeve/a18053dea84dd28e320b8b2c489540eb (tfs/tfu spec); https://support.google.com/travel/answer/7664728 (Best/Cheapest definition); https://support.google.com/travel/answer/9074247 (bag-fee filter); https://themenonlab.blog/blog/fast-flights-google-flights-api-python (2026-08-09, v3 no-browser); curl probe 2026-09-04</source>
      <relevance>Primary source for v1. Gives cheapest/fastest/best per (route, date, pax) from 1–2 HTTP loads, bag-inclusive prices via filter, and a deep link that hands off to the airline.</relevance>
      <confidence>high for URL/tabs/no-browser fetch (official docs + library + probe); medium for is_best parsing (open issue #101) and bag-filter coverage on Canadian carriers (not published)</confidence>
    </finding>

    <finding category="kayak">
      <title>Kayak: path-encoded deep link incl. children ages, native sort param, poll XHR; PerimeterX/HUMAN reported, ToS/robots prohibit</title>
      <detail>
1. URL: https://www.ca.kayak.com/flights/{ORIG}-{DEST}/{YYYY-MM-DD}/{YYYY-MM-DD}/{N}adults/children-{age}[-{age}...]?sort=bestflight_a. Probe of https://www.ca.kayak.com/flights/YUL-CDG/2026-10-15/2026-10-22/2adults/children-8?sort=bestflight_a returned HTTP 200 with title "YUL to CDG, 15/10 – 22/10" and the page reflected "2 adults and 1 child" — path encoding of passengers works. Cabin class segment (/business, /premium) and lap/seat infant tokens exist in Kayak's deeplink generator but the affiliate help page (help.affiliates.kayak.com/article/587) did not resolve from the fetcher, so infant tokens are unverified. ca.kayak.com → CAD (page JSON contains "currencyCode":"CAD" among a currency list; the results header prices are in CAD on the .ca domain).
2. Sorts: `sort=bestflight_a` (Best/Recommended), `price_a` (Cheapest), `duration_a` (Quickest), `depart_a|depart_d`, `arrive_a|arrive_d`; filter `fs=stops=0`. Kayak "Best" = "a blend of price and convenience that sometimes places a sponsored or slightly pricier option at the very top"; Best suppresses some self-transfer itineraries, Cheapest surfaces Basic Economy and Hacker Fares. All three sorts likely come from the same poll payload, but the ranking scores are server-side — plan should capture one poll response and rely on Kayak's own `sort` order only for "best" (ranking not reproducible locally).
3. Rendering: frontend polls https://www.kayak.com/i/api/search/dynamic/flights/poll (Scrapfly 2026-07-27: "Kayak's own frontend loads results by polling an internal endpoint"); results are NOT in the initial HTML. The poll needs the session cookies (Apache, kayak, csid, p1.med.sid/token ...) and a search id created by the page; call it via page.request/response interception, not standalone.
4. Final price: metasearch — "View Deal" redirects to the airline/OTA; "Book on KAYAK" (direct booking, launched with Air Canada first) exists for some carriers. Kayak displayed prices "cover the base fare, applicable taxes and mandatory fees" but not bags.
5. Luggage: Fee Assistant (left panel) — set number of carry-on / checked bags and "the results immediately update to include the cost of your luggage"; it is a planning tool (estimates from airline policies). The URL form of the fee-assistant state is not documented (searched "fs=cfc/bfc" — not found); toggling via DOM is required.
6. Anti-bot: contradictory reports — Zenrows/Scrapfly/ScrapingBee (2026) describe PerimeterX/HUMAN "Press &amp; Hold" on Kayak; Scraperly (April 2026) rates Kayak "Very Hard 5/5" and names Akamai + CAPTCHA + fingerprinting. Our plain-curl probe got a 200 results shell with server "KAYAK/1.0", no _abck/_px cookies and no px/akamai markers in HTML — so the challenge (if any) is applied on the poll XHR / after behavioural scoring, not on first HTML.
7. robots.txt disallows /flights/ for *; ToS §4 forbids scraping/automated tools without written permission.
      </detail>
      <example_url>https://www.ca.kayak.com/flights/YUL-CDG/2026-10-15/2026-10-22/2adults/children-8?sort=bestflight_a (verified 200); cheapest: ...?sort=price_a ; fastest: ...?sort=duration_a</example_url>
      <selectors_or_endpoints>XHR: POST https://www.ca.kayak.com/i/api/search/dynamic/flights/poll (session-bound). DOM: results container [class*="resultInner"] / [data-resultid]; Fee Assistant: aside panel "Fee Assistant" with steppers for "Carry-on bag" / "Checked bag"; sort tabs: role="tablist" with "Best", "Cheapest", "Quickest".</selectors_or_endpoints>
      <source>https://scrapfly.io/blog/posts/how-to-scrape-kayak (2026-07-27); https://www.kayak.com/terms-of-use; https://pointmetotheplane.boardingarea.com/kayak-baggage-assistant/; https://www.zenrows.com/blog/perimeterx-bypass (2026); https://scraperly.com/scrape/kayak (2026-04); curl probe 2026-09-04</source>
      <relevance>Best-in-class OTA metasearch for bag-inclusive comparisons and native best/cheapest/fastest; but explicit ToS/robots prohibition and HUMAN/Akamai risk make it an opportunistic, very-low-volume source.</relevance>
      <confidence>high for URL format and sort params (verified + 2026 source); medium for XHR usability and vendor identity (contradictory reports); low for infant tokens and fee-assistant URL state</confidence>
    </finding>

    <finding category="expedia">
      <title>Expedia.ca: official deep link with per-child ages; Akamai Bot Manager returns 429 to non-browser clients; robots + ToS prohibit</title>
      <detail>
1. URL (official Expedia Group white-label deeplink doc): https://www.expedia.ca/go/flight/search/Roundtrip/{YYYY-MM-DD}/{YYYY-MM-DD}?FromAirport=YUL&amp;ToAirport=CDG&amp;NumAdult=2&amp;NumChild=1&amp;Child1Age=8&amp;Class=3&amp;currency=CAD (NumAdult/NumChild/NumSenior 1–6; Child{n}Age required when NumChild>0; InfantInSeat=1 for seated infant, omit for lap; Class: 3 Economy, 2 Business, 1 First; Direct=1). It resolves to /Flights-Search?trip=roundtrip&amp;leg1=from:YUL,to:CDG,departure:10/15/2026TANYT&amp;leg2=...&amp;passengers=children:1[8],adults:2,seniors:0,infantinlap:N&amp;options=cabinclass:economy&amp;mode=search (legacy form seen in 2017–2024 scrapers; `options=sortby:price` appears in Expedia's own airline landing links; XAP deeplinks use `Sort=10`). No documented sortType/sortOrder parameter for the current UI; sort is a UI control (price, duration, departure/arrival time; "Recommended" default).
2. Sorts: Recommended (default), Price, Duration, Departure, Arrival. No "Best/Cheapest/Fastest" tabs; one results load contains all itineraries so cheapest/fastest can be computed locally; "Recommended" ranking is proprietary.
3. Rendering: results come from Expedia's GraphQL (`/graphql` with operation FlightsSearch...) after JS; the page requires JS. Not callable standalone (Akamai sensor + session).
4. Final price: Expedia is an OTA — checkout happens on Expedia; guest checkout (email + payment, no account) is available per 2026 guides; the review/"Trip summary" page shows total incl. taxes and fees before payment. Reaching it requires: results → choose outbound → choose return → fare selection (Basic/Standard/…) → traveller details → checkout; ~5 JS navigations. Not verified in this research (fetcher was rate-limited).
5. Luggage: fare-selection step lists what each fare includes (carry-on / checked bag) and results show a "Fees for baggage" link; no bag-price re-pricing on results.
6. Anti-bot: probe of the deep link from the research host returned HTTP 429 with Akamai cookies (_abck, bm_sz, bm_s, bm_so) and header x-akamai-reference-id → Akamai Bot Manager, immediate block for non-browser TLS. The 2026 marsproxies article claims "DataDome ... since 2025 scores navigation intent" — our probe shows Akamai, not DataDome (contradiction flagged; Akamai evidence is direct).
7. robots.txt disallows /Flights-Search, /Flight-SearchResults, /Flights-BagFees, /FlightCheckout, /Checkout; ToS prohibits robots/scrapers and bypassing access controls.
      </detail>
      <example_url>https://www.expedia.ca/go/flight/search/Roundtrip/2026-10-15/2026-10-22?FromAirport=YUL&amp;ToAirport=CDG&amp;NumAdult=2&amp;NumChild=1&amp;Child1Age=8&amp;Class=3&amp;currency=CAD (probe: HTTP 429, Akamai)</example_url>
      <selectors_or_endpoints>XHR: POST https://www.expedia.ca/graphql (FlightsSearch operations; session/Akamai-bound). DOM (reported by 2025–2026 scrapers): li[data-test-id="offer-listing"], [data-test-id="listing-price-dollars"], sort control [data-test-id="sort-dropdown"] / "Sort by" select.</selectors_or_endpoints>
      <source>https://developers.expediagroup.com/white-label-travel-platform/traffic-growth/deeplinking/flight-deeplinks (official); https://gist.github.com/scrapehero/bc34513e2ea72dc0890ad47fbd8a1a4f (legacy /Flights-Search form, stale); https://marsproxies.com/blog/web-scraping-expedia/ (2026); https://www.expedia.com/lp/b/terms-of-service; curl probe 2026-09-04 (429 + Akamai)</source>
      <relevance>Only OTA where the final checkout price is reachable without login, but the most aggressively protected of the nine to non-browser traffic. Defer.</relevance>
      <confidence>high for URL format (official doc) and Akamai (direct probe); low for sort params and checkout reachability (not verified)</confidence>
    </finding>

    <finding category="skyscanner">
      <title>Skyscanner.ca: official referral URL with child ages, Best/Cheapest/Fastest, single XHR; PerimeterX confirmed and actively blocking in 2026</title>
      <detail>
1. URL (official Skyscanner referral docs): https://www.skyscanner.ca/transport/flights/{orig}/{dest}/{YYMMDD}/{YYMMDD}/?adultsv2=2&amp;childrenv2=8&amp;cabinclass=economy&amp;rtn=1&amp;preferdirects=false[&amp;market=CA&amp;locale=en-CA&amp;currency=CAD]. `adultsv2` = passengers 18+ (per doc), `childrenv2` = ages joined by "|" (e.g. 8|12; URL-encoded %7C), ages 2–17; infants (&lt;2) are not part of childrenv2. Probe returned HTTP 200, title "Cheap flights from Montreal to Paris at Skyscanner", page JSON "currency":"CAD","locale":"en-CA","market":"CA" — the .ca domain sets Canadian market/CAD automatically.
2. Sorts: Best (default), Cheapest, Fastest tabs; URL `sortby=cheapest|fastest` (day view); Best = Skyscanner learning-to-rank combining price, journey time, directness. The web-unified-search JSON "lacks best/cheapest/fastest categorization — sorting happens client-side" (Scrapfly 2026-08-14), so ONE XHR capture gives cheapest/fastest; "best" order must be read from the DOM (or approximated locally).
3. Rendering: HTML has no results; data comes from XHR `/g/radar/api/v2/web-unified-search/` (itineraries.results[] with carriers, ISO times, durationInMinutes, stopCount, price string, pricingOptions[]); the mobile endpoint `/g/radar/api/v2/unified-search` needs PerimeterX Mobile SDK tokens. Session cookies (__Secure-anon_token, _pxhd, traveller_context...) are required.
4. Final price: metasearch handoff via /transport_deeplink (disallowed in robots) to airline/OTA; "Book on Skyscanner" for some partners. No checkout on Skyscanner in general.
5. Luggage: results show fare-type labels for some partners but no bag re-pricing; carry-on/checked inclusion is not reliably exposed on results (unverified; treat as "no").
6. Anti-bot: PerimeterX confirmed by probe (Set-Cookie _pxhd on first HTML). GitHub irrisolto/skyscanner issue #2 (2026-02-17, open): persistent 403 "Access banned. CAPTCHA challenge encountered" despite IP rotation. Scrapfly: "A PerimeterX captcha page returns HTTP 200". Skyscanner Python libraries on GitHub are effectively broken in 2026.
7. robots.txt disallows /transport/* and /transport_deeplink*; ToS unreadable (JS page), partner programme governs deep links.
      </detail>
      <example_url>https://www.skyscanner.ca/transport/flights/yul/cdg/261015/261022/?adultsv2=2&amp;childrenv2=8&amp;cabinclass=economy&amp;rtn=1&amp;preferdirects=false (verified 200)</example_url>
      <selectors_or_endpoints>XHR: POST https://www.skyscanner.ca/g/radar/api/v2/web-unified-search/ ; readiness selector: //span[contains(text(),'results sorted by')] ; tabs: role="tab" "Best" / "Cheapest" / "Fastest" ; itinerary cards: [class*="FlightsTicket"] (obfuscated, rotate)</selectors_or_endpoints>
      <source>https://developers.skyscanner.net/docs/referrals/flights-parameters (official); https://scrapfly.io/blog/posts/how-to-scrape-skyscanner (2026-08-14); https://github.com/irrisolto/skyscanner/issues/2 (2026-02-17); curl probe 2026-09-04 (_pxhd)</source>
      <relevance>Good metasearch coverage and native tabs, but PerimeterX + robots + partner-only deep links → optional source, expect breakage.</relevance>
      <confidence>high for URL/params (official) and PerimeterX (probe + 2026 issue); medium for XHR field shape (2026 article)</confidence>
    </finding>

    <finding category="air-canada">
      <title>Air Canada: confirmed deep link with ADT/YTH/CHD/INF/INS, Angular app on GraphQL AppSync, Akamai Bot Manager; fare families and 2026 bag fees</title>
      <detail>
1. URL: https://www.aircanada.com/booking/ca/en/aco/availability/rt/outbound?org0=YUL&amp;dest0=CDG&amp;departureDate0=2026-10-15&amp;org1=CDG&amp;dest1=YUL&amp;departureDate1=2026-10-22&amp;ADT=2&amp;YTH=0&amp;CHD=1&amp;INF=0&amp;INS=0&amp;lang=en-CA&amp;tripType=R&amp;marketCode=INT. Evidence: (a) the same parameter names appear on an indexed Aeroplan URL (aircanada.com/aeroplan/redeem/availability/outbound?tripType=O&amp;org0=CAN&amp;dest0=YYZ&amp;departureDate0=2023-06-06&amp;ADT=1&amp;YTH=0&amp;CHD=0&amp;INF=0&amp;INS=0); (b) probe of the revenue URL returned HTTP 200 with the Angular booking shell (main.5e62cc24610d4770.js, /booking/ base href); (c) the bundle contains org0/dest0/departureDate0/departureDate1/tripType/marketCode/lang/promoCode and the pax codes ADT (adult 12+? — AC counts YTH 12–17 separately), YTH (youth 12–17), CHD (child 2–11), INF (infant on lap), INS (infant in seat). marketCode: DOM (domestic), TNB (transborder), INT (international) — inferred from AC conventions, unverified; lang fr-CA switches locale.
2. Sorts: no "best"; the availability page offers sort/filters (price, duration, departure) in the UI; not URL-driven (unverified). One load shows outbound options with fare-family prices (round-trip pricing applies after selecting outbound → inbound page), so "cheapest/fastest round trip" requires outbound selection + inbound page = 2+ loads per pax config.
3. Rendering: JS app; data via GraphQL AppSync. Endpoints found in the bundle: LFS "https://ak-lfs-appsync-api-ecom.digital.aircanada.com/graphql" (Low Fare Search — availability/pricing), LFC (…lfc…/graphql), cart (…cart…/graphql), purchase, profile, auth, targeted-content (all via akamai-gw / "ak-" hosts, EU fallbacks *.euc1.ac-aco.cloud.aircanada.com). Requests carry `x-api-key` (constant in bundle) + `Authorization` (short-lived token from the auth GraphQL) + Akamai sensor cookies. Do NOT call standalone; capture with page.on("response") filtered on "/graphql" while the browser drives the flow.
4. Final price: app routes seen in bundle: availability → (fare selection on availabilityDetails) → passengers → seats / seats-price-breakdown → review-trip → payment. Air Canada allows booking as a guest (Aeroplan sign-in is optional; passengers step collects names/DOB). The Review Booking page shows "the total price you'll have to pay and the breakdown of the amounts of applicable taxes and fees" (AC FAQ). Not verified by automation here; Playwright must fill passenger names (dummy data) to reach review-trip — the plan should decide if that is acceptable (it creates no booking until payment).
5. Luggage / fare families (Economy): Basic, Standard, Flex, Comfort, Latitude (+ Premium Economy, Business Standard/Latitude). Carry-on: "Economy Basic fare tickets purchased on or after January 3, 2025, no longer include carry-on baggage" within Canada, to/from the U.S., Mexico, Central America, Caribbean (personal item only); Basic to Europe/international still includes a carry-on; Standard+ include carry-on everywhere. Checked: Basic and Standard = 0 bags on North America; Flex = 1; Comfort/Latitude = 2. Fees (tickets purchased on/after 2026-04-13, aggregators): 1st bag CA$45, 2nd CA$60 (NA); Basic transatlantic ~CA$75 first bag (fare-based allowance; international rules updated 2026-05-14). The fare-family picker on the availability page displays inclusions per fare (carry-on icon, checked-bag count); the exact bag fee for the itinerary is in the extras step / AC "baggage calculator" (dynamic).
6. Anti-bot: Akamai Bot Manager confirmed (Set-Cookie _abck, bm_sz, bm_s, bm_so; header akamai-grn; sensor script src "/oQr_7W-AF2THE1toSPAjOmCrEj8/..."). Tolerance for low-volume headed patchright from a residential IP is unknown (no 2025–2026 public report specific to aircanada.com found); Akamai is described as the vendor where TLS/JA4 + behaviour matter most, with 2026 reports that patched Chromium passes standard configs but "behavioral analysis still catches it on the highest-security configurations".
7. No robots.txt; ToS forbids screen-scraping and automated access outright.
      </detail>
      <example_url>https://www.aircanada.com/booking/ca/en/aco/availability/rt/outbound?org0=YUL&amp;dest0=CDG&amp;departureDate0=2026-10-15&amp;org1=CDG&amp;dest1=YUL&amp;departureDate1=2026-10-22&amp;ADT=2&amp;YTH=0&amp;CHD=1&amp;INF=0&amp;INS=0&amp;lang=en-CA&amp;tripType=R&amp;marketCode=INT (probe: 200 app shell)</example_url>
      <selectors_or_endpoints>GraphQL: https://ak-lfs-appsync-api-ecom.digital.aircanada.com/graphql (availability/pricing), …cart…/graphql, …purchase…/graphql; headers x-api-key + Authorization. App routes: /booking/ca/en/aco/availability/rt/outbound, …/availability/rt/inbound, …/passengers, …/seats, …/review-trip, …/payment. DOM: fare cards by role="button" with fare names "Basic|Standard|Flex|Comfort|Latitude" (fr-CA: "Base|Standard|Flex|Confort|Latitude").</selectors_or_endpoints>
      <source>curl probes + bundle grep 2026-09-04; https://www.aircanada.com/ca/en/aco/home/plan/baggage/carry-on.html (official, Basic carry-on rule); https://deeparrival.com/airlines/air-canada/baggage-fees/ (2026 fees, aggregator); https://www.aircanada.com/ca/en/aco/home/legal/terms-of-use.html; https://github.com/api-evangelist/air-canada (no public API)</source>
      <relevance>Largest carrier at YUL/YQB; fare families and bag rules are well defined; deep link exists; Akamai is the main risk.</relevance>
      <confidence>high for URL params and Akamai (direct evidence); medium for fare/bag inclusions (official carry-on page + aggregator fee tables); low for review-page automation and marketCode semantics</confidence>
    </finding>

    <finding category="air-transat">
      <title>Air Transat: no public deep link found; Kentico site + Softvoyage booking engine; Imperva/Incapsula; Eco Budget lost carry-on on Sun/US/Canada</title>
      <detail>
1. URL: NOT FOUND. /en-CA/book/book-a-flight (HTTP 200, Kentico CMS: ASP.NET_SessionId, CMSPreferredCulture) hosts a JS booking widget; the page config references "tdpBookingDesktop":"https://bookings.airtransat.com/…" (TSOnline / Softvoyage engine with legacy .do actions), "reservationsSV":"https://reservations.transat.com", "napi"/"edmRender": https://api.transat.com/…, plus a `data-submit-url="/en-CA/search"` (site search, not flights). /en-CA/flight-search-result exists (title "Flight Search Results | Air Transat") but its query-string parameters are not exposed in the HTML; the search form posts via JS. Searches for depDate/retDate/org/dest style params found nothing. Plan must drive the form with Playwright (origin, destination, dates, adults, children with ages) and read the resulting URL/XHR.
2. Sorts: unknown (UI likely offers price/time filters; no "best").
3. Rendering: JS; XHRs to api.transat.com / bookings.airtransat.com expected — capture via response interception.
4. Final price: unclear; Transat's engine reaches a passenger/summary page before payment; guest booking is normal for leisure carriers; not verified.
5. Luggage / fare options: Eco Budget, Eco Standard, Eco Flex (+ Club Standard/Club Flex). Carry-on: Eco Budget = personal item only on Sun, Caribbean, US and domestic routes (change effective Feb 2025, CBC), carry-on still included on Europe (+ Morocco, Peru); carry-on "not permitted" as an add-on on Eco Budget Sun/US/Canada (aggregator 2026-08-18). Eco Standard: carry-on everywhere + 1 × 23 kg checked bag on Europe (not on Sun/US/Canada); Eco Flex: 1–2 checked bags + free changes; Club: 2 bags. Checked bag fees: "shown during booking or in Manage My Booking, and vary with the ticketing date"; aggregators: CA$55–67.50 first bag within 24 h of departure, CA$100 at airport (2026-06-01). Fare picker on results shows inclusions per fare; exact bag price appears in the extras step.
6. Anti-bot: Imperva/Incapsula confirmed (x-cdn: Imperva, x-iinfo, incap_ses_*, visid_incap_*, nlbi_* cookies). No public 2025–2026 report on headless tolerance; Incapsula typically challenges datacenter IPs and headless signatures but is quieter than Akamai/PX for residential headed browsers (general vendor reports, not Transat-specific).
7. robots.txt disallows only legacy */FlightSearch/; ToS forbids screen-scraping/data mining.
      </detail>
      <example_url>no deep link found — entry point https://www.airtransat.com/en-CA/book/book-a-flight (form-drive); results page https://www.airtransat.com/en-CA/flight-search-result (params unknown)</example_url>
      <selectors_or_endpoints>Hosts: bookings.airtransat.com (TSOnline .do actions), reservations.transat.com, api.transat.com; DOM: booking widget on /en-CA/book/book-a-flight (inputs for "From", "To", dates, "Travellers" with adults/children/infants + child age selects); fare picker labels "Eco Budget|Eco Standard|Eco Flex" (fr-CA: "Éco Budget|Éco Standard|Éco Flex")</selectors_or_endpoints>
      <source>curl probe + HTML grep 2026-09-04; https://www.cbc.ca/news/business/air-transat-baggage-1.7454594 (Feb 2025 carry-on change); https://aifly.one/guides/air-transat-baggage-allowance/ (verified 2026-08-18); https://www.airtransat.com/en-US/travel-information/fare-options (official page, JS-rendered); ToS via search snippet</source>
      <relevance>Key carrier for YUL/YQB→Europe/Sun; feasible by form-driving; bag rules known.</relevance>
      <confidence>medium — vendor and hosts verified; fare rules from CBC + aggregators; no deep link (searched thoroughly)</confidence>
    </finding>

    <finding category="westjet">
      <title>WestJet: booking is a Vue SPA at /shop/*, deep-link query format unconfirmed, weakest visible anti-bot; official fare table incl. UltraBasic carry-on rule</title>
      <detail>
1. URL: UNCLEAR. https://www.westjet.com/shop/summary (HTTP 200, 2.4 KB shell, title "WestJet Flight Search", Vite/Vue bundle /shop/assets/main-BF8NCKGz.js, hosted on Azure "Windows-Azure-Web/1.0"). The bundle's store uses origin, destination, departureDate, returnDate, adults, children, infants, tripType (ONE_WAY/ROUND_TRIP/MULTI_CITY), cabin, numAdults/numChildren — but no confirmed query-string contract was found (searches for "shop/summary?origin=" returned nothing). The marketing page /en-ca/flights hosts the search widget that navigates into /shop. Approach: drive the widget with Playwright, then record the resulting /shop/... URL to see whether state is in the query string (likely) — if so, reuse it as a deep link.
2. Sorts: none native ("best"); UI sorts unverified.
3. Rendering: JS; XHR/GraphQL from the shop app (hosts not literal in bundle — built dynamically); capture via response interception.
4. Final price: WestJet supports guest booking; the flow is flights → fare bundle → passengers → extras/seats → review → payment; not verified here.
5. Luggage / fare bundles (official /en-ca/flights/our-fares table): UltraBasic (carry-on ✖ in North/Central America — "not allowed to bring or pay for a carry-on bag except when travelling to and from Europe and Asia or when Extended Comfort has been purchased for all flights in a single direction"; checked bag fee; no changes), Econo (carry-on ✔, checked fee), EconoFlex (carry-on ✔, 1 checked bag, changes ✔), Premium/PremiumFlex/Business/BusinessFlex (2 bags). No "Basic" fare exists in the current lineup. Fees (tickets on/after 2026-04-23, aggregators; official /en-ca/flights/fees table is JS-rendered): US/Canada 1st bag prepaid UltraBasic CA$55–65, Econo CA$45–53, airport ~CA$70; Europe: UltraBasic ~CA$80–94 first bag, 2nd ~CA$110–130.
6. Anti-bot: no vendor markers on the /shop shell or bundle (no PerimeterX/Akamai/DataDome/Turnstile strings); marketing page loads reCAPTCHA (2 refs) and AWS ALB cookies. Lowest apparent friction of the five carriers (unverified against the search XHR).
7. robots.txt disallows /*/search and /*/rechercher (marketing search), not /shop; ToS page not found (404) — stance unknown.
      </detail>
      <example_url>entry: https://www.westjet.com/en-ca/flights (search widget) → app https://www.westjet.com/shop/summary (query contract to be recorded during the first Playwright run)</example_url>
      <selectors_or_endpoints>Shop app bundle /shop/assets/main-*.js; state keys origin/destination/departureDate/returnDate/adults/children/infants/tripType/cabin; fare names "UltraBasic|Econo|EconoFlex|Premium|PremiumFlex|Business|BusinessFlex"; widget on /en-ca/flights: inputs "From", "To", date pickers, "Guests" popover (Adults/Children/Infants), child age selects</selectors_or_endpoints>
      <source>curl probes + bundle grep 2026-09-04; https://www.westjet.com/en-ca/flights/our-fares (official table); https://deeparrival.com/airlines/westjet/baggage-fees/ (2026-04-23 fees, aggregator); https://www.westjet.com/en-ca/news/2024/westjet-introduces-ultrabasic-</source>
      <relevance>Second-largest carrier for the routes; likely the easiest airline to automate; luggage rules fully known.</relevance>
      <confidence>medium — fare table official; deep link unconfirmed; anti-bot only inferred from absence of markers</confidence>
    </finding>

    <finding category="porter">
      <title>Porter: booking host unreachable from probe, www behind Cloudflare challenge; fare classes and 2026 bag fees documented</title>
      <detail>
1. URL: NOT FOUND. Booking engine is https://booking.flyporter.com/en-ca/book-travel/book-flights-online (indexed page: "select a departure and a destination city", date DD/MM/YYYY, ≥1 passenger, transborder legs booked separately); connections from the research host timed out (HTTP/1.1 and TLS 1.2 retries) — likely geo/IP or TLS-fingerprint filtering. www.flyporter.com returns HTTP 403 "Just a moment..." (Cloudflare managed challenge, challenges.cloudflare.com CSP) to curl. No documented query parameters.
2. Sorts: none native.
3. Rendering: JS booking app (vendor not identified — Navitaire not confirmed).
4. Final price: unclear; Porter supports guest booking; not verified.
5. Luggage / fares: PorterClassic Basic, Standard, Flexible, Freedom; PorterReserve Navigate, Ultimate. Basic: "only a free personal item" on Canada/US (no carry-on; "Basic Express" add-on ~CA$50 to bring one), carry-on INCLUDED on Europe/Africa routes; Standard: carry-on all routes, checked bag extra; Flexible/Freedom: 1 checked bag included; Navigate/Ultimate: 2 bags. First checked bag (bookings on/after 2026-05-07, aggregator verified 2026-07-12): from CA$40–52 prepaid at booking, CA$45–63 post-purchase, CA$50–69 at airport. The fare picker in the booking flow shows inclusions per fare; official fare page (/en-ca/book-travel/our-fares-and-fees/our-fare-options) is Cloudflare-gated to fetchers.
6. Anti-bot: Cloudflare (cf-ray, __cf_bm, managed challenge). Cloudflare challenges are the case where patchright (Chromium) and Camoufox (Firefox) report the best pass rates in 2026 comparisons, but the booking host's behaviour is unknown.
7. robots.txt disallows booking paths (/Flight/Tickets/Book-Your-Travel, /tickets/select, /fares) and all of the site for ClaudeBot/GPTBot; ToS forbids spiders/robots.
      </detail>
      <example_url>no deep link found — entry https://booking.flyporter.com/en-ca/book-travel/book-flights-online (unreachable from probe host)</example_url>
      <selectors_or_endpoints>unknown (site not reachable from the research host); fare names "Basic|Standard|Flexible|Freedom|Navigate|Ultimate"</selectors_or_endpoints>
      <source>curl probes 2026-09-04; https://www.flyrulebook.com/airline/porter-airlines (2026-07-12); https://simpleflying.com/porter-airlines-ticket-types-guide/ (2024-10-01, fare structure); https://www.flyporter.com/en-us/terms-of-use (snippet)</source>
      <relevance>Important for YQB/YUL domestic + transborder; blocked at network level for non-browser clients; needs a headed probe from home IP before planning.</relevance>
      <confidence>medium for fare/bag rules; low for automation feasibility (unreachable)</confidence>
    </finding>

    <finding category="flair">
      <title>Flair: Cloudflare 403 block page to non-browser clients; no deep link found; a-la-carte carry-on pricing and 2026 bundle rename</title>
      <detail>
1. URL: NOT FOUND. https://www.flyflair.com/ and /booking (and /travel-info/bundles, /travel-info/baggage) return HTTP 403 "Attention Required! | Cloudflare" (a block page, not a JS challenge) to curl and to the WebFetch fetcher; booking.flyflair.com / book.flyflair.com do not resolve. Flair's PSS vendor (Navitaire New Skies suspected) was not confirmed. Search parameters unknown.
2. Sorts: none native.
3. Rendering: JS app behind Cloudflare.
4. Final price: unclear; guest booking normal for ULCC; not verified.
5. Luggage: base fare = personal item only. Carry-on (overhead bin) fee: ~CA$49–109 at booking, CA$64–114 via My Trips, CA$89–149 at online check-in, CA$99–154 at gate (varies by route/date). First checked bag: ~CA$69–119 at booking, CA$109–164 at gate. Bundles (only on flyflair.com/app, not within 3 days of departure) were renamed around Dec 2025 ("Flair FWD"): Basic (personal item only), Lite (adds carry-on), Plus (carry-on + Flair Express priority + 1 × 23 kg checked bag), Pro/"MAX" (maximum inclusions; naming differs between PAX news Dec 2025 "Basic, Lite, Plus, MAX" and 2026 aggregators "Lite, Plus, Pro" — contradiction, verify in the booking flow). One aggregator (aifly.one, 2026-08-18) claims "no bundles, a-la-carte only" — contradicted by Flair's own bundles page title "Lite Bundle" and the Zendesk "Bundles" article; treat bundles as existing. Child age: 2–12 on Flair (children under 2 = infant; US infant fee 20% of base).
6. Anti-bot: Cloudflare confirmed (server: cloudflare, cf-ray, __cf_bm, 403 block). Tolerance for a headed real-Chrome/patchright session from a residential IP is unknown but Cloudflare is the vendor most often reported as passable by patchright/Camoufox in 2026.
7. robots.txt Allow: / for generic bots (AI-training bots disallowed); ToS forbids screen-scraping/crawling.
      </detail>
      <example_url>no deep link found — entry https://www.flyflair.com/ (Cloudflare 403 to non-browser clients)</example_url>
      <selectors_or_endpoints>unknown; bundle names "Basic|Lite|Plus|Pro/MAX"; help centre https://flyflair.zendesk.com/hc/en-ca/articles/28249309016215-Bundles (403 to fetcher)</selectors_or_endpoints>
      <source>curl probes 2026-09-04; https://aifly.one/guides/flair-airlines-baggage-allowance/ (2026-08-18); https://www.paxnews.com/news/airline/flair-express-unlocks-new-benefits-carry-customers (2025-12-03); https://flyflair.zendesk.com/hc/en-ca/articles/28250715837335-Children-ages-2-to-12; https://www.flyflair.com/website-terms-conditions (snippet)</source>
      <relevance>ULCC pricing depends heavily on bag add-ons; without site access, bag prices can only be modelled as ranges.</relevance>
      <confidence>medium for pricing ranges (aggregators, mutually consistent); low for automation feasibility (blocked); contradiction on bundle names flagged</confidence>
    </finding>

    <finding category="child-age">
      <title>Child/infant age taxonomies per source and a safe default child age</title>
      <detail>
- Google Flights: passenger enum only (ADULT, CHILD, INFANT_IN_SEAT, INFANT_ON_LAP); child = 2–11, no age value.
- Kayak: path token children-{age} per child (e.g. children-8, children-8-11); lap/seat infant tokens exist in the deeplink generator (unverified names).
- Expedia: NumChild + Child1Age..ChildNAge (required); InfantInSeat=1 optional.
- Skyscanner: childrenv2=age|age, ages 2–17; adultsv2 = 18+ (per official doc); infants excluded from childrenv2.
- Air Canada: ADT (adult), YTH (youth 12–17), CHD (child 2–11), INF (lap infant &lt;2), INS (infant in seat).
- Air Transat: child 2–11 (transatlantic child discount 25%), infant 8 days–&lt;2 (10% base on transatlantic); 12+ adult fare.
- WestJet: child 2–11 (own seat), infant &lt;2; youth handled as adult on the website.
- Porter: child 2–11 full fare, 12+ adult; lap infant &lt;2 no base fare (US fees may apply).
- Flair: child 2–12 same fare as adult; infant &lt;2 lap (US: 20% of base).
Default: age 8 is a "child" in every taxonomy (2–11 / 2–12 / 2–17) and never a youth/adult; use 8 unless the pax config specifies otherwise. For ages 12–17 the sources diverge (AC YTH vs Skyscanner child vs airlines' adult) — the plan should store the actual age and map per source.
      </detail>
      <example_url>see per-source findings</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>Skyscanner referral docs; Expedia deeplink docs; AC bundle grep; airline FAQ pages (flyporter.com children-infants, flyflair.zendesk.com, experience.transat.com) via search 2026-09-04</source>
      <relevance>Determines the passenger-config → URL mapping and the idempotency key (adults, child ages).</relevance>
      <confidence>high for Google/Expedia/Skyscanner/AC codes; medium for airline age bands (FAQ snippets)</confidence>
    </finding>

    <finding category="stealth">
      <title>Free Python stealth options in 2026: patchright (Chromium) is the pragmatic default; Camoufox for Cloudflare-hard targets; playwright-stealth obsolete; nodriver/zendriver are not Playwright</title>
      <detail>
Versions (PyPI JSON, 2026-09-04): playwright 1.62.0 (2026-07-31, Python ≥3.10); patchright 1.62.3 (2026-09-02; tracks upstream within days: 1.62.1 08-17, 1.62.2 08-29); camoufox 0.5.5 (2026-08-18; 0.5.6b1 2026-09-01; Python ≥3.10 &lt;4.0; browser builds v152.0.4-beta.x on Firefox 152, latest beta.30 2025-09-01 per releases page); scrapling 0.4.15 (2026-08-23, Python ≥3.10, 78.4k stars); playwright-stealth 2.0.3 (2026-04-04); tf-playwright-stealth 1.2.0 (2025-06-13, stalled); nodriver 0.50.3 (2026-05-13); zendriver 0.16.0 (2026-08-16).
- patchright: drop-in (`from patchright.sync_api import sync_playwright` / async_api), Chromium-only. Patches Runtime.enable and Console.enable CDP leaks, removes --enable-automation, adds --disable-blink-features=AutomationControlled, runs init scripts in isolated worlds; console API is disabled as a side effect. Recommended config from README: `chromium.launch_persistent_context(user_data_dir=..., channel="chrome", headless=False, no_viewport=True)` and "do NOT add custom browser headers or user_agent". 2026 comparisons: passes standard Cloudflare/nowsecure checks; "against Akamai Bot Manager and PerimeterX, results vary by target — behavioral analysis ... still catches it on the highest-security configurations"; "nothing breaks 70% on PerimeterX with DIY approaches". Headless=True is detectable via headless-Chrome artefacts; headed under xvfb is the recommended mode on Linux/WSL2.
- Camoufox: patched Firefox (C++-level fingerprint injection via BrowserForge, humanized cursor, geoip/locale coherence). Sync/async wrappers (`from camoufox.sync_api import Camoufox`, `with Camoufox(headless=..., humanize=True, geoip=True) as browser`), `headless="virtual"` uses Xvfb automatically ("the Python library can run Camoufox in a virtual display if headless mode ever leaks"). Maintainer statement: "There has been a year gap in maintenance ... Camoufox has gone down in performance due to the base Firefox version and newly discovered fingerprint inconsistencies. Camoufox is currently under active development." README: "under development, may not be suitable for stable production use". 87 open issues, 11.7k stars. Strongest on Cloudflare (Firefox TLS treated differently), slowest.
- playwright-stealth (AtuboDad; PyPI now 2.0.x by a different maintainer): JS-level patches "transplanted from puppeteer-extra-plugin-stealth, not perfect"; 2026 sources call this class of JS hooks "obsolete" against PerimeterX/DataDome (they patch at browser-engine level and detect JS-injected overrides).
- Scrapling 0.4.x: StealthyFetcher/DynamicFetcher wrap browser engines (Playwright Chromium/real Chrome; StealthyFetcher built on a stealth Firefox/Camoufox-style engine — engine not named in current README), `solve_cloudflare=True`, `network_idle=True`, full async; useful as a batteries-included alternative but it hides the Playwright page object you need for response interception.
- nodriver/zendriver: CDP-direct (no Playwright API); nodriver's repo restricts contributions and leaves fixes unmerged, zendriver is the actively maintained fork. Not drop-in for a Playwright codebase.
- WSL2/Linux: headed browsers need an X server — use `xvfb-run -a python scraper.py` (Playwright's own error message suggests xvfb-run); WSLg on Windows 11 also provides a display. Persistent `user_data_dir` per source preserves Akamai/PX cookies across runs (improves trust).
      </detail>
      <example_url>https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python ; https://camoufox.com/python/ ; https://github.com/daijro/camoufox ; https://github.com/D4Vinci/Scrapling ; https://github.com/AtuboDad/playwright_stealth ; https://github.com/cdpdriver/zendriver</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>PyPI JSON (versions/dates); repo READMEs; https://scrapewise.ai/blogs/playwright-stealth-2026 ; https://scrapfly.io/blog/posts/best-stealth-browsers (2026); https://humanbrowser.cloud/blog/playwright-stealth-not-working-2026 ; https://bytetunnels.com/posts/nodriver-vs-zendriver-picking-right-undetected-chrome-wrapper/ ; https://github.com/microsoft/playwright/issues/26497 (xvfb message)</source>
      <relevance>Selects the browser stack for 003: patchright + real Chrome channel + persistent profile + xvfb; Camoufox as a per-source fallback for Cloudflare sites (Porter/Flair).</relevance>
      <confidence>high for versions/dates (PyPI); medium for detection claims (vendor-marketing blogs, no independent benchmark); Camoufox stability medium-low (maintainer's own warning)</confidence>
    </finding>

    <finding category="playwright-network">
      <title>Playwright Python network interception primitives (official docs)</title>
      <detail>
`page.on("response", handler)` observes every response (response.url, .status, .json()); `with page.expect_response(glob_or_predicate) as info: ...; info.value.json()` waits for a specific XHR; `page.route("**/pattern", handler)` can `route.continue_()`/`route.fulfill()`/`route.abort()` (use to block images/analytics to reduce load); `page.request` / `context.request` is an APIRequestContext that shares the browser context's cookies — it can replay JSON endpoints with the session cookies but NOT with headers the page computes (Akamai sensor, PX tokens), so prefer capturing the page's own XHR responses over replaying them. Install: `pip install playwright`, `playwright install chromium` (`--with-deps` on fresh Ubuntu/CI). Python ≥3.10 for 1.62.
      </detail>
      <example_url>https://playwright.dev/python/docs/network ; https://playwright.dev/python/docs/intro</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>Official Playwright Python docs (fetched 2026-09-04)</source>
      <relevance>The XHR-capture approach for Kayak/Skyscanner/Air Canada/WestJet rests on these APIs.</relevance>
      <confidence>high</confidence>
    </finding>

    <finding category="supabase">
      <title>supabase-py upsert with on_conflict, batch sizing, key types and RLS "public read / scraper write"</title>
      <detail>
- supabase-py 2.31.0 (2026-06-04, Python ≥3.9; postgrest 2.31.0). `supabase.table("fares").upsert(rows, on_conflict="source,route,depart_date,return_date,pax_key", ignore_duplicates=False, default_to_null=False, returning="minimal").execute()`; rows may be a list (bulk upsert). Official notes: "Primary keys must be included in the values dict to use upsert"; `on_conflict` names the columns of a UNIQUE constraint (comma-separated for composite — mirrors JS `onConflict`); `ignore_duplicates=True` → ON CONFLICT DO NOTHING; `default_to_null=False` keeps column defaults for missing fields in bulk rows. Error "there is no unique or exclusion constraint matching the ON CONFLICT specification" (42P10) means the composite UNIQUE/PK is missing — create it explicitly.
- Batch size: no hard documented upsert limit; PostgREST returns max 1,000 rows by default (project API setting) and community guidance is 100–500 rows per request; chunk upserts accordingly.
- Keys: new `sb_publishable_...` (browser-safe, honours RLS) and `sb_secret_...` (server-only; "authorize access ... through the built-in service_role Postgres role" which "skips every Row Level Security policy"; Supabase returns 401 to secret keys used from browser User-Agents). Legacy `anon`/`service_role` JWTs are "deprecating ... by the end of 2026". Scraper: secret key from env on the WSL2 host / CI secret; website: publishable key.
- RLS: `alter table public.fares enable row level security;` then `create policy "public read" on public.fares for select to anon, authenticated using (true);` — no insert/update policies needed for the scraper because service_role/secret key bypasses RLS (bypassrls). Index the policy/filter columns; for per-user policies wrap `auth.uid()` in `(select ...)`.
- Idempotency: daily runs upsert on the natural key (source, origin, destination, depart_date, return_date, adults, child_ages, cabin, variant ∈ {cheapest,fastest,best}); keep `scraped_at`/`run_id` columns for history (or a separate append-only `fare_observations` table with PK (natural key, scraped_at)).
      </detail>
      <example_url>https://supabase.com/docs/reference/python/upsert ; https://supabase.com/docs/guides/database/postgres/row-level-security ; https://supabase.com/docs/guides/api/api-keys</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>Official Supabase docs (fetched 2026-09-04); PyPI JSON; https://github.com/orgs/supabase/discussions/36532 (42P10); https://github.com/orgs/supabase/discussions/11349 (batching)</source>
      <relevance>Direct input for the schema and ingestion module in 002/003.</relevance>
      <confidence>high (official docs) except batch-size guidance (community, medium)</confidence>
    </finding>

    <finding category="scheduling">
      <title>Scheduling: home WSL2 (residential IP) beats GitHub Actions (Azure datacenter IPs) for anti-bot; keep WSL alive via Windows Task Scheduler; systemd timers or cron</title>
      <detail>
- GitHub Actions: free 2,000 min/month on private repos, unlimited on public; `playwright install chromium --with-deps` adds 30–90 s per run; scheduled workflows are "delayed by several minutes or, occasionally, dropped entirely" under load (2026 community threads report multi-hour delays) and are auto-disabled after 60 days without commits on public repos. Runners share Azure datacenter IP ranges, which Akamai/Cloudflare/PerimeterX score as high-risk ("datacenter IPs provide a significant negative trust score"). Scraping is "well within the acceptable use policy" if infrequent, but GitHub notes the target site may object. Verdict: acceptable only for Google Flights via fast-flights (HTTP), unsuitable for the airline/OTA browser flows.
- WSL2: cron and systemd timers both stop when WSL shuts down (Windows sleep, all terminals closed). Enable systemd in /etc/wsl.conf (`[boot] systemd=true`), create a Windows Task Scheduler task at logon/boot that runs `wsl.exe -d &lt;distro&gt; -- sleep infinity` (or a systemd service) to keep the VM alive, and prefer systemd timers (Persistent=true catches up missed runs after sleep; journald logs) over cron. Fix clock drift after sleep (`hwclock -s` or chrony) since fare "scraped_at" must be correct. Run headed browsers with `xvfb-run -a`.
      </detail>
      <example_url>https://github.com/orgs/community/discussions/183117 ; https://github.com/efrecon/gh-action-keepalive ; https://www.xda-developers.com/automate-windows-with-wsl-cron/ ; https://endform.dev/blog/playwright-github-actions</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>GitHub community discussions (2025–2026); Playwright CI guides (2025–2026); WSL scheduling articles (2025–2026)</source>
      <relevance>Decides where the scraper runs; residential IP is the single biggest free lever against blocks.</relevance>
      <confidence>high for Actions limits/behaviour; medium for WSL keep-alive recipe (multiple consistent blog sources, no official doc)</confidence>
    </finding>

    <finding category="best-definition">
      <title>How Google/Kayak/Skyscanner define "Best", and a proposed local scoring rule for sources without one</title>
      <detail>
- Google: "best trade-offs between price, convenience, and ease of booking", using duration, number of stops, airport changes during layovers (official). Third-party guides cite an unofficial ~40% price / 30% duration / 20% stops / 10% layover-quality weighting.
- Kayak: "Recommended/Best" = blend of price and convenience; may promote sponsored/slightly pricier options; suppresses some self-transfer itineraries.
- Skyscanner: learning-to-rank over price, total journey time, directness, plus search context (engineering blog); Best default, Cheapest/Fastest alternatives.
Proposed local rule (for airline sites and as a cross-source normaliser):
  score = 0.50 * price / min_price + 0.35 * duration / min_duration + 0.15 * stop_penalty, where stop_penalty = 1 + 0.5*stops + 0.25*(overnight or layover > 4h) + 0.25*(airport change); lowest score wins; ties → cheaper. Store variant="best" with `best_rule="local-v1"` vs "native" so the website can show provenance. Constraints: compute on the same candidate set used for cheapest/fastest (one results load), exclude self-transfer/separate-ticket itineraries (Google/Kayak "hacker fares") from "best" to match Google/Kayak behaviour.
      </detail>
      <example_url>https://support.google.com/travel/answer/7664728 ; https://medium.com/hackernoon/learning-to-rank-for-flight-itinerary-search-8594761eb867 ; https://www.going.com/guides/how-to-use-kayak-to-find-cheap-flights</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>Google help (official); Skyscanner engineering blog; Kayak guides (2026)</source>
      <relevance>Gives 002 a defensible, explainable "best" for the 5 airline sites and a cross-source comparison basis.</relevance>
      <confidence>high for definitions (official/primary); the proposed weights are an assumption to be tuned</confidence>
    </finding>

    <finding category="one-load-check">
      <title>Can cheapest/fastest/best be obtained from ONE results load per (route, date, pax)?</title>
      <detail>
- Google Flights: one load gives Best ("Top departing flights") + all other outbound options; cheapest/fastest derivable locally from the same set. Extra OTA-only fares require a second load (Cheapest tab, tfu sort=2). Round-trip totals are shown per outbound; the inbound leg requires a click (fast-flights issue #60) — store the outbound-level round-trip price + deep link, optionally resolve the return leg for "fastest" (duration of both legs) with a second load.
- Kayak: one poll session returns all itineraries with price/duration/stops; native sort order for "best" needs the sort=bestflight_a page (or the ranking field if present in the poll JSON — unverified). Cheapest/fastest derivable locally. Round-trip itineraries are complete (both legs) in one load.
- Skyscanner: one XHR gives all itineraries (both legs), price/duration/stops; "best" order only from DOM.
- Expedia: results list outbound options with round-trip "from" price; return leg needs a click → 2 loads for a complete itinerary.
- Airlines (AC/WS/TS/PD/F8): outbound page → select outbound → inbound page (round-trip pricing is combinational on AC/WestJet). Cheapest round trip = min over (outbound, inbound) combos ≈ cheapest outbound + cheapest inbound in most branded-fare engines, but not guaranteed; the plan should select the cheapest outbound, read the inbound page, and record the total; do the same for fastest (shortest outbound → shortest inbound). That is 2–3 page loads per variant per pax config.
      </detail>
      <example_url>n/a</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>Per-source findings above; fast-flights issue #60</source>
      <relevance>Directly sizes the per-run request budget (rate limits) in 002.</relevance>
      <confidence>medium — Google/Skyscanner/Kayak behaviour from docs and 2026 articles; airline combinational pricing from domain knowledge (assumption)</confidence>
    </finding>

    <finding category="locale">
      <title>.ca vs .com and fr-CA vs en-CA effects</title>
      <detail>
- Kayak: ca.kayak.com prices in CAD; kayak.com defaults to USD for US visitors (geo). Skyscanner.ca sets market=CA, currency=CAD, locale=en-CA. Expedia.ca prices CAD (`currency=CAD` param also accepted). Google: `curr=CAD&amp;gl=CA&amp;hl=en`. Air Canada: `/booking/ca/en/...` + `lang=en-CA` (fr-CA path `/booking/ca/fr/`), Transat `/en-CA/` vs `/fr-CA/`, WestJet `/en-ca/` vs `/fr-ca/`, Porter `/en-ca/` vs `/fr-ca/`, Flair `/en` vs `/fr`.
- Text-based selectors break between languages (e.g., "Best"/"Meilleurs", "Basic"/"Base", "Eco Budget"/"Éco Budget"); prefer role/aria/data-test attributes and pin English locale in the URL and in `Accept-Language: en-CA` via the browser context locale; keep currency assertions (price strings must contain "CA$" or "$" with CAD context).
      </detail>
      <example_url>see per-source</example_url>
      <selectors_or_endpoints>n/a</selectors_or_endpoints>
      <source>Probes 2026-09-04 (Skyscanner JSON, Kayak currency list), official URL docs</source>
      <relevance>Prevents mixed-currency data and locale-driven selector breakage.</relevance>
      <confidence>high for URL/locale mechanics; medium for Kayak geo default</confidence>
    </finding>

  </findings>

  <recommendations>
    <recommendation priority="high"><action>Build the scraper on Google Flights only (per re-scope): Playwright headless Chromium, one `tfs` deep link per (route, dates, pax), read Best from the default load ("Top departing flights" group), Cheapest via `&amp;tfu=EgoIABAAGAAgAigB`, Fastest via `&amp;tfu=EgYIBRAAGAA` (or local sort of the Best load by total duration), then click the chosen outbound + return to reach `/travel/flights/booking?tfs=…` and read per-provider totals and the bag text.</action><rationale>Live-verified today: every required field (total incl. taxes for the pax config, carry-on inclusion, 1st-bag fee range, deep link, Google's low/typical/high insight) is on those pages without login; no anti-bot challenge for headless Chromium from the home IP.</rationale></recommendation>
    <recommendation priority="high"><action>Parse rows from the first `[aria-label]` of each `li.pIav2d` (price "From N Canadian dollars round trip total", stops, carriers, times, "Total duration"), not from obfuscated class names or heading text; wait until the "Other departing flights" group or the "more flights" button is present (or the 3rd GetShoppingResults response) before reading, and click "more flights" to get the full list.</action><rationale>Headings change by locale and route ("Top departing options"); rows stream in over ~2–4 s and early reads returned 2–4 rows for the same query that later showed 18–26.</rationale></recommendation>
    <recommendation priority="high"><action>Use `faster-flights` (or `fast-flights`) ONLY as the `tfs` builder (`create_query(...).params()["tfs"]`, `Passengers(adults, children, infants_in_seat, infants_on_lap)`, `max_stops`, `carry_on_bags`, `exclude_basic_economy`), optionally as an adult-only fast pre-check via `get_flights(q, shopping=ShoppingOptions("best","top_flights"))`; do not use either library's data path for searches with children or for the return leg.</action><rationale>fast-flights 3.1.0 returns one "lure" itinerary and has a broken dependency; faster-flights' RPC path returns the single SSR result whenever a child is present and its round-trip step is broken (issue #3), plus it depends on a hard-coded March-2026 build label (issue #4).</rationale></recommendation>
    <recommendation priority="high"><action>Store for each (source=google, origin, destination, depart_date, return_date, adults, child_ages, cabin, variant∈{best,cheapest,fastest}): total price CAD for all pax from the results row, booking-page airline total and cheapest-OTA total, carry_on_included (from "free carry-on"/"No carry-on" text), first_checked_bag_fee_min/max (from "1st checked bag per passenger: CA$150–170"), duration_min, stops, carriers, Google price-insight level, results deep link and booking deep link (`booking?tfs=…`).</action><rationale>Matches the Supabase schema goal (cheapest/fastest/best per source/route/date/pax with final price + luggage + deep link); all fields were observed on the pages.</rationale></recommendation>
    <recommendation priority="medium"><action>Run from the home WSL2 box (residential IP) on a systemd timer with `xvfb-run` only if switching to headed mode; keep volume human-paced (2–4 s between page loads, a few routes × dates per run, jittered schedule) and add a circuit breaker on 429 / "unusual traffic" pages; keep patchright + persistent profile ready as a drop-in if Google starts challenging.</action><rationale>robots.txt disallows the search path and Google's ToS keys off robots.txt; Google's defence is WAF + rate limiting, which low residential volume did not trigger today.</rationale></recommendation>
    <recommendation priority="medium"><action>Default child age 8 in the pax config but note Google encodes only CHILD (2–11) — store the ages for provenance; treat infants as a separate pax config because they change the candidate set.</action><rationale>Google's `tfs` PassengerType has no age; 2A+1C+1 lap infant produced a different, tiny result set.</rationale></recommendation>
    <recommendation priority="medium"><action>Supabase: table `fares` with UNIQUE(source, origin, destination, depart_date, return_date, adults, child_ages, cabin, variant); chunked upsert (≤500) with `on_conflict` on that key using the `sb_secret_` key; RLS enabled with `select … to anon using (true)`; website reads with `sb_publishable_`.</action><rationale>Official supabase-py/RLS/key guidance; legacy JWT keys deprecate end-2026.</rationale></recommendation>
    <recommendation priority="low"><action>Pin `hl=en-US&amp;curr=CAD&amp;gl=CA` and browser locale en-CA; keep fr-CA out of scope for selectors (aria text differs: "Aller-retour à partir de 2173 dollars canadiens (total)").</action><rationale>Observed locale differences in headings, tabs and aria-labels.</rationale></recommendation>
    <recommendation priority="low"><action>Optional later: intercept `GetShoppingResults`/`GetBookingResults` JSON (batchexecute) instead of DOM parsing, using faster-flights' parser/index map (top/other groups, amenity flags [9]=checked bag) — only after the DOM path is stable.</action><rationale>JSON is richer (amenity flags, per-airline baggage URLs) but its structure is undocumented by Google and shifts; DOM aria-labels are human-facing and more stable.</rationale></recommendation>
    <recommendation priority="low"><action>Appendix sources (Kayak, Skyscanner, Expedia, Air Canada, Transat, WestJet, Porter, Flair) are out of scope per the re-scope; if ever revisited, see their findings (Kayak/Skyscanner PerimeterX, Expedia/AC Akamai, Transat Imperva, Porter/Flair Cloudflare; no public deep links for the four non-AC carriers).</action><rationale>Kept for reference only.</rationale></recommendation>
  </recommendations>

  <code_examples>
```python
# --- Google Flights end-to-end (LIVE-VERIFIED 2026-09-04): tfs builder + headless Playwright + booking page
from playwright.sync_api import sync_playwright
from fast_flights import FlightQuery, Passengers, create_query   # from `pip install faster-flights` (or fast-flights + typing_extensions)
import re

TFU = {"best": None, "cheapest": "EgoIABAAGAAgAigB", "fastest": "EgYIBRAAGAA"}   # tfu = TfuState{search_mode=CHEAPEST} / {sort=DURATION}

def google_url(o, d, dep, ret, adults, children, infants_on_lap=0, variant="best"):
    q = create_query(flights=[FlightQuery(date=dep, from_airport=o, to_airport=d),
                              FlightQuery(date=ret, from_airport=d, to_airport=o)],
                     trip="round-trip", seat="economy",
                     passengers=Passengers(adults=adults, children=children, infants_on_lap=infants_on_lap),
                     language="en-US", currency="CAD")
    url = f"https://www.google.com/travel/flights/search?tfs={q.params()['tfs']}&hl=en-US&curr=CAD&gl=CA"
    return url + (f"&tfu={TFU[variant]}" if TFU[variant] else "")

ROW_RE = re.compile(r"From (\d+) Canadian dollars round trip total\. (Nonstop|\d+ stops?) flight with (.+?)\. Leaves .*?Total duration (\d+) hr(?: (\d+) min)?", re.S)

def read_rows(page):
    page.wait_for_selector("li.pIav2d", timeout=45000)
    # results stream in: wait for the second group (or the expander) before reading
    page.wait_for_selector("text=/Other departing|more flights/", timeout=20000)
    more = page.get_by_role("button", name=re.compile("more flights"))
    if more.count(): more.first.click(); page.wait_for_timeout(2500)
    out = []
    rows = page.locator("li.pIav2d")
    for i in range(rows.count()):
        al = rows.nth(i).locator("[aria-label]").first.get_attribute("aria-label") or ""
        m = ROW_RE.search(al)
        if m:
            out.append(dict(price_cad=int(m.group(1)), stops=0 if m.group(2)=="Nonstop" else int(m.group(2).split()[0]),
                            carriers=m.group(3), duration_min=int(m.group(4))*60+int(m.group(5) or 0), aria=al, idx=i))
    return out

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(locale="en-CA", timezone_id="America/Toronto")
    page = ctx.new_page()
    page.goto(google_url("YUL","CDG","2026-10-15","2026-10-22",2,1,variant="best"), wait_until="domcontentloaded")
    best_rows = read_rows(page)             # rows[0] is Google's #1 "Top departing flight"
    cheapest = min(best_rows, key=lambda r: r["price_cad"])
    fastest  = min(best_rows, key=lambda r: r["duration_min"])
    # booking page for the best itinerary: click outbound, then the first return
    page.locator("li.pIav2d").nth(best_rows[0]["idx"]).click(); page.wait_for_selector("li.pIav2d"); page.wait_for_timeout(3000)
    page.locator("li.pIav2d").first.click(); page.wait_for_url(re.compile(r"/travel/flights/booking")); page.wait_for_timeout(5000)
    body = page.locator("body").inner_text()
    booking_link = page.url                                   # stable deep link to the selected itinerary
    providers = re.findall(r"Book with (.+?)\n(?:Airline\n)?CA\$([\d,]+)", body)   # [('Air Transat', '2,173'), ('FlightHub', '2,254'), ...]
    bag = re.search(r"1st checked bag per passenger: CA\$(\d+)(?:–(\d+))?", body)
    carry_on = "free carry-on" in body.lower()
    print(providers[:3], bag.groups() if bag else None, carry_on, booking_link[:80])
    ctx.close(); b.close()
```

```python
# --- faster-flights 3.8.0 adult-only fast path (HTTP RPC, ~0.5 s) — NOT for searches with children (falls back to 1 SSR row)
from fast_flights import FlightQuery, Passengers, create_query, get_flights, ShoppingOptions
q = create_query(flights=[FlightQuery(date="2026-10-15", from_airport="YUL", to_airport="CDG"),
                          FlightQuery(date="2026-10-22", from_airport="CDG", to_airport="YUL")],
                 trip="round-trip", passengers=Passengers(adults=2), language="en-US", currency="CAD")
res = get_flights(q, shopping=ShoppingOptions(ranking_mode="best", result_sort="top_flights"))
print(res.diagnostics, res.metadata.shopping.groups)      # groups: top=[0,1,2], other=[3..]
for f in res: print(f.rank, f.group_key, f.price, f.airlines, sum(s.duration for s in f.flights))   # price = total for the requested passengers
```

```python
# --- Google Flights via fast-flights 3.1.0 (2026-08-18) — signature per README (verify names against installed version)
from fast_flights import FlightQuery, Passengers, create_query, get_flights

q = create_query(
    [FlightQuery(date="2026-10-15", from_airport="YUL", to_airport="CDG", max_stops=1),
     FlightQuery(date="2026-10-22", from_airport="CDG", to_airport="YUL", max_stops=1)],
    trip="round-trip", seat="economy",
    passengers=Passengers(adults=2, children=1, infants_in_seat=0, infants_on_lap=0),  # no child ages in Google's protobuf
    currency="CAD",
)
result = get_flights(q)          # optional: fetch_mode="fallback" uses a hosted Playwright endpoint (issue #109: 401s seen on v2.2)
for f in result.flights:
    print(f.is_best, f.name, f.price, f.duration, f.stops, f.departure, f.arrival)
# Deep link for the same search (tfs built by fast-flights): 
url = f"https://www.google.com/travel/flights/search?tfs={q.tfs}&hl=en&gl=CA&curr=CAD"   # attribute name may differ; see fast_flights.filter
```

```python
# --- Kayak / Skyscanner / Expedia / Air Canada URL builders (children ages list e.g. [8])
def kayak_url(o, d, dep, ret, adults, child_ages, sort="bestflight_a"):
    pax = f"/{adults}adults" + (("/children-" + "-".join(map(str, child_ages))) if child_ages else "")
    return f"https://www.ca.kayak.com/flights/{o}-{d}/{dep}/{ret}{pax}?sort={sort}"   # price_a | duration_a

def skyscanner_url(o, d, dep, ret, adults, child_ages, sortby=None):
    yymmdd = lambda s: s[2:4] + s[5:7] + s[8:10]
    u = (f"https://www.skyscanner.ca/transport/flights/{o.lower()}/{d.lower()}/{yymmdd(dep)}/{yymmdd(ret)}/"
         f"?adultsv2={adults}&cabinclass=economy&rtn=1&preferdirects=false&market=CA&locale=en-CA&currency=CAD")
    if child_ages: u += "&childrenv2=" + "%7C".join(map(str, child_ages))   # ages 2–17
    if sortby: u += f"&sortby={sortby}"                                       # cheapest | fastest
    return u

def expedia_url(o, d, dep, ret, adults, child_ages):
    u = (f"https://www.expedia.ca/go/flight/search/Roundtrip/{dep}/{ret}"
         f"?FromAirport={o}&ToAirport={d}&NumAdult={adults}&Class=3&currency=CAD")
    if child_ages:
        u += f"&NumChild={len(child_ages)}" + "".join(f"&Child{i+1}Age={a}" for i, a in enumerate(child_ages))
    return u

def aircanada_url(o, d, dep, ret, adults, child_ages, market="INT", lang="en"):
    chd = sum(1 for a in child_ages if 2 <= a <= 11); yth = sum(1 for a in child_ages if 12 <= a <= 17)
    return (f"https://www.aircanada.com/booking/ca/{lang}/aco/availability/rt/outbound"
            f"?org0={o}&dest0={d}&departureDate0={dep}&org1={d}&dest1={o}&departureDate1={ret}"
            f"&ADT={adults}&YTH={yth}&CHD={chd}&INF=0&INS=0&lang={lang}-CA&tripType=R&marketCode={market}")
# WestJet / Air Transat / Porter / Flair: no confirmed deep link — drive the search form (see findings).
```

```python
# --- patchright launch (README-recommended stealth config) + response capture
from patchright.sync_api import sync_playwright   # drop-in for playwright.sync_api; Chromium only
import json

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir="./profiles/aircanada",   # persist Akamai/PX cookies between runs
        channel="chrome",                        # real Google Chrome, not bundled Chromium
        headless=False,                          # run under: xvfb-run -a python scraper.py
        no_viewport=True,
        locale="en-CA", timezone_id="America/Toronto",
        # do NOT set user_agent / extra headers (patchright README)
    )
    page = ctx.new_page()
    captured = []
    page.on("response", lambda r: captured.append(r) if "/graphql" in r.url and r.status == 200 else None)
    page.goto(aircanada_url("YUL", "CDG", "2026-10-15", "2026-10-22", 2, [8]), wait_until="domcontentloaded")
    page.wait_for_timeout(8000)                  # or wait for a results locator
    for r in captured:
        try:
            body = r.json()
        except Exception:
            continue
        if "data" in body:                       # inspect operationName / shape on first run
            print(r.url, json.dumps(body)[:300])
    ctx.close()
```

```python
# --- Kayak poll capture with expect_response
with page.expect_response(lambda r: "/i/api/search/dynamic/flights/poll" in r.url and r.status == 200, timeout=60000) as info:
    page.goto(kayak_url("YUL", "CDG", "2026-10-15", "2026-10-22", 2, [8]))
poll = info.value.json()     # iterate until poll["status"] indicates completion; re-capture subsequent poll responses
```

```python
# --- supabase-py 2.31.0 upsert with composite on_conflict, chunked
import os
from supabase import create_client
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])   # sb_secret_... (server-side only)

KEY = "source,origin,destination,depart_date,return_date,adults,child_ages,cabin,variant"
def upsert_fares(rows, chunk=500):
    for i in range(0, len(rows), chunk):
        sb.table("fares").upsert(rows[i:i+chunk], on_conflict=KEY, returning="minimal").execute()
```

```sql
-- Supabase schema + RLS: public read-only, scraper writes with secret key (bypasses RLS)
create table public.fares (
  id bigint generated always as identity primary key,
  source text not null, origin text not null, destination text not null,
  depart_date date not null, return_date date not null,
  adults int not null, child_ages text not null default '',      -- e.g. '8' or '8,11'
  cabin text not null default 'economy',
  variant text not null check (variant in ('cheapest','fastest','best')),
  price_total numeric(10,2) not null, currency text not null default 'CAD',
  price_stage text not null,            -- 'results' | 'fare_selected' | 'review'
  carry_on_included boolean, first_checked_bag_fee numeric(10,2), bag_fee_source text,
  duration_min int, stops int, airline text, fare_family text, deep_link text,
  best_rule text, scraped_at timestamptz not null default now(),
  unique (source, origin, destination, depart_date, return_date, adults, child_ages, cabin, variant)
);
alter table public.fares enable row level security;
create policy "public read fares" on public.fares for select to anon, authenticated using (true);
-- no insert/update policy: the scraper uses the secret key (service_role, bypassrls)
```

```ini
# --- systemd timer on WSL2 (requires [boot] systemd=true in /etc/wsl.conf and a Windows Task Scheduler keep-alive)
# /etc/systemd/system/flight-scraper.service
[Service]
Type=oneshot
WorkingDirectory=/home/jfontaine/Projects/flight-scraper
EnvironmentFile=/home/jfontaine/Projects/flight-scraper/.env
ExecStart=/usr/bin/xvfb-run -a /home/jfontaine/Projects/flight-scraper/.venv/bin/python -m scraper run
# /etc/systemd/system/flight-scraper.timer
[Timer]
OnCalendar=*-*-* 06:30:00
Persistent=true
RandomizedDelaySec=20m
[Install]
WantedBy=timers.target
```
  </code_examples>

  <metadata>
    <confidence level="high for Google Flights (live-executed end-to-end in a headless browser today); medium-high for the appendix sources (probes + official docs, no browser runs)">Google Flights: URL, tabs/sort states, row parsing, booking-page totals and bag text, RPC names and library behaviour were all observed by running Playwright and both libraries from the user's host on 2026-09-04. Appendix sources: URL formats/vendors verified by curl probes or official docs for 7/9; WestJet/Transat/Porter/Flair deep links not found; their checkout flows were not exercised.</confidence>
    <dependencies>
      - Python ≥3.10; playwright 1.62.0 (2026-07-31) + `playwright install chromium` (chromium-headless-shell 151); faster-flights 3.8.0 (2026-07-09) or fast-flights 3.1.0 (2026-08-18, needs `typing_extensions`) as tfs builder only; patchright 1.62.3 (2026-09-02) optional insurance; supabase 2.31.0 (2026-06-04)
      - System: Google Chrome (channel="chrome") or `patchright install chromium`; xvfb (`apt install xvfb`); systemd enabled in WSL2; Windows Task Scheduler keep-alive
      - Supabase project with new-style keys (sb_publishable_/sb_secret_); UNIQUE composite key on fares
      - Residential IP (home WSL2); GitHub Actions only for the HTTP-only Google job
    </dependencies>
    <open_questions>
      - GOOGLE: how long do `li.pIav2d` / aria-label phrasing stay stable? (add a smoke test that asserts ≥1 parsed row per run and alerts on 0)
      - GOOGLE: is the booking-page bag text present for all carriers (observed for a Transat/Porter itinerary: "1 free carry-on", "1st checked bag per passenger: CA$150–170"); what does it say for AC Basic ("No carry-on"?) and for OTA options?
      - GOOGLE: does the checked-bag filter appear for domestic/transborder routes (only carry-on stepper on YUL→CDG)?
      - GOOGLE: what daily volume from the home IP triggers 429 (today ~30 requests in 15 min were fine)?
      - GOOGLE: will `tfu` constants (EgoIABAAGAAgAigB / EgYIBRAAGAA) remain valid across Google front-end builds?
      - faster-flights: will #3 (return leg) and #4 (BotGuard) be fixed, and will the RPC path accept children?
      - Does Air Canada's Akamai profile tolerate 2–6 headed patchright sessions/day from the home IP? (needs a live probe)
      - Exact WestJet /shop query-string contract (record on first Playwright run) and whether the shop XHR is protected.
      - Air Transat results URL parameters and whether child ages are in the query string or POST body.
      - Are booking.flyporter.com and flyflair.com reachable with a real headed Chrome from the home IP? (curl was blocked/unreachable)
      - Is fast-flights 3.1.0's is_best parsing fixed (issue #101 open, no reply)? Does the Cheapest tab need a browser?
      - Google bag-fee filter coverage for AC/WS/TS/PD/F8 (not published).
      - Kayak poll JSON: does it contain Kayak's "best" ranking score, and what is the Fee Assistant URL state?
      - Expedia current sort query parameter (none documented; "options=sortby:price" seen on Expedia-owned links).
      - Is reaching airline review pages with dummy passenger data acceptable to the user (ethics/ToS)? Decide in 002.
      - Air Canada marketCode semantics (DOM/TNB/INT assumed).
    </open_questions>
    <assumptions>
      - Google results-row price ("round trip total") equals the booking-page airline total for the same itinerary (observed equal: CA$2,173 both places, one sample).
      - The "Continue" handoff URL from Google to the airline was not followed; the booking-page total is treated as the "final price" proxy (bags/seats extra).
      - Low volume (a few routes × a few dates × 1–2 pax configs, once or twice daily) — every tolerance statement assumes this.
      - Aggregator bag-fee tables (deeparrival, aifly.one, flyrulebook, upgradedpoints) reflect 2026 official pricing; official pages were JS-rendered or Cloudflare-gated to the fetcher.
      - Airline round-trip cheapest ≈ cheapest outbound + cheapest inbound on branded-fare engines (not guaranteed).
      - The proposed "best" weights (0.50/0.35/0.15) are a starting point, not derived from any site's algorithm.
      - Kayak vendor: PerimeterX/HUMAN per multiple 2026 sources; Akamai per one source; probe inconclusive.
    </assumptions>
    <quality_report>
      <sources_consulted>~120 fetches/searches + 6 local Playwright runs and 6 library executions: 9 robots.txt; official docs (Playwright ×2, Supabase ×3+JS ref, Skyscanner referral params, Expedia deeplinks, Google Travel help ×2, Google ToS, Kayak ToS, Air Canada ToS + carry-on page, WestJet our-fares); repos/PyPI (fast-flights README/issues/PyPI, patchright, camoufox + releases + stealth page, Scrapling, playwright_stealth, zendriver/nodriver, postgrest-py); 2026 articles (Scrapfly Kayak 2026-07-27, Scrapfly Skyscanner 2026-08-14, themenonlab 2026-08-09, Zenrows/Scrapewise/humanbrowser/bytetunnels stealth comparisons, marsproxies Expedia, Scraperly Kayak 2026-04); direct curl/HTML/JS probes of all 9 sites plus AC and WestJet app bundles (2026-09-04); fare/bag aggregators dated 2026 (deeparrival, aifly.one, flyrulebook, upgradedpoints, PAX news, CBC).</sources_consulted>
      <claims_verified>GOOGLE (executed): tfs deep link loads in CAD with 2A+1C; Top/Other grouping; Cheapest/Duration tfu values; row aria-label format; booking page totals incl. taxes for 3 pax and bag text; GetShoppingResults/GetBookingResults RPC names and f.req passenger array; fast-flights 3.1.0 import failure and 1-row result; faster-flights rpc-first counts/prices by pax and child fallback; no captcha in 11 loads. Appendix: robots.txt lines (all 9); protection vendors for Expedia (Akamai, 429), Air Canada (Akamai), Skyscanner (PerimeterX _pxhd), Transat (Imperva), Porter/Flair (Cloudflare), Google (none) — by response headers/cookies; Kayak/Skyscanner/Expedia/Air Canada deep-link formats (200 responses + official docs + bundle param names); AC GraphQL endpoint hosts; WestJet shop state keys; library versions/dates (PyPI JSON); Supabase upsert/RLS/key semantics (official docs); Google Best/Cheapest definitions and tfs/tfu structure (help page + community spec); fast-flights open issues; WestJet fare table (official); AC Basic carry-on rule (official).</claims_verified>
      <claims_assumed>Checkout/review reachability for every source (not automated here); headed-browser tolerance per vendor (from vendor blogs, not tested); bag fee amounts (aggregators); Kayak vendor identity; Kayak infant tokens; AC marketCode values; Expedia sort params; Transat/WestJet/Porter/Flair search URL contracts; Flair bundle naming (Pro vs MAX); local "best" weights.</claims_assumed>
      <contradictions_encountered>Expedia vendor: DataDome (marsproxies 2026) vs Akamai (our probe) → Akamai. Kayak vendor: PerimeterX/HUMAN (Zenrows/Scrapfly/ScrapingBee 2026) vs Akamai (Scraperly 2026) → unresolved, flagged. Flair bundles: "Basic/Lite/Plus/MAX" (PAX 2025-12) vs "Lite/Plus/Pro" (2026 aggregators) vs "no bundles" (aifly.one) → bundles exist, tier names unverified. AC fee change dates: 2026-04-13 (NA) and 2026-05-14 (international) cited by different aggregators → both kept. patchright/playwright release dates: GitHub release pages parsed as 2024 by the fetcher vs PyPI upload times 2026 → PyPI used. Camoufox: PyPI wrapper active (0.5.5, 2026-08) vs browser builds last 2025-09 and maintainer's "year gap" note → reported both.</contradictions_encountered>
      <confidence_by_finding>robots: high; ToS: high/medium; Google: high (medium on is_best/bag coverage); Kayak: high URL / medium XHR+vendor; Expedia: high URL+Akamai / low checkout+sort; Skyscanner: high; Air Canada: high URL+vendor / medium fares / low review-page; Transat: medium; WestJet: medium; Porter: medium fares / low access; Flair: medium fares / low access; child-age: high/medium; stealth: high versions / medium detection; playwright-network: high; supabase: high; scheduling: high/medium; best-definition: high definitions / assumption on weights; one-load: medium; locale: high.</confidence_by_finding>
    </quality_report>
  </metadata>
</research>
