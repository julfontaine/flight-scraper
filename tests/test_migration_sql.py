from __future__ import annotations

import re
from pathlib import Path

import pglast
from pglast import ast, enums

MIGRATION = Path(__file__).parent.parent / "supabase" / "migrations" / "0001_init.sql"


def test_migration_parses():
    sql = MIGRATION.read_text(encoding="utf-8")
    stmts = pglast.parse_sql(sql)
    assert len(stmts) > 20


def _statements():
    return [s.stmt for s in pglast.parse_sql(MIGRATION.read_text(encoding="utf-8"))]


def test_tables_views_and_policies_present():
    stmts = _statements()
    tables = {s.relation.relname for s in stmts if isinstance(s, ast.CreateStmt)}
    assert tables == {"sources", "routes", "search_runs", "searches", "itineraries"}
    views = {s.view.relname for s in stmts if isinstance(s, ast.ViewStmt)}
    assert views == {"latest_prices", "latest_prices_by_offset", "cell_last_scraped"}
    policies = [s for s in stmts if isinstance(s, ast.CreatePolicyStmt)]
    assert len(policies) == 1 and policies[0].table.relname == "itineraries"
    rls = {
        s.relation.relname
        for s in stmts
        if isinstance(s, ast.AlterTableStmt)
        and any(c.subtype == enums.AlterTableType.AT_EnableRowSecurity for c in s.cmds)
    }
    assert rls == tables


def test_seed_rows_and_natural_key():
    sql = MIGRATION.read_text(encoding="utf-8")
    for source in (
        "google_flights",
        "westjet",
        "air_canada",
        "kayak",
        "air_transat",
        "skyscanner",
        "porter",
        "flair",
        "expedia",
    ):
        assert f"('{source}'," in sql
    assert re.search(r"unnest\(array\['YQB', 'YUL'\]\)", sql)
    assert (
        "(source_id, route_id, depart_date, return_date, adults, children, child_ages, cabin, scrape_date)"
        in sql
    )
    assert "unique (search_id, pick)" in sql
    assert "child_ages   smallint[] not null default '{}'" in sql
