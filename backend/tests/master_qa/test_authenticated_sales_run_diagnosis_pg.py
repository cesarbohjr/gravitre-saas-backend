"""Offline read-only diagnosis backed by actual disposable PostgreSQL rows.

Uses the production repository query shape against a SQL-backed client.
Synthetic provider snapshots are not live HubSpot acceptance.
"""
from __future__ import annotations

import json
import re

import pytest

from tests.db.pg_harness import pg_cluster, requires_pg
from app.workflows.sales_growth_recipe import diagnose_authenticated_sales_run

pytestmark = requires_pg

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "33333333-3333-4333-8333-333333333333"
WF = "22222222-2222-4222-8222-222222222222"
RUN = "44444444-4444-4444-8444-444444444444"

_SCHEMA = """
CREATE TABLE public.workflow_runs (
    id uuid PRIMARY KEY, org_id uuid NOT NULL, environment text NOT NULL,
    workflow_id uuid NOT NULL, run_type text NOT NULL, status text NOT NULL,
    definition_snapshot jsonb NOT NULL
);
CREATE TABLE public.workflow_steps (
    id uuid PRIMARY KEY, run_id uuid NOT NULL,
    org_id uuid NOT NULL, step_id text NOT NULL, step_index int,
    status text NOT NULL, completed_at timestamptz,
    output_snapshot jsonb NOT NULL
);
CREATE TABLE public.workflows (
    id uuid PRIMARY KEY, org_id uuid NOT NULL, name text NOT NULL
);
CREATE TABLE public.workflow_defs (
    id uuid PRIMARY KEY, org_id uuid NOT NULL,
    name text NOT NULL, goal text NOT NULL
);
"""

_RUN_SNAPSHOT = json.dumps({"schema_version": "2025.1", "steps": [{
    "id": "sales-evidence-1", "type": "invoke_tool",
    "config": {"action": "hubspot.deals.search", "max_records": 250},
}]})
_STEP_SNAPSHOT = json.dumps({
    "invoke_action": "hubspot.deals.search", "success": True,
    "results": [{"id": "sample-deal"}],
    "coverage": {"complete": True, "returned": 1, "total_reported": 1},
})


class SqlQuery:
    def __init__(self, pg, table):
        assert table in {"workflow_runs", "workflow_steps", "workflows", "workflow_defs"}
        self.pg, self.table = pg, table
        self.filters = []
        self.max_rows = None
        self.order_by = None

    def select(self, *fields):
        return self

    def eq(self, key, value):
        assert key in {"id", "org_id", "environment", "run_id"}
        assert re.fullmatch(r"[a-zA-Z0-9_-]+", str(value))
        self.filters.append(f"{key} = '{value}'")
        return self

    def order(self, key, *args, **kwargs):
        assert key == "step_index"
        self.order_by = key
        return self

    def limit(self, count):
        self.max_rows = count
        return self

    def execute(self):
        sql = f"SELECT coalesce(json_agg(t), '[]'::json) FROM (SELECT * FROM public.{self.table}"
        if self.filters:
            sql += " WHERE " + " AND ".join(self.filters)
        if self.order_by:
            sql += " ORDER BY " + self.order_by
        if self.max_rows is not None:
            sql += " LIMIT " + str(int(self.max_rows))
        sql += ") t;"
        return type("Response", (), {"data": json.loads(self.pg.value(sql))})()


class SqlClient:
    def __init__(self, pg):
        self.pg = pg

    def table(self, table):
        return SqlQuery(self.pg, table)


@pytest.fixture
def db():
    with pg_cluster(_SCHEMA) as pg:
        pg.psql(
            f"INSERT INTO public.workflow_defs VALUES ('{WF}', '{ORG_A}',"
            " 'Sales growth diagnostic', 'Increase pipeline');"
            f"INSERT INTO public.workflow_runs VALUES ('{RUN}', '{ORG_A}', 'synthetic',"
            f" '{WF}', 'execute', 'completed', '{_RUN_SNAPSHOT}'::jsonb);"
            f"INSERT INTO public.workflow_steps VALUES "
            f"('55555555-5555-4555-8555-555555555555', '{RUN}', '{ORG_A}', "
            f"'sales-evidence-1', 0, 'completed', '2026-11-08T20:00:00Z',"
            f" '{_STEP_SNAPSHOT}'::jsonb);"
        )
        yield pg


def test_actual_persisted_sql_run_and_step_are_read_by_canonical_repository(db):
    response = diagnose_authenticated_sales_run(
        client=SqlClient(db), org_id=ORG_A, environment_name="synthetic", run_id=RUN,
    )
    assert response["diagnosis"]["status"] == "OBSERVATIONS_AVAILABLE"
    assert response["diagnosis"]["observations"][0]["value"] == 1.0
    assert response["diagnosis"]["business_outcome"] == "NOT_MEASURED"
    assert response["diagnosis"]["recommended_writes"] == []
    assert db.value("SELECT count(*) FROM public.workflow_runs") == "1"
    assert db.value("SELECT count(*) FROM public.workflow_steps") == "1"


def test_sql_tenant_and_environment_fences_deny_reads(db):
    client = SqlClient(db)
    assert diagnose_authenticated_sales_run(
        client=client, org_id=ORG_B, environment_name="synthetic", run_id=RUN,
    ) is None
    assert diagnose_authenticated_sales_run(
        client=client, org_id=ORG_A, environment_name="production", run_id=RUN,
    ) is None
