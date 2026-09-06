"""Google Flights booking page (``/travel/flights/booking?tfs=…``) parsing — pure function over
``body.inner_text()``.

Observed (research, live 2026-09-04)::

    Booking options
    Book with Air Transat
    Airline
    CA$2,173
    Continue
    Book with FlightHub
    CA$2,254
    ...
    Book with Porter Airlines
    Price hidden because it might be incorrect
    Visit site for price
    Prices include required taxes + fees for 3 passengers. Optional charges and bag fees may apply.
    ...
    1 free carry-on per passenger
    1st checked bag per passenger: CA$150–170
    ...
    CA$2,173 is low for Economy — CA$1,403 cheaper than usual; usually CA$2,700–5,600
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ...models import Provider

PARSER_VERSION = "booking-v1"

# inner_text glues the "Airline" badge to the name on one line: "Book with Air TransatAirline"
BOOK_WITH_RE = re.compile(r"^Book with (.+?)(?P<airline>(?<=[a-z\)])Airline)?\s*$")
MONEY_RE = re.compile(r"(CA\$|C\$|\$|US\$)\s?(\d[\d,]*)(?:\.(\d{2}))?")
MONEY_LINE_RE = re.compile(r"^(?:from )?(CA\$|C\$|US\$|\$)\s?(\d[\d,]*)(?:\.(\d{2}))?\s*$", re.I)
HIDDEN_RE = re.compile(r"price hidden|visit site for price|check price", re.I)
# "for 3 passengers" (research) or "for 1 adult" / "for 2 adults, 1 child" (observed): sum the counts
PAX_NOTE_RE = re.compile(r"Prices include required taxes \+ fees for ([^.]+?)\.", re.I)
CARRY_ON_INCLUDED_RE = re.compile(r"(\d+) free carry-on(?: bags?)?(?: per passenger)?", re.I)
CARRY_ON_EXCLUDED_RE = re.compile(
    r"no carry-on|carry-on (?:bag )?(?:not included|not allowed|not permitted)|personal item only|"
    r"carry-on bags? (?:cost|for a fee)",
    re.I,
)
CARRY_ON_FEE_RE = re.compile(r"carry-on(?: bag)?(?: per passenger)?:?\s*(?:CA\$|\$)(\d[\d,]*)", re.I)
CHECKED_RANGE_RE = re.compile(
    r"1st checked bag(?: per passenger)?:?\s*(?:CA\$|\$)(\d[\d,]*)(?:\s?[–—-]\s?(?:CA\$|\$)?(\d[\d,]*))?",
    re.I,
)
CHECKED_SENTENCE_RE = re.compile(
    r"First checked bag costs (?:between )?(\d[\d,]*) Canadian dollars(?: and (\d[\d,]*) Canadian dollars)?",
    re.I,
)
CHECKED_FREE_RE = re.compile(
    r"(\d+) free checked bags?|checked bag included|1st checked bag(?: per passenger)?:?\s*(?:free|included)",
    re.I,
)
INSIGHT_RE = re.compile(
    r"^(?:CA\$|\$)\d[\d,]* is (?:low|typical|high|fairly typical|very low|very high) for .+", re.I
)
FLIGHT_NO_RE = re.compile(r"^(?:Flight )?([A-Z][A-Z0-9]|[0-9][A-Z]) ?(\d{2,4})$")
SEPARATE_TICKETS_RE = re.compile(r"separate tickets|self[- ]transfer", re.I)
FARE_FAMILY_RE = re.compile(
    r"^(Basic(?: Economy)?|Economy Basic|Standard|Flex|Comfort|Latitude|Econo(?:Flex)?|UltraBasic|"
    r"Eco (?:Budget|Standard|Flex)|Light|Saver|Main Cabin|Premium Economy)$",
    re.I,
)


def _money(groups: tuple[str, str, str | None]) -> float:
    _cur, whole, cents = groups
    return float(whole.replace(",", "")) + (int(cents) / 100 if cents else 0.0)


@dataclass
class BookingInfo:
    providers: list[Provider] = field(default_factory=list)
    passengers_note: int | None = None
    carry_on_included: bool | None = None
    carry_on_fee_cad: float | None = None
    checked_bag_fee_cad: float | None = None
    checked_bag_fee_max_cad: float | None = None
    checked_bag_fee_raw: str | None = None
    luggage_text: list[str] = field(default_factory=list)
    price_insight: str | None = None
    flight_numbers: list[str] = field(default_factory=list)
    fare_family: str | None = None
    currency_raw: str | None = None
    separate_tickets: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def priced(self) -> list[Provider]:
        return [p for p in self.providers if p.total_cad is not None]

    @property
    def cheapest(self) -> Provider | None:
        return min(self.priced, key=lambda p: p.total_cad or 0) if self.priced else None

    @property
    def has_luggage_info(self) -> bool:
        return self.carry_on_included is not None or self.checked_bag_fee_cad is not None

    def to_raw(self) -> dict[str, Any]:
        return {
            "parser_version": PARSER_VERSION,
            "providers": [p.model_dump() for p in self.providers],
            "passengers_note": self.passengers_note,
            "luggage_text": self.luggage_text,
            "checked_bag_fee_max_cad": self.checked_bag_fee_max_cad,
            "checked_bag_fee_raw": self.checked_bag_fee_raw,
            "carry_on_included": self.carry_on_included,
            "price_insight": self.price_insight,
            "flight_numbers": self.flight_numbers,
            "fare_family": self.fare_family,
            "separate_tickets": self.separate_tickets,
            **self.raw,
        }


def _parse_providers(lines: list[str]) -> list[Provider]:
    providers: list[Provider] = []
    i = 0
    while i < len(lines):
        m = BOOK_WITH_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1).strip()
        is_airline = bool(m.group("airline"))
        total: float | None = None
        note: str | None = None
        j = i + 1
        while j < len(lines) and j <= i + 8 and not BOOK_WITH_RE.match(lines[j]):
            line = lines[j]
            if line.lower() == "airline":
                is_airline = True
            elif HIDDEN_RE.search(line):
                note = note or line  # keep the explanatory first line
            else:
                pm = MONEY_LINE_RE.match(line)
                if pm and total is None:
                    total = _money((pm.group(1), pm.group(2), pm.group(3)))
            if total is not None and (j > i + 3 or note):
                break
            j += 1
        providers.append(Provider(name=name, total_cad=total, is_airline=is_airline, note=note))
        i = j if j > i + 1 else i + 1
    return providers


def parse_booking_text(text: str) -> BookingInfo:
    info = BookingInfo()
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    info.providers = _parse_providers(lines)
    if any("CA$" in ln for ln in lines):
        info.currency_raw = "CA$"

    joined = "\n".join(lines)
    pm = PAX_NOTE_RE.search(joined)
    if pm:
        counts = [int(x) for x in re.findall(r"\d+", pm.group(1))]
        info.passengers_note = sum(counts) if counts else None
        info.raw["passengers_note_text"] = pm.group(0)

    for ln in lines:
        low = ln.lower()
        if "carry-on" in low or "checked bag" in low or "personal item" in low:
            if ln not in info.luggage_text:
                info.luggage_text.append(ln)
        if info.price_insight is None and INSIGHT_RE.match(ln):
            info.price_insight = ln
        fm = FLIGHT_NO_RE.match(ln)
        if fm:
            code = f"{fm.group(1)} {fm.group(2)}"
            if code not in info.flight_numbers:
                info.flight_numbers.append(code)
        if info.fare_family is None and FARE_FAMILY_RE.match(ln):
            info.fare_family = ln
    if SEPARATE_TICKETS_RE.search(joined):
        info.separate_tickets = True

    lug = "\n".join(info.luggage_text)
    if CARRY_ON_INCLUDED_RE.search(lug):
        info.carry_on_included = True
    elif CARRY_ON_EXCLUDED_RE.search(lug):
        info.carry_on_included = False
        cm = CARRY_ON_FEE_RE.search(lug)
        if cm:
            info.carry_on_fee_cad = float(cm.group(1).replace(",", ""))
    cr = CHECKED_RANGE_RE.search(lug)
    cs = CHECKED_SENTENCE_RE.search(lug)
    if CHECKED_FREE_RE.search(lug):
        info.checked_bag_fee_cad = 0.0
        info.checked_bag_fee_raw = CHECKED_FREE_RE.search(lug).group(0)  # type: ignore[union-attr]
    elif cr:
        info.checked_bag_fee_cad = float(cr.group(1).replace(",", ""))
        info.checked_bag_fee_max_cad = float(cr.group(2).replace(",", "")) if cr.group(2) else None
        info.checked_bag_fee_raw = cr.group(0)
    elif cs:
        info.checked_bag_fee_cad = float(cs.group(1).replace(",", ""))
        info.checked_bag_fee_max_cad = float(cs.group(2).replace(",", "")) if cs.group(2) else None
        info.checked_bag_fee_raw = cs.group(0)
    return info


__all__ = ["PARSER_VERSION", "BookingInfo", "parse_booking_text"]
