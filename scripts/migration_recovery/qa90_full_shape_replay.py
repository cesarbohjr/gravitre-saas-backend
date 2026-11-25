#!/usr/bin/env python3
"""QA90 production-shaped *disposable* PostgreSQL migration and rollback proof.

Expects a separately restored data-free, verified baseline in a scratch database.
Never reads production data or connects outside loopback. Schema is never modified
until the independent baseline has been restored into the scratch database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = (
    "20261002030000_marketplace_3_certification_evidence",
    "20261022230000_billing_plans_october_list_prices",
    "20261024191000_prospecting_play_tables",
    "20261024202500_prospecting_credit_reservations",
    "20261024213000_prospecting_staging",
    "20261025010000_prospect_play_execution",
    "20261025020000_prospect_atomic_runtime",
    "20261025023000_prospect_delivery_ownership",
    "20261025120000_prospect_action_approvals",
    "20261025184500_prospect_atomic_claim",
    "20261025190000_qualified_prospecting_connector_types",
    "20261025192000_prospect_approval_resolution",
    "20261025202000_prospect_atomic_finish",
    "20261025213000_prospect_atomic_delivery",
    "20261102095000_autonomous_atomic_write_claim",
    "20261105090000_run_status_contract_v2",
)

# Public schema catalog including roles/grants, triggers, RLS, functions, indexes,
# constraints, policies, columns and current table definitions. This checks that
# all such recorded state survives the intentional aborted transaction unchanged.
CATALOG = """
select jsonb_build_object(
 'relations', (select coalesce(jsonb_agg(jsonb_build_array(
   c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity,c.relacl)
   order by c.relname), '[]'::jsonb)
   from pg_class c join pg_namespace n on n.oid=c.relnamespace
   where n.nspname='public' and c.relkind in ('r','p','v','m','S','f')),
 'columns', (select coalesce(jsonb_agg(jsonb_build_array(
   table_name,column_name,data_type,udt_name,is_nullable,column_default)
   order by table_name,ordinal_position), '[]'::jsonb)
   from information_schema.columns where table_schema='public'),
 'constraints', (select coalesce(jsonb_agg(jsonb_build_array(
   c.conname,c.conrelid::regclass::text,pg_get_constraintdef(c.oid))
   order by c.conrelid::regclass::text,c.conname), '[]'::jsonb)
   from pg_constraint c join pg_namespace n on n.oid=c.connamespace
   where n.nspname='public'),
 'indexes', (select coalesce(jsonb_agg(jsonb_build_array(
   tablename,indexname,indexdef) order by tablename,indexname), '[]'::jsonb)
   from pg_indexes where schemaname='public'),
 'policies', (select coalesce(jsonb_agg(jsonb_build_array(
   tablename,policyname,roles,cmd,qual,with_check)
   order by tablename,policyname), '[]'::jsonb)
   from pg_policies where schemaname='public'),
 'functions', (select coalesce(jsonb_agg(jsonb_build_array(
   p.oid::regprocedure::text,pg_get_functiondef(p.oid),p.proacl)
   order by p.oid::regprocedure::text), '[]'::jsonb)
   from pg_proc p join pg_namespace n on n.oid=p.pronamespace
   where n.nspname='public' and p.prokind in ('f','p')),
 'triggers', (select coalesce(jsonb_agg(jsonb_build_array(
   c.relname,t.tgname,pg_get_triggerdef(t.oid))
   order by c.relname,t.tgname), '[]'::jsonb)
   from pg_trigger t join pg_class c on c.oid=t.tgrelid
   join pg_namespace n on n.oid=c.relnamespace
   where n.nspname='public' and not t.tgisinternal)
)::text
"""


def assert_loopback(url: str) -> None:
    u = urlsplit(url)
    if (u.scheme not in ("postgresql", "postgres")
        or u.hostname not in ("127.0.0.1", "localhost", "::1")
        or u.query or u.fragment):
        raise ValueError("Only loopback PostgreSQL database URLs allowed")
    if u.path != "/postgres":
        raise ValueError("Only the disposable local Supabase postgres database is permitted")


def fingerprint(conn: psycopg.Connection) -> str:
    value = conn.execute(CATALOG).fetchone()[0]
    return hashlib.sha256(value.encode()).hexdigest()


def verify(conn: psycopg.Connection) -> None:
    assert conn.execute("select to_regclass('public.organizations')").fetchone()[0], "Missing production-shaped baseline"
    assert conn.execute("select to_regclass('public.marketplace_assets')").fetchone()[0], "Missing marketplace schema"
    assert conn.execute("select to_regclass('public.workflow_runs')").fetchone()[0], "Missing workflow schema"
    assert conn.execute("select to_regclass('public.runs')").fetchone()[0], "Missing v2 mirror target"
    definition = conn.execute("""select pg_get_functiondef(
       'public.prospect_record_delivery_atomic(uuid,text,text,text,text,text)'::regprocedure)""").fetchone()[0].lower()
    assert "prospect_outreach_lead_links" in definition, "Security regression: lost tenant-owned lead lookup"
    assert "recipient mismatch" in definition, "Security regression: lost recipient mismatch block"
    assert conn.execute("select relrowsecurity from pg_class where oid='public.prospect_contacts'::regclass").fetchone()[0]
    assert not conn.execute("""select has_function_privilege(
      'authenticated', 'public.prospect_record_delivery_atomic(uuid,text,text,text,text,text)', 'execute')""").fetchone()[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    assert_loopback(args.database_url)
    assert tuple(sorted(VERSIONS)) == VERSIONS
    result = {"scope": "disposable local Supabase PG17, restored production-shape data-free schema",
              "versions": list(VERSIONS), "applied": [], "rollback_verified": False,
              "passed": False, "no_remote_mutations": True}
    try:
        with psycopg.connect(args.database_url) as conn:
            conn.autocommit = True
            before = fingerprint(conn)
            result["before_schema_sha256"] = before
            # Attempt all migrations in one transaction and abort deliberately.
            # PostgreSQL must roll back every DDL and data effect.
            try:
                with conn.transaction():
                    for name in VERSIONS:
                        sql = (ROOT / "supabase/migrations" / f"{name}.sql").read_text()
                        conn.execute(sql, prepare=False)
                    verify(conn)
                    raise RuntimeError("QA90_EXPECTED_ABORT")
            except RuntimeError as exc:
                if str(exc) != "QA90_EXPECTED_ABORT":
                    raise
            after_rollback = fingerprint(conn)
            result["after_rollback_schema_sha256"] = after_rollback
            assert before == after_rollback, "Rollback altered catalog: baseline lost"
            result["rollback_verified"] = True

            # Positive execution/compatibility pass; deliberately abort this
            # transaction too so the verified recovery baseline remains intact.
            try:
                with conn.transaction():
                    for name in VERSIONS:
                        conn.execute((ROOT / "supabase/migrations" / f"{name}.sql").read_text(),
                                     prepare=False)
                        result["applied"].append(name)
                    verify(conn)
                    result["after_application_schema_sha256"] = fingerprint(conn)
                    assert len(result["applied"]) == 16
                    raise RuntimeError("QA90_EXPECTED_POSITIVE_ROLLBACK")
            except RuntimeError as exc:
                if str(exc) != "QA90_EXPECTED_POSITIVE_ROLLBACK":
                    raise
            assert fingerprint(conn) == before, "Post-positive rollback changed baseline"
            result["passed"] = True
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "applied": len(result["applied"]),
                      "rollback_verified": result["rollback_verified"],
                      "scope": result["scope"]}))


if __name__ == "__main__":
    main()
