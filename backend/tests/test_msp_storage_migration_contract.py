"""Static safety contract for the MSP storage migration.

These checks prevent a future cleanup from accidentally widening database
access. Live authenticated Supabase tests are still required before release.
"""
from pathlib import Path

SQL = (
    Path(__file__).resolve().parents[2]
    / "supabase/migrations/20261017220000_msp_delegations_restricted.sql"
).read_text(encoding="utf-8").lower()


def test_tables_restricted_to_service_role():
    for table in ("msp_delegations", "msp_delegation_audit"):
        assert f"alter table public.{table} enable row level security" in SQL
        assert f"alter table public.{table} force row level security" in SQL
        assert f"revoke all on public.{table} from public, anon, authenticated" in SQL


def test_no_parent_access_grants_or_definer_bypass():
    assert "create policy" not in SQL
    assert "grant select, insert, update on public.msp_delegations to service_role" in SQL
    assert "grant select, insert on public.msp_delegation_audit to service_role" in SQL
    assert "security definer" not in "\n".join(
        line for line in SQL.splitlines() if not line.lstrip().startswith("--")
    )


def test_grants_are_scoped_revocable_and_expiring():
    for required in (
        "provider_org_id uuid not null",
        "customer_org_id uuid not null",
        "grantee_user_id uuid not null",
        "approved_by_customer_user_id uuid not null",
        "expires_at timestamptz not null",
        "revoked_at timestamptz",
        "check (provider_org_id <> customer_org_id)",
    ):
        assert required in SQL
