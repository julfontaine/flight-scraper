"""WestJet — DISABLED in v1 (first candidate to enable; see docs/enabling-a-source.md)."""

from __future__ import annotations

from ._stub import DisabledAdapter

ENTRY_URL = "https://www.westjet.com/en-ca/flights"  # search widget → /shop/* SPA (query contract unknown)


class WestJetAdapter(DisabledAdapter):
    source_id = "westjet"
    name = "WestJet"
    kind = "airline"
    priority = 2
    default_price_stage = "fare_select"
    disabled_reason = (
        "v1 disabled: no confirmed deep link (Vue SPA /shop/*, query contract unknown); checkout unverified; "
        "weakest anti-bot of the airlines, first candidate to enable after a headed probe. "
        "Research: finding category=westjet"
    )
