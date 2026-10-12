"""Contract for 20261011192411_phase1_security_rls.sql (statically checked; applied twice on PG16 in review)."""
from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20261011192411_phase1_security_rls.sql"
)
MEMBERSHIP = "org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _statements() -> str:
    return "\n".join(line for line in _sql().splitlines() if not line.lstrip().startswith("--"))


def test_rls_enabled_and_anon_revoked_on_exposed_tables() -> None:
    sql = _statements()
    for table in ("agent_custom_voices", "billing_topup_events", "webhook_event_receipts"):
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in sql
        assert re.search(rf"REVOKE ALL ON public\.{table} FROM anon", sql)


def test_org_policies_use_multi_org_membership_predicate() -> None:
    sql = _statements()
    for policy in (
        "agent_custom_voices_org_select",
        "billing_topup_events_org_select",
        "work_objects_org",
        "work_object_events_org",
        "agent_memories_org",
        "agent_memory_history_org",
    ):
        assert f'DROP POLICY IF EXISTS "{policy}"' in sql
        body = sql.split(f'CREATE POLICY "{policy}"', 1)[1].split(";", 1)[0]
        assert MEMBERSHIP in body
    assert "LIMIT 1" not in sql


def test_receipts_table_and_approval_column_are_idempotent() -> None:
    sql = _statements()
    assert "CREATE TABLE IF NOT EXISTS public.webhook_event_receipts" in sql
    assert "PRIMARY KEY (org_id, provider, event_id)" in sql
    assert "ADD COLUMN IF NOT EXISTS consumed_at timestamptz" in sql
    assert not re.search(r"\bDROP\s+(TABLE|COLUMN)\b", sql, flags=re.IGNORECASE)
    assert "CREATE POLICY" not in sql.split("public.webhook_event_receipts", 1)[1]
