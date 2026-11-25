#!/usr/bin/env python3
"""QA90: compare two known non-byte-identical migration pairs in disposable PG.

The remote SQL constants are frozen, *read-only* copies of the single-statement
migration entries from Supabase project smyeexlrqdpymwjmgzqu (2026-11-22).
This script never connects to Supabase. All psql connections must be loopback.
This is targeted DDL parity, NOT full migration-order or schema certification.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REMOTE = {
    "conversation_surface": """alter table public.conversations
  add column if not exists surface text;

alter table public.conversations
  drop constraint if exists conversations_surface_check;

alter table public.conversations
  add constraint conversations_surface_check
  check (surface is null or surface in ('web', 'desktop', 'extension', 'voice'));""",
    "add_smartlead_connector_type": """do $migration$
declare existing_definition text; updated_definition text;
begin
 select pg_get_constraintdef(c.oid) into existing_definition from pg_constraint c where c.conrelid='public.connectors'::regclass and c.conname='connectors_type_check' and c.contype='c';
 if existing_definition is null then raise exception 'connectors_type_check is missing'; end if;
 if position('''smartlead''::text' in existing_definition)>0 then return; end if;
 if position('''instantly''::text' in existing_definition)=0 then raise exception 'unexpected connector type allowlist'; end if;
 updated_definition=replace(existing_definition,'''instantly''::text','''instantly''::text, ''smartlead''::text');
 alter table public.connectors drop constraint connectors_type_check;
 execute format('alter table public.connectors add constraint connectors_type_check %s',updated_definition);
end $migration$;""",
}
LOCAL = {
    "conversation_surface": "supabase/migrations/20261026200000_conversation_surface.sql",
    "add_smartlead_connector_type": "supabase/migrations/20261025170000_add_smartlead_connector_type.sql",
}
INIT = {
    "conversation_surface": "create table public.conversations (id uuid primary key);",
    "add_smartlead_connector_type": """create table public.connectors (
      id uuid, type text,
      constraint connectors_type_check
      check (type = any (array['instantly'::text, 'hubspot'::text]))
    );""",
}
SNAPSHOT = {
    "conversation_surface": """select json_build_object(
      'type', (select data_type from information_schema.columns
               where table_schema='public' and table_name='conversations'
               and column_name='surface'),
      'check', (select pg_get_constraintdef(oid) from pg_constraint
                where conrelid='public.conversations'::regclass
                and conname='conversations_surface_check')
    )::text;""",
    "add_smartlead_connector_type": """select pg_get_constraintdef(oid)
      from pg_constraint
      where conrelid='public.connectors'::regclass
        and conname='connectors_type_check';""",
}


def psql(database: str, sql: str, *, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    host = env.get("PGHOST", "")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Refusing any non-loopback PostgreSQL host")
    args = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-At", "-d", database]
    outcome = subprocess.run(args, input=sql, text=True, capture_output=True, env=env, check=False)
    if outcome.returncode and not allow_failure:
        raise AssertionError(f"psql operation failed: {outcome.stderr[-1800:]}")
    return outcome


def main() -> None:
    for name in REMOTE:
        results = {}
        for kind in ("remote", "repo"):
            db = f"qa90_{name}_{kind}"
            if len(db) > 63:
                raise ValueError("Database identifier too long")
            psql("postgres", f"create database {db};")
            psql(db, INIT[name])
            source = REMOTE[name] if kind == "remote" else (ROOT / LOCAL[name]).read_text()
            psql(db, source)
            first = psql(db, SNAPSHOT[name]).stdout.strip()
            assert first, f"{name}/{kind}: empty DDL snapshot"
            psql(db, source)  # idempotence, including duplicate type guard
            second = psql(db, SNAPSHOT[name]).stdout.strip()
            assert first == second, f"{name}/{kind}: non-idempotent DDL"
            results[kind] = second
        assert results["remote"] == results["repo"], f"{name}: schema divergence"
        if name == "add_smartlead_connector_type":
            assert "smartlead" in results["repo"] and "instantly" in results["repo"]
        if name == "conversation_surface":
            assert "surface" not in results["repo"] or "text" in results["repo"]
        print(json.dumps({"migration": name, "ddl_parity": "PASS", "idempotent": True,
                          "scope": "disposable loopback PostgreSQL"}))
    print("QA90 bounded DDL parity PASS (2 pairs; no Supabase connections)")


if __name__ == "__main__":
    main()
