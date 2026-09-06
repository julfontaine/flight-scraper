from __future__ import annotations

import pytest

from flight_scraper.models import Pick
from flight_scraper.picks import local_v1, select_picks
from tests.conftest import make_it

NATIVE_ALL = frozenset({Pick.BEST, Pick.CHEAPEST, Pick.FASTEST})


def test_native_google_picks_from_tagged_candidates():
    cands = [
        make_it(2173, 690, 1, "best_load", 0),
        make_it(1900, 900, 2, "best_load", 1),
        make_it(1500, 1200, 2, "cheapest_load", 0),
        make_it(1450, 1300, 2, "cheapest_load", 1),  # cheapest
        make_it(2884, 420, 0, "duration_load", 0),  # fastest
        make_it(2000, 500, 1, "duration_load", 1),
    ]
    picks = select_picks(cands, NATIVE_ALL)
    assert picks[Pick.BEST] is cands[0]
    assert picks[Pick.CHEAPEST] is cands[3]
    assert picks[Pick.FASTEST] is cands[4]
    assert all(p.pick_rule == "native" for p in picks.values())


def test_tie_breaks():
    cands = [
        make_it(1000, 800, 1, "cheapest_load", 0),
        make_it(1000, 700, 1, "cheapest_load", 1),  # same price, shorter wins
        make_it(1200, 400, 0, "duration_load", 0),
        make_it(1100, 400, 0, "duration_load", 1),  # same duration, cheaper wins
        make_it(999, 999, 0, "best_load", 0),
    ]
    picks = select_picks(cands, NATIVE_ALL)
    assert picks[Pick.CHEAPEST] is cands[1]
    assert picks[Pick.FASTEST] is cands[3]


def test_fallback_pools_when_a_load_is_missing():
    cands = [make_it(2173, 690, 1, "best_load", 0), make_it(1500, 900, 2, "best_load", 1)]
    picks = select_picks(cands, NATIVE_ALL)
    assert picks[Pick.CHEAPEST] is cands[1] and picks[Pick.FASTEST] is cands[0]


def test_local_v1_ordering_and_self_transfer_exclusion():
    cands = [
        make_it(1000, 600, 0, "single_load", 0),  # cheap & fast & nonstop → best
        make_it(900, 1500, 2, "single_load", 1, long_layover=True),  # cheapest
        make_it(1500, 500, 0, "single_load", 2),  # fastest
        make_it(700, 550, 0, "single_load", 3, self_transfer=True),  # excluded from best
        make_it(2000, 700, 1, "single_load", 4, airport_change=True),
    ]
    assert local_v1(cands, Pick.CHEAPEST) is cands[3]  # cheapest is allowed to be a self-transfer
    assert local_v1(cands, Pick.FASTEST) is cands[2]
    assert local_v1(cands, Pick.BEST) is cands[0]
    picks = select_picks(cands, frozenset())
    assert picks[Pick.BEST].pick_rule == "local-v1" and picks[Pick.BEST].row_index == 0
    assert picks[Pick.CHEAPEST].pick_rule == "local-v1"


def test_native_best_missing_falls_back_to_local():
    cands = [make_it(1000, 600, 0, "cheapest_load", 0), make_it(800, 900, 1, "cheapest_load", 1)]
    picks = select_picks(cands, NATIVE_ALL)
    assert picks[Pick.BEST].pick_rule == "local-v1"
    assert picks[Pick.CHEAPEST].pick_rule == "native"


def test_missing_prices_do_not_crash():
    cands = [make_it(None, 600, 0, "best_load", 0), make_it(800, None, 1, "best_load", 1)]
    picks = select_picks(cands, NATIVE_ALL)
    assert picks[Pick.CHEAPEST] is cands[1] and picks[Pick.FASTEST] is cands[0]
    with pytest.raises(ValueError):
        select_picks([], NATIVE_ALL)
