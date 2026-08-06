#!/usr/bin/env python3
"""Phase 0 helper: probe / apply RLS via Supabase Management API."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REF = os.environ.get("SUPABASE_PROJECT_REF", "smyeexlrqdpymwjmgzqu")


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (
        ROOT / "backend" / ".env.operator.local",
        ROOT / "backend" / ".env",
        ROOT / ".env",
    ):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    return merged


def run_sql(token: str, query: str) -> list | dict:
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=120,
    )
    if r.status_code >= 400:
        raise SystemExit(f"SQL API {r.status_code}: {r.text[:2000]}")
    data = r.json()
    return data


def main() -> int:
    env = load_env()
    token = env.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        raise SystemExit("SUPABASE_ACCESS_TOKEN required")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        rows = run_sql(
            token,
            """
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS rls_enabled,
                   EXISTS (
                     SELECT 1 FROM pg_policies p
                     WHERE p.tablename = c.relname AND p.schemaname = 'public'
                   ) AS has_policy,
                   EXISTS (
                     SELECT 1 FROM information_schema.columns col
                     WHERE col.table_schema = 'public'
                       AND col.table_name = c.relname
                       AND col.column_name = 'org_id'
                   ) AS has_org_id
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relrowsecurity = false
            ORDER BY 1;
            """,
        )
        print(json.dumps(rows, indent=2))
        return 0
    if cmd == "exec":
        sql_path = Path(sys.argv[2])
        sql = sql_path.read_text(encoding="utf-8")
        rows = run_sql(token, sql)
        print(json.dumps(rows, indent=2) if rows is not None else "ok")
        return 0
    raise SystemExit(f"unknown cmd {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
