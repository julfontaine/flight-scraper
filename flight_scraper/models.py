"""Pydantic v2 data models shared by every adapter, the runner and the sinks.

These mirror the plan's ``<adapter_contract>`` verbatim; keep them free of any
browser or database import so they can be used in pure-function tests.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Pick(StrEnum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    BEST = "best"


class PriceStage(StrEnum):
    RESULTS = "results"  # results-row total (what Google shows in the list)
    FARE_SELECT = "fare_select"  # airline fare-family page (future sources)
    REVIEW = "review"  # airline/OTA review page (future sources)
    BOOKING = "booking"  # Google /travel/flights/booking per-provider total incl. taxes + fees


class PaxConfig(BaseModel):
    key: str  # '1a', '2a', '1a1c', '1a2c'
    adults: int = Field(ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    child_ages: list[int] = Field(
        default_factory=list
    )  # [] for Google (no age); real ages for future sources
    priority: int = 1


class SearchQuery(BaseModel):
    source_id: str
    origin: str  # IATA, upper-case
    destination: str
    depart_date: date
    return_date: date
    offset_days: int | None = None  # None for ad-hoc CLI searches
    pax: PaxConfig
    cabin: str = "economy"
    currency: str = "CAD"

    @property
    def cell_key(self) -> str:  # rotation identity, independent of concrete dates
        return f"{self.source_id}:{self.origin}-{self.destination}:+{self.offset_days}:{self.pax.key}"

    @property
    def route_key(self) -> str:
        return f"{self.origin}-{self.destination}"

    @property
    def search_key(self) -> str:  # file-system safe identity incl. dates (artifacts, out/ names)
        return f"{self.source_id}_{self.origin}-{self.destination}_{self.depart_date}_{self.pax.key}"


class Leg(BaseModel):
    depart_local: datetime | None = None  # airport-local wall time; Google exposes no tz
    arrive_local: datetime | None = None
    duration_min: int | None = None
    stops: int | None = None
    airlines: list[str] = Field(default_factory=list)
    flight_numbers: list[str] = Field(default_factory=list)
    aria_label: str | None = None  # verbatim source sentence, for fixtures and debugging


class Provider(BaseModel):
    name: str
    total_cad: float | None  # None when Google hides the price ("Visit site for price")
    is_airline: bool = False
    note: str | None = None


class Itinerary(BaseModel):
    outbound: Leg
    inbound: Leg | None = None  # filled after the return-leg click (booking-visit picks)
    airlines: list[str] = Field(default_factory=list)
    flight_numbers: list[str] = Field(default_factory=list)
    duration_min: int | None = None  # outbound + inbound when both known, else outbound
    stops: int | None = None  # outbound
    return_stops: int | None = None
    fare_family: str | None = None
    price_results_cad: float | None = None  # results-row "round trip total" (all passengers)
    price_total_cad: float | None = None  # cheapest provider total from the booking page
    price_provider: str | None = None
    providers: list[Provider] = Field(default_factory=list)
    price_stage: PriceStage = PriceStage.RESULTS
    currency_raw: str | None = None
    carry_on_included: bool | None = None
    carry_on_fee_cad: float | None = None
    checked_bag_fee_cad: float | None = None  # low end of a range
    luggage_source: str | None = None  # 'google_booking_page' | None
    price_insight: str | None = None
    deep_link_url: str | None = None  # booking URL when visited, else results URL
    results_url: str | None = None
    candidate_source: str = "best_load"  # 'best_load' | 'cheapest_load' | 'duration_load' | 'single_load'
    row_index: int = 0  # position in its load, 0 = first row
    pick_rule: str = "native"  # 'native' | 'local-v1'
    raw: dict[str, Any] = Field(default_factory=dict)

    def identity(self) -> tuple:  # used to skip duplicate booking visits
        return (
            tuple(self.outbound.airlines),
            self.outbound.depart_local,
            self.outbound.arrive_local,
            self.inbound.depart_local if self.inbound else None,
            self.inbound.arrive_local if self.inbound else None,
        )


class SearchResult(BaseModel):
    query: SearchQuery
    status: str = "pending"  # ok | partial | blocked | error | skipped
    error: str | None = None
    blocked: bool = False
    page_url: str | None = None
    page_loads: int = 0
    picks: dict[Pick, Itinerary] = Field(default_factory=dict)
    candidates: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: int = 1
