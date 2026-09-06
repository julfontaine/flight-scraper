"""Adapter registry: all nine sources, ordered by enable priority (1 = first)."""

from __future__ import annotations

from .air_canada import AirCanadaAdapter
from .air_transat import AirTransatAdapter
from .base import ArtifactSaver, BaseAdapter, BlockedError, NoResultsParsed, SourceDisabled
from .expedia import ExpediaAdapter
from .flair import FlairAdapter
from .google_flights.adapter import GoogleFlightsAdapter
from .kayak import KayakAdapter
from .porter import PorterAdapter
from .skyscanner import SkyscannerAdapter
from .westjet import WestJetAdapter

_ALL: list[type[BaseAdapter]] = sorted(
    [
        GoogleFlightsAdapter,
        WestJetAdapter,
        AirCanadaAdapter,
        KayakAdapter,
        AirTransatAdapter,
        SkyscannerAdapter,
        PorterAdapter,
        FlairAdapter,
        ExpediaAdapter,
    ],
    key=lambda a: a.priority,
)

REGISTRY: dict[str, type[BaseAdapter]] = {a.source_id: a for a in _ALL}

__all__ = [
    "REGISTRY",
    "ArtifactSaver",
    "BaseAdapter",
    "BlockedError",
    "NoResultsParsed",
    "SourceDisabled",
]
