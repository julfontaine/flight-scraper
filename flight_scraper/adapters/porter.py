"""Porter Airlines — DISABLED in v1 (booking host unreachable from probe; Cloudflare challenge on www)."""

from __future__ import annotations

from ._stub import DisabledAdapter

ENTRY_URL = "https://booking.flyporter.com/en-ca/book-travel/book-flights-online"


class PorterAdapter(DisabledAdapter):
    source_id = "porter"
    name = "Porter Airlines"
    kind = "airline"
    priority = 7
    default_price_stage = "fare_select"
    disabled_reason = (
        "v1 disabled: booking host unreachable from probe, www behind Cloudflare challenge; no deep link; "
        "robots disallows booking paths; ToS forbids robots. Research: finding category=porter"
    )
