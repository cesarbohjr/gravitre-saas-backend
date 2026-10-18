"""Static regression contracts for atomic MSP grant/revoke audit wiring.

These do not replace live two-tenant integration tests.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "supabase/migrations/20261017230000_msp_delegation_atomic_audit.sql").read_text()
ROUTER = (ROOT / "backend/app/routers/msp_delegations.py").read_text()


def test_migration_has_valid_function_delimiters_and_transaction():
    assert SQL.count("AS $$\n") == 1
    assert SQL.count("AS $tag$") == 1
    assert SQL.count("\n$$;") == 1
    assert SQL.count("$tag$;") == 1
    assert SQL.startswith("-- Atomic audit:")
    assert "BEGIN;" in SQL and SQL.rstrip().endswith("COMMIT;")


def test_grant_audit_is_database_triggered():
    assert "AFTER INSERT OR UPDATE OF revoked_at" in SQL
    assert "RAISE EXCEPTION 'Missing trusted MSP revocation actor'" in SQL
    assert "'grant.created'" in SQL and "'grant.revoked'" in SQL
    assert "client.table(\"msp_delegation_audit\").insert" not in ROUTER


def test_revoke_uses_atomic_rpc_not_separate_update():
    assert 'client.rpc("msp_revoke_delegation_atomic"' in ROUTER
    assert 'client.table("msp_delegations").update' not in ROUTER
    assert "GRANT EXECUTE ON FUNCTION public.msp_revoke_delegation_atomic(uuid,uuid,uuid) TO service_role" in SQL
    assert "REVOKE ALL ON FUNCTION public.msp_revoke_delegation_atomic(uuid,uuid,uuid) FROM PUBLIC, anon, authenticated" in SQL


def test_no_customer_parent_access_grants():
    assert "auth_org_accessible" not in SQL
    assert "CREATE POLICY" not in SQL.upper()
