"""Pick selection — pure functions over parsed candidates (no browser).

Google ranks all three picks natively (Best = first row of the default load, Cheapest = min price of the
Cheapest-tab load, Fastest = min duration of the Duration-sort load). Sources without a native ranking
fall back to ``local_v1`` (research §best-definition) and are tagged ``pick_rule='local-v1'``.
"""

from __future__ import annotations

from .models import Itinerary, Pick

BIG = 10**6


def _price(c: Itinerary) -> float:
    return c.price_results_cad if c.price_results_cad is not None else float(BIG)


def _duration(c: Itinerary) -> int:
    return c.duration_min if c.duration_min is not None else BIG


def cheapest_of(cands: list[Itinerary]) -> Itinerary:
    return min(cands, key=lambda c: (_price(c), _duration(c), c.row_index))


def fastest_of(cands: list[Itinerary]) -> Itinerary:
    return min(cands, key=lambda c: (_duration(c), _price(c), c.row_index))


def select_picks(cands: list[Itinerary], native: frozenset[Pick]) -> dict[Pick, Itinerary]:
    if not cands:
        raise ValueError("no candidates to pick from")
    out: dict[Pick, Itinerary] = {}
    if Pick.BEST in native:  # Google: first row of the default load = "Top departing flights" #1
        # first row of the default load; if row 0 had no price ("Total price is unavailable") take the
        # first priced row of that load — still Google's own ranking, so pick_rule stays 'native'
        pool = sorted((c for c in cands if c.candidate_source == "best_load"), key=lambda c: c.row_index)
        if pool:
            best = pool[0]
            if best.row_index != 0:
                best.raw["best_row0_unpriced"] = True
            out[Pick.BEST] = best
    if Pick.CHEAPEST in native:  # min price over the Cheapest-tab load (OTA fares included); tie → shorter
        pool = [c for c in cands if c.candidate_source == "cheapest_load"] or cands
        out[Pick.CHEAPEST] = cheapest_of(pool)
    if Pick.FASTEST in native:  # min total duration over the Duration-sort load; tie → cheaper
        pool = [c for c in cands if c.candidate_source == "duration_load"] or cands
        out[Pick.FASTEST] = fastest_of(pool)
    for pick in Pick:  # anything the site cannot rank natively → local rule
        if pick not in out:
            chosen = local_v1(cands, pick).model_copy(deep=True)
            chosen.pick_rule = "local-v1"
            out[pick] = chosen
    return out


def local_v1(cands: list[Itinerary], pick: Pick) -> Itinerary:
    """Shared 'best' rule for sources without a native Best; also the fallback for cheapest/fastest.

    Computed on ONE candidate set; self-transfer / separate-ticket itineraries are excluded from BEST.
    Lowest score wins; ties → cheaper.
    """
    if not cands:
        raise ValueError("no candidates")
    if pick is Pick.CHEAPEST:
        return cheapest_of(cands)
    if pick is Pick.FASTEST:
        return fastest_of(cands)
    pool = [c for c in cands if not c.raw.get("self_transfer")] or cands
    priced = [c for c in pool if c.price_results_cad is not None] or pool
    min_price = min((_price(c) for c in priced), default=1.0) or 1.0
    durations = [c.duration_min for c in pool if c.duration_min]
    min_dur = min(durations) if durations else 1

    def score(c: Itinerary) -> float:
        stop_penalty = (
            1
            + 0.5 * (c.stops or 0)
            + 0.25 * bool(c.raw.get("long_layover"))
            + 0.25 * bool(c.raw.get("airport_change"))
        )
        return (
            0.50 * _price(c) / min_price + 0.35 * (c.duration_min or min_dur) / min_dur + 0.15 * stop_penalty
        )

    return min(pool, key=lambda c: (score(c), _price(c), c.row_index))
