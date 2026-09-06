from __future__ import annotations

from datetime import date

import pytest

from flight_scraper.adapters import REGISTRY, BaseAdapter, SourceDisabled
from flight_scraper.adapters.air_canada import market_code
from flight_scraper.models import PaxConfig, Pick, SearchQuery

EXPECTED = {
    "google_flights": ("meta", True),
    "westjet": ("airline", False),
    "air_canada": ("airline", False),
    "kayak": ("meta", False),
    "air_transat": ("airline", False),
    "skyscanner": ("meta", False),
    "porter": ("airline", False),
    "flair": ("airline", False),
    "expedia": ("ota", False),
}


def test_registry_has_all_nine_in_priority_order():
    assert list(REGISTRY) == list(EXPECTED)
    for source_id, (kind, enabled) in EXPECTED.items():
        cls = REGISTRY[source_id]
        assert issubclass(cls, BaseAdapter)
        assert cls.kind == kind and cls.enabled is enabled and cls.source_id == source_id
        if not enabled:
            assert cls.disabled_reason and "Research: finding category=" in cls.disabled_reason
        else:
            assert cls.disabled_reason is None


@pytest.mark.parametrize("source_id", [s for s, (_k, e) in EXPECTED.items() if not e])
def test_stubs_raise_source_disabled(source_id: str, query_yul_cdg: SearchQuery):
    adapter = REGISTRY[source_id]()
    with pytest.raises(SourceDisabled, match="v1 disabled"):
        adapter.search(None, query_yul_cdg)
    with pytest.raises(SourceDisabled):
        adapter.run_search(None, query_yul_cdg)


def test_kayak_url(query_yul_cdg: SearchQuery):
    url = REGISTRY["kayak"]().build_url(query_yul_cdg)
    assert (
        url
        == "https://www.ca.kayak.com/flights/YUL-CDG/2026-10-15/2026-10-22/2adults/children-8?sort=bestflight_a"
    )
    assert REGISTRY["kayak"]().build_url(query_yul_cdg, Pick.CHEAPEST).endswith("?sort=price_a")
    assert REGISTRY["kayak"]().build_url(query_yul_cdg, Pick.FASTEST).endswith("?sort=duration_a")
    q1 = query_yul_cdg.model_copy(update={"pax": PaxConfig(key="1a", adults=1)})
    assert "/1adults?" in REGISTRY["kayak"]().build_url(q1)


def test_skyscanner_url(query_yul_cdg: SearchQuery):
    url = REGISTRY["skyscanner"]().build_url(query_yul_cdg)
    assert url.startswith("https://www.skyscanner.ca/transport/flights/yul/cdg/261015/261022/?")
    assert "adultsv2=2" in url and "childrenv2=8" in url and "cabinclass=economy" in url and "rtn=1" in url
    assert "sortby=cheapest" in REGISTRY["skyscanner"]().build_url(query_yul_cdg, Pick.CHEAPEST)
    q2c = query_yul_cdg.model_copy(
        update={"pax": PaxConfig(key="1a2c", adults=1, children=2, child_ages=[5, 9])}
    )
    assert "childrenv2=5%7C9" in REGISTRY["skyscanner"]().build_url(q2c)


def test_expedia_url(query_yul_cdg: SearchQuery):
    url = REGISTRY["expedia"]().build_url(query_yul_cdg)
    assert url.startswith("https://www.expedia.ca/go/flight/search/Roundtrip/2026-10-15/2026-10-22?")
    for part in (
        "FromAirport=YUL",
        "ToAirport=CDG",
        "NumAdult=2",
        "NumChild=1",
        "Child1Age=8",
        "Class=3",
        "currency=CAD",
    ):
        assert part in url


def test_air_canada_url(query_yul_cdg: SearchQuery):
    url = REGISTRY["air_canada"]().build_url(query_yul_cdg)
    assert url.startswith("https://www.aircanada.com/booking/ca/en/aco/availability/rt/outbound?")
    for part in (
        "org0=YUL",
        "dest0=CDG",
        "departureDate0=2026-10-15",
        "org1=CDG",
        "dest1=YUL",
        "departureDate1=2026-10-22",
        "ADT=2",
        "YTH=0",
        "CHD=1",
        "INF=0",
        "INS=0",
        "lang=en-CA",
        "tripType=R",
        "marketCode=INT",
    ):
        assert part in url
    assert (
        market_code("YQB", "YYZ") == "DOM"
        and market_code("YUL", "MCO") == "TNB"
        and market_code("YUL", "CUN") == "INT"
    )


def test_google_skeleton_build_url_only(query_yul_cdg: SearchQuery):
    adapter = REGISTRY["google_flights"]()
    assert adapter.enabled and adapter.native_picks == {Pick.BEST, Pick.CHEAPEST, Pick.FASTEST}
    assert "tfs=" in adapter.build_url(query_yul_cdg)


def test_ad_hoc_query_dates():
    q = SearchQuery(
        source_id="google_flights",
        origin="YQB",
        destination="CDG",
        depart_date=date(2026, 11, 7),
        return_date=date(2026, 11, 14),
        pax=PaxConfig(key="1a", adults=1),
    )
    assert (
        q.cell_key == "google_flights:YQB-CDG:+None:1a"
        and q.search_key == "google_flights_YQB-CDG_2026-11-07_1a"
    )
