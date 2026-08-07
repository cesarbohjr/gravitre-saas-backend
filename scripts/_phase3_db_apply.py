#!/usr/bin/env python3
"""Apply Phase 3 DB fixes via Supabase Management API + capture EXPLAIN / advisor deltas."""
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
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def run_sql(token: str, query: str):
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=180,
    )
    if r.status_code >= 400:
        raise SystemExit(f"SQL API {r.status_code}: {r.text[:2000]}")
    return r.json()


def main() -> int:
    env = load_env()
    token = env.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        raise SystemExit("SUPABASE_ACCESS_TOKEN required")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "apply"

    if cmd == "apply":
        sql = (ROOT / "supabase/migrations/20260805220000_audit_events_org_action_created_idx.sql").read_text(
            encoding="utf-8"
        )
        # Also drop duplicate index on optimization_recommendations if present
        burn = """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'optimization_recommendations'
              AND indexname = 'optimization_recommendations_org_id_idx'
          ) AND EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'optimization_recommendations'
              AND indexname = 'idx_optimization_recommendations_org'
          ) THEN
            DROP INDEX IF EXISTS public.optimization_recommendations_org_id_idx;
          END IF;
        END $$;
        """
        print(json.dumps({"index": run_sql(token, sql)}, indent=2)[:500])
        print(json.dumps({"dup_index": run_sql(token, burn)}, indent=2)[:500])
        return 0

    if cmd == "explain":
        q = """
        EXPLAIN (FORMAT JSON)
        SELECT id, action, created_at
        FROM public.audit_events
        WHERE org_id = 'cbbf993b-b22f-41ce-964b-1fc25e0dd9ea'
          AND action = 'tool.invoke.completed'
        ORDER BY created_at DESC
        LIMIT 50;
        """
        print(json.dumps(run_sql(token, q), indent=2))
        return 0

    if cmd == "indexes":
        q = """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = 'audit_events'
        ORDER BY indexname;
        """
        print(json.dumps(run_sql(token, q), indent=2))
        return 0

    raise SystemExit(f"unknown cmd {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
