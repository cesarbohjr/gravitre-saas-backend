#!/usr/bin/env python3
"""QA90 replay of 16 deferred migrations on minimal isolated PostgreSQL fixtures.

This does NOT emulate the complete production schema and does not certify a
Supabase migration repair. It applies real SQL in timestamp order to a disposable
loopback-only PostgreSQL 17 database and checks material constraints, RLS and
service-only grants. Any failure is evidence, never silently skipped.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

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
BOOTSTRAP = """
do $$ begin
 if not exists(select 1 from pg_roles where rolname='anon') then create role anon nologin; end if;
 if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if;
 if not exists(select 1 from pg_roles where rolname='service_role') then create role service_role nologin; end if;
end $$;
create schema auth;
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create function auth.role() returns text language sql stable as $$ select 'service_role'::text $$;
create table public.organizations(id uuid primary key);
create table public.organization_members(org_id uuid, user_id uuid);
create table public.marketplace_assets(
 id uuid primary key, org_id uuid not null, asset_type text,
 status text, config jsonb
);
create table public.billing_plans(code text primary key, price_usd numeric);
insert into public.billing_plans values ('node',0),('control',0),('command',0);
create table public.connectors(
 id uuid primary key, type text,
 constraint connectors_type_check check
 (type = any(array['instantly'::text,'hubspot'::text]))
);
create table public.workflow_runs(
 id uuid primary key, org_id uuid, approval_status text,
 required_approvals integer, status text, workflow_id uuid,
 trigger_type text, run_type text, run_hash text, environment text,
 created_at timestamptz default now(), completed_at timestamptz,
 error_message text
);
create table public.runs(id uuid primary key, status text);
"""
PGDATABASE = "qa90_deferred_ordered"


def psql(database: str, sql: str, *, expect_failure: bool = False) -> str:
    env = os.environ.copy()
    if env.get("PGHOST") not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Refusing non-loopback database")
    cmd = ["psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-d", database]
    result = subprocess.run(cmd, input=sql, text=True, capture_output=True,
                            env=env, check=False, timeout=90)
    if expect_failure:
        assert result.returncode != 0, "Expected rejection, but PostgreSQL accepted operation"
        return result.stderr
    if result.returncode:
        raise AssertionError(f"SQL replay failed: {result.stderr[-2200:]}")
    return result.stdout.strip()


def main() -> None:
    psql("postgres", f"create database {PGDATABASE}")
    psql(PGDATABASE, BOOTSTRAP)
    observed = []
    for version in VERSIONS:
        sql = (ROOT / "supabase" / "migrations" / (version + ".sql")).read_text()
        # Each file is an independent atomic migration, preserving source order.
        env = os.environ.copy()
        assert env.get("PGHOST") in {"127.0.0.1", "localhost", "::1"}
        res = subprocess.run(["psql", "-X", "-q", "-1", "-v", "ON_ERROR_STOP=1",
                              "-d", PGDATABASE], input=sql, text=True,
                             capture_output=True, env=env, check=False, timeout=90)
        if res.returncode:
            raise AssertionError(f"Migration {version} failed: {res.stderr[-2200:]}")
        observed.append(version)
        print(f"APPLIED_IN_DISPOSABLE_DB {version}", flush=True)

    assert tuple(sorted(VERSIONS)) == VERSIONS
    assert observed == list(VERSIONS)
    prices = psql(PGDATABASE,
                  "select string_agg(code || ':' || price_usd::text, ',' order by code) from public.billing_plans")
    assert prices == "command:599,control:249,node:79", prices
    rls = psql(PGDATABASE, """select count(*) from pg_class c
        join pg_namespace n on n.oid=c.relnamespace
        where n.nspname='public' and c.relname in
        ('marketplace_outcome_pack_certifications','marketplace_outcome_pack_checks',
         'prospect_companies','prospect_contacts','prospect_staging',
         'prospect_play_runs','prospect_play_steps','prospect_outreach_events',
         'prospect_action_approvals','prospect_stage_approvals')
        and c.relrowsecurity""")
    assert rls == "10", f"Missing tenant RLS on expected tables: {rls}"
    assert psql(PGDATABASE,
        "select has_table_privilege('authenticated','public.prospect_companies','INSERT')") == "f"
    assert psql(PGDATABASE,
        "select has_function_privilege('anon','public.prospect_record_delivery_atomic(uuid,text,text,text,text,text)','EXECUTE')") == "f"
    assert psql(PGDATABASE,
        "select has_function_privilege('authenticated','public.claim_approved_autonomous_write(uuid,uuid,text,text,text,int)','EXECUTE')") == "f"
    # Ensure the final definition still verifies lead ownership rather than merely
    # trusting a provider's lead id/email. This was enforced by an earlier migration.
    final_delivery = psql(PGDATABASE, """select pg_get_functiondef(
        'public.prospect_record_delivery_atomic(uuid,text,text,text,text,text)'::regprocedure)""").lower()
    assert "prospect_outreach_lead_links" in final_delivery, (
        "SECURITY REGRESSION: final delivery function replaced tenant-owned lead verification")
    assert "recipient mismatch" in final_delivery, (
        "SECURITY REGRESSION: final delivery function does not reject mismatched recipient")
    # Tenant FK must reject contact linking to a company in another organization.
    psql(PGDATABASE, """insert into public.organizations(id) values
        ('00000000-0000-0000-0000-000000000001'),('00000000-0000-0000-0000-000000000002');
        insert into public.prospect_companies(
        id,org_id,domain,name,source_url,source_license) values (
        '00000000-0000-0000-0000-000000000101',
        '00000000-0000-0000-0000-000000000001',
        'example.test','Fixture','https://example.test','fixture')""")
    error = psql(PGDATABASE, """insert into public.prospect_contacts(
        org_id,company_id) values(
        '00000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000101')""", expect_failure=True)
    assert "foreign key" in error.lower(), error[-700:]
    # Negative and positive provider-free delivery checks on synthetic tenant data.
    # No connected vendor calls: only the disposable PostgreSQL function is invoked.
    missing = psql(PGDATABASE, """select public.prospect_record_delivery_atomic(
        '00000000-0000-0000-0000-000000000001','smartlead','evt-missing',
        'lead-missing','delivered','person@example.test')""", expect_failure=True)
    assert "tenant-owned contact mapping" in missing.lower(), missing[-700:]
    psql(PGDATABASE, """insert into public.prospect_contacts(
        id,org_id,company_id,email) values(
        '00000000-0000-0000-0000-000000000102',
        '00000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000101','person@example.test');
        insert into public.prospect_outreach_lead_links(org_id,provider,provider_lead_id,contact_id)
        values('00000000-0000-0000-0000-000000000001',
          'smartlead','lead-mapped','00000000-0000-0000-0000-000000000102')""")
    wrong_recipient = psql(PGDATABASE, """select public.prospect_record_delivery_atomic(
        '00000000-0000-0000-0000-000000000001','smartlead','evt-mismatch',
        'lead-mapped','delivered','wrong@example.test')""", expect_failure=True)
    assert "recipient mismatch" in wrong_recipient.lower(), wrong_recipient[-700:]
    wrong_tenant = psql(PGDATABASE, """select public.prospect_record_delivery_atomic(
        '00000000-0000-0000-0000-000000000002','smartlead','evt-cross-tenant',
        'lead-mapped','delivered','person@example.test')""", expect_failure=True)
    assert "tenant-owned contact mapping" in wrong_tenant.lower(), wrong_tenant[-700:]
    first = psql(PGDATABASE, """select public.prospect_record_delivery_atomic(
        '00000000-0000-0000-0000-000000000001','smartlead','evt-valid',
        'lead-mapped','delivered','PERSON@example.test')""")
    replay = psql(PGDATABASE, """select public.prospect_record_delivery_atomic(
        '00000000-0000-0000-0000-000000000001','smartlead','evt-valid',
        'lead-mapped','delivered','person@example.test')""")
    assert first == "t" and replay == "f", (first, replay)
    assert psql(PGDATABASE, "select count(*) from public.prospect_outreach_events") == "1"
    # A valid v2 status is admitted; an unsupported status is rejected.
    psql(PGDATABASE, """insert into public.runs(id,status)
        values('00000000-0000-0000-0000-000000000201','partial_success')""")
    error = psql(PGDATABASE, """insert into public.runs(id,status)
        values('00000000-0000-0000-0000-000000000202','unknown_status')""",
        expect_failure=True)
    assert "check constraint" in error.lower(), error[-700:]
    print(json.dumps({"result": "PASS", "migrations": len(observed),
        "scope": "isolated minimal-schema ordered replay; no Supabase or provider calls",
        "assertions": ["SQL execution order", "RLS", "function grants",
                       "ownership guard", "provider event negative/positive replay", "tenant foreign key",
                       "catalog prices", "v2 statuses"]}))


if __name__ == "__main__":
    main()
