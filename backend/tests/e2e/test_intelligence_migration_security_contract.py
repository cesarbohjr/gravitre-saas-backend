"""Offline migration safety contract: every new multi-tenant table fail-closed."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
SCHEMAS = {
    "20261026160000_intelligence_history_and_entity_matches.sql": [
        "intelligence_history_checkpoints", "intelligence_history_records", "intelligence_entity_matches",
    ],
    "20261026180000_intelligence_recommendation_play_links.sql": [
        "intelligence_recommendation_play_links",
    ],
    "20261026190000_intelligence_sweep_atomic_metering.sql": [
        "intelligence_sweep_usage_ledger",
    ],
}


def test_all_intelligence_tables_have_org_fk_rls_and_no_client_grants():
    for filename, tables in SCHEMAS.items():
        sql = (ROOT / filename).read_text().lower()
        for table in tables:
            assert f"create table if not exists public.{table}" in sql
            assert f"alter table public.{table} enable row level security" in sql
            assert re.search(
                rf"revoke all on public\.{table} from anon\s*,\s*authenticated", sql
            )
        assert "references public.organizations(id)" in sql


def test_legacy_unmetered_service_role_admission_revoked():
    sql = (ROOT / "20261026190000_intelligence_sweep_atomic_metering.sql").read_text().lower()
    assert "revoke execute on function public.admit_intelligence_overview_sweep" in sql
    assert "from service_role" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "intelligence_sweep_usage_ledger" in sql
    assert "grant execute on function public.admit_metered_intelligence_sweep" in sql
    assert "grant execute on function public.settle_intelligence_sweep_unit" in sql
    assert sql.count("create or replace function public.admit_metered_intelligence_sweep") == 1
    assert sql.count("create or replace function public.settle_intelligence_sweep_unit") == 1
