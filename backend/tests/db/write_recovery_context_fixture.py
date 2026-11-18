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


class PgRecoveryClient:
    """Minimal service-role Supabase transport for actual recovery SQL.

    Does not emulate ledger state. All claim, lease, settlement, and scoped
    reads are executed against the same disposable PostgreSQL instance.
    """

    def __init__(self, pg):
        self.pg = pg

    def _connect(self):
        connection = psycopg.connect(
            host=str(self.pg.sock), port=self.pg.port,
            dbname="postgres", user="postgres",
        )
        connection.execute("SET ROLE service_role")
        connection.execute("SET request.jwt.claim.role = 'service_role'")
        return connection

    def rpc(self, name, params):
        if name == "claim_due_write_recoveries":
            statement = (
                "SELECT coalesce(json_agg(r), '[]'::json) "
                "FROM public.claim_due_write_recoveries(%s) r"
            )
            values = (params["p_limit"],)
        elif name == "settle_leased_write_recovery":
            statement = (
                "SELECT public.settle_leased_write_recovery("
                "%s::uuid,%s,%s::uuid,%s,%s)"
            )
            values = (
                params["p_org_id"], params["p_key"], params["p_lease_token"],
                params["p_status"], Jsonb(params["p_result"]),
            )
        elif name == "defer_leased_write_recovery":
            statement = (
                "SELECT public.defer_leased_write_recovery(%s::uuid,%s,%s::uuid)"
            )
            values = (
                params["p_org_id"], params["p_key"], params["p_lease_token"],
            )
        else:
            raise AssertionError("unrecognized recovery RPC: " + str(name))

        pg_client = self

        class Call:
            def execute(self):
                from types import SimpleNamespace
                with pg_client._connect() as conn:
                    row = conn.execute(statement, values).fetchone()
                return SimpleNamespace(data=row[0])

        return Call()

    def table(self, name):
        if name != "write_invoke_idempotency":
            raise AssertionError("unexpected ledger table " + str(name))
        pg_client = self

        class Query:
            def __init__(self):
                self.filters = {}
                self.limit_value = 1

            def select(self, columns):
                if columns != "*":
                    raise AssertionError("only full persisted ledger rows supported")
                return self

            def eq(self, column, value):
                if column not in ("org_id", "idempotency_key"):
                    raise AssertionError("unexpected ledger scope: " + str(column))
                self.filters[column] = value
                return self

            def limit(self, count):
                self.limit_value = count
                return self

            def execute(self):
                from types import SimpleNamespace
                if set(self.filters) != {"org_id", "idempotency_key"}:
                    raise AssertionError("tenant and key scope must both be supplied")
                with pg_client._connect() as conn:
                    records = conn.execute(
                        "SELECT org_id::text, idempotency_key, invoke_action,"
                        " connector_id, original_args, status,"
                        " recovery_lease_token::text FROM public.write_invoke_idempotency"
                        " WHERE org_id=%s::uuid AND idempotency_key=%s LIMIT %s",
                        (self.filters["org_id"], self.filters["idempotency_key"],
                         self.limit_value),
                    ).fetchall()
                columns = ("org_id", "idempotency_key", "invoke_action",
                           "connector_id", "original_args", "status",
                           "recovery_lease_token")
                return SimpleNamespace(data=[dict(zip(columns, row)) for row in records])

        return Query()
