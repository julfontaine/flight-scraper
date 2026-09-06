"""Air Transat — DISABLED in v1 (no public deep link; form-drive only)."""

from __future__ import annotations

from ._stub import DisabledAdapter

ENTRY_URL = "https://www.airtransat.com/en-CA/book/book-a-flight"


class AirTransatAdapter(DisabledAdapter):
    source_id = "air_transat"
    name = "Air Transat"
    kind = "airline"
    priority = 5
    default_price_stage = "fare_select"
    disabled_reason = (
        "v1 disabled: no deep link (Softvoyage engine, form-drive only); Imperva/Incapsula; "
        "ToS forbids screen-scraping. Research: finding category=air-transat"
    )
