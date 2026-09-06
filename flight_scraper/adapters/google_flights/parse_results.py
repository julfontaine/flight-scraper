"""Google Flights results parsing: the aria-label sentence of each ``li.pIav2d`` row → ``Leg`` + price.

Everything here is a pure function over strings (fixture-tested); ``read_rows`` is the one browser
helper and returns the raw aria-label strings so fixtures can be captured verbatim.

Observed en-US sentence (research, live 2026-09-04)::

    From 2173 Canadian dollars round trip total. 1 stop flight with Porter Airlines and Air Transat.
    Leaves Montréal-Pierre Elliott Trudeau International Airport at 5:00 PM on Thursday, October 15 and
    arrives at Paris Charles de Gaulle Airport at 9:30 AM on Friday, October 16. Total duration 11 hr 30 min.
    Layover (1 of 1) is a 2 hr 37 min layover at Toronto Pearson International Airport. ...
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ...models import Itinerary, Leg, SearchQuery

log = logging.getLogger(__name__)

PARSER_VERSION = "aria-v1"
ROW_SELECTOR = "li.pIav2d"
LONG_LAYOVER_MIN = 4 * 60

PRICE_RE = re.compile(r"From (\d[\d,]*) (Canadian dollars|[A-Za-z ]+?)(?: round trip)? total", re.I)
STOPS_RE = re.compile(r"\b(Nonstop|(\d+) stops?) flight with (.+?)\.(?:\s|$)", re.I)
LEAVES_RE = re.compile(
    r"Leaves (.+?) at (\d{1,2}:\d{2}\s?[AP]M) on (\w+), (\w+) (\d{1,2})"
    r"(?: and arrives at (.+?) at (\d{1,2}:\d{2}\s?[AP]M) on (\w+), (\w+) (\d{1,2}))?",
    re.I,
)
DURATION_RE = re.compile(r"Total duration (?:(\d+) hr)?\s?(?:(\d+) min)?", re.I)
LAYOVER_RE = re.compile(
    r"Layover \((\d+) of (\d+)\) is an? (?:(\d+) hr)?\s?(?:(\d+) min)? ?(overnight )?layover at (.+?)\.", re.I
)
CARRIER_SPLIT_RE = re.compile(r",\s*(?:and\s+)?|\s+and\s+")
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}  # fmt: skip


@dataclass
class ParsedRow:
    price: float | None
    currency_raw: str | None
    leg: Leg
    raw: dict[str, Any] = field(default_factory=dict)


def _parse_time(text: str) -> tuple[int, int]:
    t = text.replace(" ", "").upper()
    hhmm, ampm = t[:-2], t[-2:]
    hh, mm = (int(x) for x in hhmm.split(":"))
    if ampm == "PM" and hh != 12:
        hh += 12
    if ampm == "AM" and hh == 12:
        hh = 0
    return hh, mm


def infer_year(month: int, day: int, anchor: date) -> int:
    """Google prints no year; pick the year that puts (month, day) on/after ``anchor`` (rollover-safe)."""
    year = anchor.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return year
    if candidate < anchor and (anchor - candidate).days > 300:
        return year + 1
    if candidate > anchor and (candidate - anchor).days > 300:
        return year - 1
    return year


def _to_datetime(time_text: str, month_name: str, day: str, anchor: date) -> datetime | None:
    month = MONTHS.get(month_name.lower())
    if month is None:
        return None
    hh, mm = _parse_time(time_text)
    return datetime(infer_year(month, int(day), anchor), month, int(day), hh, mm)


def split_carriers(text: str) -> list[str]:
    parts = [p.strip() for p in CARRIER_SPLIT_RE.split(text) if p.strip()]
    out: list[str] = []
    for p in parts:
        if p not in out:
            out.append(p)
    return out


def parse_row_aria(text: str, anchor: date) -> ParsedRow | None:
    """Parse one row sentence. Returns None when the price sentence is missing (row excluded)."""
    text = " ".join(text.split())  # collapse whitespace/newlines
    pm = PRICE_RE.search(text)
    if not pm:
        return None
    price = float(pm.group(1).replace(",", ""))
    currency_raw = pm.group(2).strip()
    raw: dict[str, Any] = {"aria_label": text, "parser_version": PARSER_VERSION}
    leg = Leg(aria_label=text)

    sm = STOPS_RE.search(text)
    if sm:
        leg.stops = 0 if sm.group(1).lower() == "nonstop" else int(sm.group(2))
        leg.airlines = split_carriers(sm.group(3))
    else:
        raw.setdefault("unparsed", []).append("stops")

    lm = LEAVES_RE.search(text)
    if lm:
        raw["depart_airport"] = lm.group(1)
        leg.depart_local = _to_datetime(lm.group(2), lm.group(4), lm.group(5), anchor)
        if lm.group(6):
            raw["arrive_airport"] = lm.group(6)
            leg.arrive_local = _to_datetime(lm.group(7), lm.group(9), lm.group(10), anchor)
    else:
        raw.setdefault("unparsed", []).append("times")

    dm = DURATION_RE.search(text)
    if dm and (dm.group(1) or dm.group(2)):
        leg.duration_min = int(dm.group(1) or 0) * 60 + int(dm.group(2) or 0)
    else:
        raw.setdefault("unparsed", []).append("duration")

    layovers = []
    for m in LAYOVER_RE.finditer(text):
        minutes = int(m.group(3) or 0) * 60 + int(m.group(4) or 0)
        overnight = bool(m.group(5))
        layovers.append({"minutes": minutes, "overnight": overnight, "airport": m.group(6)})
        if overnight or minutes > LONG_LAYOVER_MIN:
            raw["long_layover"] = True
    if layovers:
        raw["layovers"] = layovers
    lowered = text.lower()
    if "self transfer" in lowered or "self-transfer" in lowered or "separate tickets" in lowered:
        raw["self_transfer"] = True
    if "airport change" in lowered or "change of airport" in lowered or "different airport" in lowered:
        raw["airport_change"] = True
    if "overnight" in lowered and "overnight" not in json.dumps(layovers):
        raw["overnight"] = True
    if currency_raw.lower() != "canadian dollars":
        raw["currency_mismatch"] = True
    return ParsedRow(price=price, currency_raw=currency_raw, leg=leg, raw=raw)


def rows_to_itineraries(
    labels: list[str], query: SearchQuery, candidate_source: str, results_url: str
) -> tuple[list[Itinerary], list[str]]:
    """aria-labels → tagged candidates (+ the labels that did not parse, kept for ``raw.unparsed``)."""
    out: list[Itinerary] = []
    unparsed: list[str] = []
    seen: set[str] = set()
    for idx, label in enumerate(labels):
        if label in seen:  # identical sentence twice = a re-render artefact, not a second itinerary
            continue
        seen.add(label)
        parsed = parse_row_aria(label, query.depart_date)
        if parsed is None or parsed.raw.get("currency_mismatch"):
            unparsed.append(label)
            continue
        out.append(
            Itinerary(
                outbound=parsed.leg,
                airlines=list(parsed.leg.airlines),
                duration_min=parsed.leg.duration_min,
                stops=parsed.leg.stops,
                price_results_cad=parsed.price,
                currency_raw=parsed.currency_raw,
                results_url=results_url,
                deep_link_url=results_url,
                candidate_source=candidate_source,
                row_index=idx,
                raw={**parsed.raw, "candidate_source": candidate_source, "row_index": idx},
            )
        )
    return out, unparsed


# ------------------------------------------------------------------ browser helper
ROW_LABELS_JS = """els => els.map(li => {
  const el = li.querySelector('[aria-label]');
  return el ? (el.getAttribute('aria-label') || '') : '';
})"""


def row_labels(page: Any) -> list[str]:
    """First ``[aria-label]`` of every ``li.pIav2d`` row, in DOM order (one round-trip)."""
    return list(page.eval_on_selector_all(ROW_SELECTOR, ROW_LABELS_JS))


def wait_rows_stable(page: Any, *, settle_s: float = 2.0, max_s: float = 15.0) -> list[str]:
    """Rows stream in: poll until the label list stops changing for ``settle_s`` (max ``max_s``)."""
    deadline = time.monotonic() + max_s
    last = row_labels(page)
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.5)
        current = row_labels(page)
        if current != last:
            last, stable_since = current, time.monotonic()
        elif time.monotonic() - stable_since >= settle_s:
            break
    return last


class RpcCounter:
    """Counts Google's ``GetShoppingResults`` / ``GetBookingResults`` responses per navigation.

    The research observed 2-3 shopping responses per results load (initial, best, more); reading the
    DOM before the second one returns a partial, sometimes duplicated, list."""

    def __init__(self, page: Any) -> None:
        self.shopping = 0
        self.booking = 0
        page.on("response", self._on_response)

    def _on_response(self, response: Any) -> None:
        url = getattr(response, "url", "") or ""
        if "GetShoppingResults" in url:
            self.shopping += 1
        elif "GetBookingResults" in url:
            self.booking += 1

    def reset(self) -> None:
        self.shopping = 0
        self.booking = 0

    def wait_for(self, attr: str, n: int, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if getattr(self, attr) >= n:
                return True
            time.sleep(0.25)
        return getattr(self, attr) >= n


def read_rows(
    page: Any, *, expand: bool = True, sleep_actions=None, rpc: RpcCounter | None = None, min_rpc: int = 2
) -> list[str]:
    """Wait for the list to finish streaming, expand "more flights", return the row aria-labels."""
    page.wait_for_selector(ROW_SELECTOR, timeout=45_000)
    if rpc is not None and not rpc.wait_for("shopping", min_rpc, 20.0):
        log.debug("only %d GetShoppingResults responses within 20 s", rpc.shopping)
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:  # noqa: BLE001 - soft wait
        pass
    labels = wait_rows_stable(page)
    if expand:
        for _ in range(2):  # the button may re-render once after the first expansion
            more = page.get_by_role("button", name=re.compile(r"more flights", re.I))
            try:
                if not more.count() or not more.first.is_visible():
                    break
                more.first.click(timeout=5_000)
                if sleep_actions:
                    sleep_actions()
            except Exception as exc:  # noqa: BLE001 - expansion is best-effort
                log.debug("expand click failed: %s", exc)
                break
            labels = wait_rows_stable(page)
    return labels


__all__ = [
    "PARSER_VERSION",
    "ROW_SELECTOR",
    "ParsedRow",
    "RpcCounter",
    "infer_year",
    "parse_row_aria",
    "read_rows",
    "row_labels",
    "rows_to_itineraries",
    "split_carriers",
    "wait_rows_stable",
]
