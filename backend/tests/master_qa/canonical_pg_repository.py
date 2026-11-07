"""Disposable canonical workflow persistence harness.

The SQL backend is actual local PostgreSQL; only the Supabase PostgREST
transport is replaced with a narrow psycopg table client. Production repository
functions remain unpatched. This is an offline test harness, never a provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tests.db.pg_harness import MIGRATIONS, pg_cluster
from tests.db.test_domain_event_outbox_pg import (
    BOOTSTRAP_SQL, MIGRATION, CLAIM_TYPES_MIGRATION, ORG, USER,
)

# Add legacy columns required by production create_execute_run, plus the
# canonical run / step mirrors written by schema_sync. No production migrations
# are applied or changed here. The real outbox migrations run unchanged.
CANONICAL_SCHEMA = """
ALTER TABLE public.workflow_runs
 ADD COLUMN run_type text,
 ADD COLUMN triggered_by text,
 ADD COLUMN definition_snapshot jsonb,
 ADD COLUMN run_hash text,
 ADD COLUMN required_approvals integer,
 ADD COLUMN approver_roles jsonb,
 ADD COLUMN environment text DEFAULT 'synthetic',
 ADD COLUMN trigger_type text,
 ADD COLUMN approval_status text,
 ADD COLUMN workflow_version_id uuid,
 ADD COLUMN started_at timestamptz,
 ADD COLUMN duration_ms integer,
 ADD COLUMN error_message text;
CREATE TABLE public.workflow_steps (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL,
 run_id uuid NOT NULL REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
 step_id text NOT NULL,
 step_index integer NOT NULL,
 step_name text,
 step_type text,
 status text NOT NULL,
 output_snapshot jsonb,
 input_snapshot jsonb,
 logs text,
 error_code text,
 error_message text,
 is_retryable boolean DEFAULT false,
 started_at timestamptz,
 completed_at timestamptz
);
CREATE TABLE public.run_approvals (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL,
 run_id uuid NOT NULL REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
 approver_id text NOT NULL,
 status text NOT NULL,
 comment text,
 UNIQUE(run_id,approver_id)
);
CREATE TABLE public.workflows (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, name text
);
CREATE TABLE public.workflow_defs (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, name text
);
CREATE TABLE public.runs (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, workflow_id uuid,
 workflow_name text, status text, trigger text, approval_status text,
 started_at timestamptz, completed_at timestamptz, duration_ms integer,
 error_message text, metadata jsonb, updated_at timestamptz
);
CREATE TABLE public.play_runs (
 id uuid PRIMARY KEY, org_id uuid NOT NULL,
 installation_id text, play_key text, play_version text,
 operating_mode text, trigger_type text, status text,
 workflow_run_ids jsonb, created_by text,
 started_at timestamptz, metadata jsonb
);
CREATE TABLE public.run_steps (
 id uuid PRIMARY KEY, org_id uuid NOT NULL, run_id uuid NOT NULL,
 name text, status text, order_index integer, started_at timestamptz,
 completed_at timestamptz, duration_ms integer, logs jsonb,
 metadata jsonb, updated_at timestamptz
);
"""

def _serializable(value):
    if isinstance(value, (UUID, datetime, date)):
        return str(value)
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serializable(v) for v in value]
    return value


def _bind(value):
    return Jsonb(value) if isinstance(value, (dict, list)) else value


@dataclass
class Response:
    data: list[dict]


class PgTable:
    def __init__(self, pg, name):
        assert name in {
            "workflow_runs", "workflow_steps", "run_approvals", "play_runs",
            "workflows", "workflow_defs", "runs", "run_steps",
        }, name
        self.pg = pg
        self.name = name
        self.verb = "select"
        self.columns = "*"
        self.filters = []
        self.payload = None
        self.limit_n = None
        self.order_col = None
        self.order_desc = False
        self.conflict = "id"

    def select(self, columns="*"):
        self.verb, self.columns = "select", columns
        return self

    def insert(self, payload):
        self.verb, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.verb, self.payload = "update", payload
        return self

    def upsert(self, payload, on_conflict="id"):
        self.verb, self.payload, self.conflict = "upsert", payload, on_conflict
        return self

    def eq(self, name, value):
        self.filters.append((name, value))
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def order(self, column, desc=False):
        self.order_col, self.order_desc = column, desc
        return self

    def execute(self):
        table = sql.Identifier("public", self.name)
        args = []
        if self.verb == "select":
            # Supabase .select accepts comma separated names, not raw SQL.
            cols = sql.SQL("*") if self.columns == "*" else sql.SQL(",").join(
                sql.Identifier(x.strip()) for x in self.columns.split(","))
            stmt = sql.SQL("SELECT {} FROM {}").format(cols, table)
        elif self.verb in {"insert", "upsert"}:
            records = self.payload if isinstance(self.payload, list) else [self.payload]
            if not records:
                return Response([])
            cols = list(records[0])
            placeholders = sql.SQL(",").join(
                sql.SQL("(") + sql.SQL(",").join(sql.Placeholder() for _ in cols) + sql.SQL(")")
                for _ in records)
            stmt = sql.SQL("INSERT INTO {} ({}) VALUES {}").format(
                table, sql.SQL(",").join(map(sql.Identifier, cols)), placeholders)
            args = [_bind(record.get(k)) for record in records for k in cols]
            if self.verb == "upsert":
                updates = sql.SQL(",").join(
                    sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(k), sql.Identifier(k))
                    for k in cols if k != self.conflict)
                stmt += sql.SQL(" ON CONFLICT ({}) DO UPDATE SET {}").format(
                    sql.Identifier(self.conflict), updates)
            stmt += sql.SQL(" RETURNING *")
        elif self.verb == "update":
            stmt = sql.SQL("UPDATE {} SET {}").format(
                table, sql.SQL(",").join(
                    sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder())
                    for k in self.payload))
            args = [_bind(v) for v in self.payload.values()]
        else:
            raise AssertionError(self.verb)
        if self.filters:
            stmt += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(
                sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder())
                for k, _ in self.filters)
            args.extend(_bind(v) for _, v in self.filters)
        if self.order_col and self.verb == "select":
            stmt += sql.SQL(" ORDER BY {} {}").format(
                sql.Identifier(self.order_col),
                sql.SQL("DESC" if self.order_desc else "ASC"))
        if self.limit_n and self.verb == "select":
            stmt += sql.SQL(" LIMIT {}").format(sql.Placeholder())
            args.append(self.limit_n)
        if self.verb == "update":
            stmt += sql.SQL(" RETURNING *")
        with psycopg.connect(
            host=str(self.pg.sock), port=self.pg.port, dbname="postgres", user="postgres",
            row_factory=dict_row,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(stmt, args)
                result = [_serializable(row) for row in cur.fetchall()]
        return Response(result)


class PgRepositoryClient:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return PgTable(self.pg, name)


def canonical_pg_cluster():
    return pg_cluster(
        BOOTSTRAP_SQL,
        CANONICAL_SCHEMA,
        MIGRATION.read_text(),
        CLAIM_TYPES_MIGRATION.read_text(),
        (MIGRATIONS / "20261107235500_p27_graph_recovery_leases.sql").read_text(),
    )
