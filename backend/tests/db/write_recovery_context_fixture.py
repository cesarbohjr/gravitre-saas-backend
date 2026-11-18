"""PostgreSQL-only acceptance adapter for fenced write recovery context.

Used by joined Chat and Agent tests; the production RPC and permissions are
not patched out. Only the Supabase transport is replaced with psycopg.
"""
from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from tests.db.pg_harness import MIGRATIONS

AUTH_ROLE_SQL = """CREATE OR REPLACE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE AS 'SELECT nullif(current_setting(''request.jwt.claim.role'', true), '''')';
"""
CONTEXT_SQL = (MIGRATIONS / "20261118030000_write_recovery_context.sql").read_text()


def bind_recovery_context(
    pg, *, org_id: str, idempotency_key: str, claim_token: str,
    invoke_action: str, connector_id: str, original_args: dict,
) -> bool:
    """Call the service-role-only RPC with parameterized inputs."""
    if not connector_id or not isinstance(original_args, dict):
        return False
    with psycopg.connect(
        host=str(pg.sock), port=pg.port, dbname="postgres", user="postgres",
    ) as conn:
        conn.execute("SET ROLE service_role")
        conn.execute("SET request.jwt.claim.role = 'service_role'")
        row = conn.execute(
            "SELECT public.bind_write_recovery_context("
            "%s::uuid, %s, %s::uuid, %s, %s, %s)",
            (org_id, idempotency_key, claim_token, invoke_action,
             connector_id, Jsonb(original_args)),
        ).fetchone()
        return isinstance(row[0], dict) and row[0].get("outcome") == "bound"
