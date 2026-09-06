"""Google Flights adapter — the one live source in v1.

Flow per search (≤ 9 page loads, counted exactly: 1 per goto, 1 per outbound click, 1 per return click)::

    default load  (Best = row 0)            → booking visit for BEST      (outbound click + return click)
    Cheapest tab  (tfu=EgoIABAAGAAgAigB)    → booking visit for CHEAPEST  (skipped when already visited)
    Duration sort (tfu=EgYIBRAAGAA)         → booking visit for FASTEST   (idem)

The booking visit is done straight from the load the pick came from (no extra navigation), which is
what keeps the plan's 9-load ceiling honest. ``search()`` alone (the generic contract) does the three
loads without booking visits; ``enrich_luggage()`` re-navigates to the pick's load when needed.
Every transition runs ``check_block``; a block raises ``BlockedError`` — never interact with a captcha.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ...models import Itinerary, Leg, Pick, PriceStage, SearchQuery, SearchResult
from ..base import BaseAdapter, BlockedError, NoResultsParsed
from .parse_booking import BookingInfo, parse_booking_text
from .parse_results import (
    ROW_SELECTOR,
    RpcCounter,
    parse_row_aria,
    read_rows,
    row_labels,
    rows_to_itineraries,
)
from .tfs import booking_flight_numbers, build_search_url, rewrite_passengers

log = logging.getLogger(__name__)

LOADS: list[tuple[Pick | None, str, Pick]] = [
    (None, "best_load", Pick.BEST),
    (Pick.CHEAPEST, "cheapest_load", Pick.CHEAPEST),
    (Pick.FASTEST, "duration_load", Pick.FASTEST),
]
LOAD_FIXTURE_NAME = {"best_load": "best", "cheapest_load": "cheapest", "duration_load": "duration"}
BOOKING_URL_RE = re.compile(r"/travel/flights/booking")
LUGGAGE_SOURCE = "google_booking_page"


def _flight_numbers_from_url(url: str) -> list[str]:
    """The booking page prints no flight numbers, but its tfs carries carrier + number per segment."""
    from urllib.parse import parse_qs, urlparse

    try:
        tfs = parse_qs(urlparse(url).query).get("tfs", [""])[0]
    except ValueError:
        return []
    return booking_flight_numbers(tfs) if tfs else []


def _strip_html(html: str) -> str:
    """Fixture HTML without scripts/styles (keeps the DOM structure, drops ~80% of the bytes)."""
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    return re.sub(r'\s(?:nonce|jsdata|data-ved|ved|jscontroller|jsaction)="[^"]*"', "", html)


class GoogleFlightsAdapter(BaseAdapter):
    source_id = "google_flights"
    name = "Google Flights"
    kind = "meta"
    enabled = True
    priority = 1
    disabled_reason = None
    native_picks = frozenset({Pick.BEST, Pick.CHEAPEST, Pick.FASTEST})
    default_price_stage = "booking"

    def __init__(self, *args: Any, capture_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.capture_dir = capture_dir  # set by `cli capture`: write sanitised fixtures here
        self._current_labels: list[str] = []
        self._rpc: RpcCounter | None = None
        self._rpc_page: Any = None
        self.capture_rpc = False  # --capture-rpc: record GetShoppingResults bodies + DOM cross-check
        self._recorder: Any = None
        self.rpc_reports: list[dict[str, Any]] = []
        # lever D experiment (--experimental-pax-derive): (key, adults, children) configs to derive
        self.pax_derive_configs: list[tuple[str, int, int]] = []

    # ---- pure -------------------------------------------------------------------------------
    def build_url(self, query: SearchQuery, variant: Pick | None = None) -> str:
        return build_search_url(query, variant)

    # ---- helpers ----------------------------------------------------------------------------
    def _consume(self, n: int = 1) -> None:
        if self.budget is not None:
            self.budget.consume(n)

    def _sleep(self, kind: str) -> None:
        if self.sleep is not None:
            getattr(self.sleep, kind)()

    def _capture(self, name: str, content: str) -> None:
        if self.capture_dir is None:
            return
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        if name.endswith(".html"):  # full pages are 1-2 MB even without scripts: keep them gzipped
            import gzip

            with gzip.open(self.capture_dir / (name + ".gz"), "wt", encoding="utf-8") as fh:
                fh.write(content)
            return
        (self.capture_dir / name).write_text(content, encoding="utf-8")

    def _rpc_for(self, page: Any) -> RpcCounter:
        if self._rpc is None or self._rpc_page is not page:
            self._rpc, self._rpc_page = RpcCounter(page), page
            if self.capture_rpc:
                from .rpc import RpcRecorder

                self._recorder = RpcRecorder(page)
        return self._rpc

    def _rpc_cross_check(self, tag: str, cands: list[Itinerary]) -> None:
        if self._recorder is None:
            return
        from .rpc import RpcRecorder, cross_check

        bodies = self._recorder.take("GetShoppingResults")
        report = cross_check(bodies, [c.price_results_cad for c in cands if c.price_results_cad])
        report["load"] = tag
        self.rpc_reports.append(report)
        log.info("rpc cross-check %s: %s", tag, report)
        root = getattr(self.artifacts, "root", None)
        run_id = getattr(self.artifacts, "run_id", None)
        if root is not None and run_id is not None:
            RpcRecorder.save(Path(root) / run_id / "rpc" / (self.current_search_key or "search"), tag, bodies)

    def _read_rows(self, page: Any, *, min_rpc: int = 2) -> list[str]:
        return read_rows(
            page,
            sleep_actions=lambda: self._sleep("between_actions"),
            rpc=self._rpc_for(page),
            min_rpc=min_rpc,
        )

    def _goto(self, page: Any, url: str) -> None:
        self._consume(1)
        self._rpc_for(page).reset()
        response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        from ...browser import check_block  # local: keep Playwright out of import-time paths

        check_block(page, response)

    def _check(self, page: Any) -> None:
        from ...browser import check_block

        check_block(page)

    def _artifacts(self, page: Any, reason: str) -> None:
        try:
            self.artifacts.save(page, self.current_search_key or "search", reason)
        except Exception as exc:  # noqa: BLE001 - artifacts never mask the real error
            log.warning("artifact save failed: %s", exc)

    # ---- results loads ----------------------------------------------------------------------
    def _load_results(self, page: Any, query: SearchQuery, variant: Pick | None, tag: str) -> list[Itinerary]:
        url = self.build_url(query, variant)
        log.info("load %s %s", tag, url[:110])
        self._goto(page, url)
        try:
            labels = self._read_rows(page)
        except Exception as exc:  # noqa: BLE001 - a block can surface as a timeout on the row selector
            self._check(page)
            self._artifacts(page, f"no rows: {type(exc).__name__}: {exc}")
            raise NoResultsParsed(f"no_results_parsed ({tag}: {type(exc).__name__})") from exc
        self._check(page)
        self._current_labels = labels
        fixture = LOAD_FIXTURE_NAME[tag]
        self._capture(f"{fixture}_rows.json", json.dumps(labels, indent=2, ensure_ascii=False))
        if self.capture_dir is not None:
            self._capture(f"results_{fixture}.html", _strip_html(page.content()))
        cands, unparsed = rows_to_itineraries(labels, query, tag, url)
        if unparsed:
            log.warning("%s: %d/%d rows did not parse", tag, len(unparsed), len(labels))
        if not cands:
            self._artifacts(page, f"no_results_parsed ({tag}, {len(labels)} rows)")
            raise NoResultsParsed(f"no_results_parsed ({tag}: {len(labels)} rows, 0 parsed)")
        for c in cands:
            if unparsed:
                c.raw["unparsed"] = unparsed
        self._rpc_cross_check(tag, cands)
        return cands

    def search(self, page: Any, query: SearchQuery) -> list[Itinerary]:
        """Generic contract: the three results loads, no booking visits (3 page loads)."""
        self.current_search_key = query.search_key
        out: list[Itinerary] = []
        for i, (variant, tag, _pick) in enumerate(LOADS):
            if i:
                self._sleep("between_loads")
            out.extend(self._load_results(page, query, variant, tag))
        return out

    # ---- booking visit ----------------------------------------------------------------------
    FASTEST_RETURN_TOLERANCE_MIN = 10

    @classmethod
    def _choose_return(cls, rows: list[Itinerary], pick: Pick) -> Itinerary:
        if pick is Pick.CHEAPEST:
            return min(rows, key=lambda r: (r.price_results_cad or 1e9, r.duration_min or 10**6))
        if pick is Pick.FASTEST:
            # shortest return, but a flight within 10 min of the shortest is "as fast": take the cheapest
            # of those (observed YQB-YYZ: the 1-minute-shorter return cost CA$1,758 vs CA$562)
            shortest = min(r.duration_min or 10**6 for r in rows)
            pool = [
                r for r in rows if (r.duration_min or 10**6) <= shortest + cls.FASTEST_RETURN_TOLERANCE_MIN
            ]
            return min(pool, key=lambda r: (r.price_results_cad or 1e9, r.duration_min or 10**6))
        return rows[0]  # BEST → Google's first returning row

    def _click_row(self, page: Any, label: str, index: int) -> None:
        """Click the row whose aria-label matches (falls back to the index); counts one page load."""
        rows = page.locator(ROW_SELECTOR)
        target = None
        current = row_labels(page)
        if label in current:
            target = rows.nth(current.index(label))
        elif index < len(current):
            target = rows.nth(index)
        if target is None:
            raise NoResultsParsed("row to click disappeared")
        self._consume(1)
        # The labelled div (div[role=link]) is an empty accessibility overlay that Playwright refuses to
        # click (siblings intercept pointer events). Click the visible departure-times span instead —
        # the click bubbles up to Google's row handler — and fall back to a forced click on the row.
        times = target.locator('[aria-label^="Leaves"]').first
        try:
            times.click(timeout=10_000)
        except Exception as exc:  # noqa: BLE001
            log.debug("times click failed (%s); forcing a click on the row", type(exc).__name__)
            target.click(timeout=10_000, force=True)

    def _wait_return_list(self, page: Any, origin_airport: str | None) -> list[str]:
        """Returning rows fly back to the origin: wait until the first row's sentence says so."""
        marker = f"arrives at {origin_airport}" if origin_airport else "Leaves"
        rpc = self._rpc_for(page)
        before = rpc.shopping
        page.wait_for_function(
            """([sel, marker]) => {
                const li = document.querySelector(sel);
                if (!li) return false;
                const el = li.querySelector('[aria-label]');
                return !!el && (el.getAttribute('aria-label') || '').includes(marker);
            }""",
            arg=[ROW_SELECTOR, marker],
            timeout=30_000,
        )
        rpc.wait_for("shopping", before + 1, 10.0)
        return self._read_rows(page, min_rpc=0)

    def _visit_booking(self, page: Any, query: SearchQuery, it: Itinerary, pick: Pick) -> Itinerary:
        """Page is on the load ``it`` came from: click outbound → return → booking page, parse, fill."""
        it = it.model_copy(deep=True)
        self._sleep("between_actions")
        self._click_row(page, it.outbound.aria_label or "", it.row_index)
        try:
            return_labels = self._wait_return_list(page, it.raw.get("depart_airport"))
        except Exception as exc:  # noqa: BLE001
            self._check(page)
            self._artifacts(page, f"returning list not rendered: {exc}")
            it.raw["booking_error"] = f"returning list: {type(exc).__name__}: {exc}"
            return it
        self._check(page)
        self._capture(
            f"returning_{pick.value}_rows.json", json.dumps(return_labels, indent=2, ensure_ascii=False)
        )
        rows, _unparsed = rows_to_itineraries(return_labels, query, "return_list", page.url)
        if not rows:
            self._artifacts(page, "returning list parsed 0 rows")
            it.raw["booking_error"] = "returning list parsed 0 rows"
            return it
        for r in rows:  # return rows are dated from the return date
            parsed = parse_row_aria(r.outbound.aria_label or "", query.return_date)
            if parsed:
                r.outbound = parsed.leg
        chosen = self._choose_return(rows, pick)
        it.inbound = Leg(**chosen.outbound.model_dump())
        it.return_stops = chosen.outbound.stops
        it.raw["return_row_index"] = chosen.row_index
        it.raw["return_rows"] = len(rows)
        if chosen.price_results_cad is not None:
            it.raw["price_results_with_return_cad"] = chosen.price_results_cad
        for a in chosen.outbound.airlines:
            if a not in it.airlines:
                it.airlines.append(a)
        if it.outbound.duration_min is not None and chosen.outbound.duration_min is not None:
            it.duration_min = it.outbound.duration_min + chosen.outbound.duration_min

        self._sleep("between_actions")
        self._click_row(page, chosen.outbound.aria_label or "", chosen.row_index)
        try:
            page.wait_for_url(BOOKING_URL_RE, timeout=45_000)
        except Exception as exc:  # noqa: BLE001
            self._check(page)
            self._artifacts(page, f"booking page not reached: {exc}")
            it.raw["booking_error"] = f"booking page: {type(exc).__name__}: {exc}"
            return it
        try:  # prices load asynchronously ("Getting prices" first); wait for the booking options
            page.wait_for_selector(
                "text=/Book with|Booking options|No booking options|Visit site/", timeout=30_000
            )
        except Exception:  # noqa: BLE001 - soft: parse whatever is there and record it
            log.warning("booking options did not render within 30 s")
        if self.sleep is not None:
            self.sleep.settle(3.0, 5.0)
        else:
            page.wait_for_timeout(3_000)
        text = page.locator("body").inner_text(timeout=15_000)
        from ...browser import check_block

        check_block(page, text=text)
        self._capture(f"booking_{pick.value}.txt", text)
        if self.capture_dir is not None:
            self._capture(f"booking_{pick.value}.html", _strip_html(page.content()))
        info = parse_booking_text(text)
        self._apply_booking(it, info, query, page.url)
        return it

    @staticmethod
    def _apply_booking(it: Itinerary, info: BookingInfo, query: SearchQuery, url: str) -> None:
        it.deep_link_url = url
        it.providers = info.providers
        it.raw["booking"] = info.to_raw()
        it.raw["booking_url"] = url
        expected = query.pax.adults + query.pax.children
        cheapest = info.cheapest
        if info.passengers_note is not None and info.passengers_note != expected:
            it.raw["pax_mismatch"] = True
            log.warning("booking page prices for %d passengers, expected %d", info.passengers_note, expected)
        if cheapest is not None and not it.raw.get("pax_mismatch"):
            it.price_total_cad = cheapest.total_cad
            it.price_provider = cheapest.name
            it.price_stage = PriceStage.BOOKING
        else:
            it.raw["booking_price_unavailable"] = (
                "no priced provider" if cheapest is None else "passenger count mismatch"
            )
        if info.currency_raw:
            it.currency_raw = info.currency_raw
        if info.has_luggage_info:
            it.carry_on_included = info.carry_on_included
            it.carry_on_fee_cad = info.carry_on_fee_cad
            it.checked_bag_fee_cad = info.checked_bag_fee_cad
            it.luggage_source = LUGGAGE_SOURCE
        it.price_insight = info.price_insight
        flights = info.flight_numbers or _flight_numbers_from_url(url)
        if flights:
            it.flight_numbers = flights
        if info.fare_family:
            it.fare_family = info.fare_family
        if info.separate_tickets:
            it.raw["self_transfer"] = True

    def _pax_derive(self, page: Any, query: SearchQuery, it: Itinerary) -> None:
        """Lever D experiment: reload this pick's booking link re-encoded for the other passenger
        configs and record the totals in ``raw.pax_derived`` (report only; 1 load per config)."""
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        if not it.deep_link_url or "/booking" not in it.deep_link_url:
            return
        parsed = urlparse(it.deep_link_url)
        params = parse_qs(parsed.query)
        tfs = params.get("tfs", [""])[0]
        if not tfs:
            return
        derived: dict[str, Any] = {}
        for key, adults, children in self.pax_derive_configs:
            if (adults, children) == (query.pax.adults, query.pax.children):
                continue
            new_params = {k: v[0] for k, v in params.items()} | {
                "tfs": rewrite_passengers(tfs, adults, children)
            }
            url = urlunparse(parsed._replace(query=urlencode(new_params)))
            self._sleep("between_loads")
            try:
                self._goto(page, url)
                page.wait_for_selector("text=/Book with|Booking options|No booking options/", timeout=30_000)
                self.sleep.settle(2.0, 4.0) if self.sleep is not None else page.wait_for_timeout(2_000)
                text = page.locator("body").inner_text(timeout=15_000)
                info = parse_booking_text(text)
                cheapest = info.cheapest
                derived[key] = {
                    "url": page.url,
                    "adults": adults,
                    "children": children,
                    "passengers_note": info.passengers_note,
                    "accepted": info.passengers_note == adults + children,
                    "price_total_cad": cheapest.total_cad if cheapest else None,
                    "price_provider": cheapest.name if cheapest else None,
                    "providers": [p.model_dump() for p in info.providers],
                }
            except BlockedError:
                raise
            except Exception as exc:  # noqa: BLE001 - experiment only
                derived[key] = {"error": f"{type(exc).__name__}: {exc}"}
            log.info("pax-derive %s: %s", key, {k: v for k, v in derived[key].items() if k != "providers"})
        it.raw["pax_derived"] = derived

    def enrich_luggage(self, page: Any, query: SearchQuery, itinerary: Itinerary, pick: Pick) -> Itinerary:
        """Generic contract: re-navigate to the pick's load if needed (1 extra load), then visit."""
        if itinerary.results_url and page.url.split("&tfu=")[0] != itinerary.results_url.split("&tfu=")[0]:
            self._sleep("between_loads")
            self._goto(page, itinerary.results_url)
            self._current_labels = read_rows(page, sleep_actions=lambda: self._sleep("between_actions"))
        return self._visit_booking(page, query, itinerary, pick)

    # ---- template override: interleaved loads + visits (≤ 9 loads) ---------------------------
    def run_search(self, page: Any, query: SearchQuery) -> SearchResult:
        self.current_search_key = query.search_key
        mode = self.budget_cfg.booking_visits
        candidates: list[Itinerary] = []
        picks: dict[Pick, Itinerary] = {}
        visited: dict[tuple, Itinerary] = {}
        failed_visits = 0
        for i, (variant, tag, pick) in enumerate(LOADS):
            if i:
                self._sleep("between_loads")
            cands = self._load_results(page, query, variant, tag)
            candidates.extend(cands)
            chosen = self.select_picks(cands)[pick]
            visit = mode == "all" or (mode == "best_only" and pick is Pick.BEST)
            key = chosen.identity()
            if visit and key in visited:
                chosen = visited[key].model_copy(deep=True)
                chosen.raw["booking_dedup_of"] = visited[key].raw.get("booking_pick")
                chosen.candidate_source = tag
            elif visit:
                try:
                    chosen = self._visit_booking(page, query, chosen, pick)
                except BlockedError:
                    raise
                except Exception as exc:  # noqa: BLE001 - keep the results-stage pick, record why
                    log.warning("booking visit for %s failed: %s", pick.value, exc)
                    self._artifacts(page, f"booking visit failed: {type(exc).__name__}: {exc}")
                    chosen.raw["booking_error"] = f"{type(exc).__name__}: {exc}"
                chosen.raw.setdefault("booking_pick", pick.value)
                if chosen.price_stage is PriceStage.BOOKING:
                    visited[key] = chosen  # only successful visits are reused by later picks
                    if self.pax_derive_configs and pick is Pick.BEST:
                        self._pax_derive(page, query, chosen)
                else:
                    failed_visits += 1
            else:
                chosen.raw["booking_visit"] = f"skipped (booking_visits={mode})"
            picks[pick] = chosen
        status = "partial" if failed_visits else "ok"
        return SearchResult(
            query=query,
            picks=picks,
            candidates=len(candidates),
            status=status,
            page_url=self.build_url(query),
            page_loads=self.budget.used_in_current_search if self.budget else 0,
        )
