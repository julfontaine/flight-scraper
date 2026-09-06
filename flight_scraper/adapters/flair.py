"""Flair Airlines — DISABLED in v1 (Cloudflare 403 block page to non-browser clients; no deep link)."""

from __future__ import annotations

from ._stub import DisabledAdapter

ENTRY_URL = "https://www.flyflair.com/"


class FlairAdapter(DisabledAdapter):
    source_id = "flair"
    name = "Flair Airlines"
    kind = "airline"
    priority = 8
    default_price_stage = "fare_select"
    disabled_reason = (
        "v1 disabled: Cloudflare 403 block page to non-browser clients; no deep link; ToS forbids "
        "screen-scraping. Research: finding category=flair"
    )
