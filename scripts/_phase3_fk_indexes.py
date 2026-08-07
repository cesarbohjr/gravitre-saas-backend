#!/usr/bin/env python3
"""List / create hottest unindexed FK covering indexes via Management API."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REF = os.environ.get("SUPABASE_PROJECT_REF", "smyeexlrqdpymwjmgzqu")

LIST_SQL = """
SELECT c.conrelid::regclass::text AS table_name,
       a.attname AS column_name,
       c.confrelid::regclass::text AS referenced,
       COALESCE(s.n_live_tup, 0) AS live_rows
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
LEFT JOIN pg_stat_user_tables s ON s.relid = c.conrelid
WHERE c.contype = 'f'
  AND NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid
      AND a.attnum = ANY (i.indkey::smallint[])
  )
ORDER BY COALESCE(s.n_live_tup, 0) DESC
LIMIT 30;
"""


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


def safe_ident(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError(name)
    return name


def main() -> int:
    env = load_env()
    token = env["SUPABASE_ACCESS_TOKEN"]
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    rows = run_sql(token, LIST_SQL)
    print(json.dumps({"count": len(rows), "rows": rows[:30]}, indent=2))
    if cmd != "apply":
        return 0

    created = []
    for row in rows[:15]:
        table = str(row["table_name"]).replace("public.", "")
        col = str(row["column_name"])
        try:
            table_i = safe_ident(table)
            col_i = safe_ident(col)
        except ValueError:
            continue
        idx = f"idx_{table_i}_{col_i}_fk"
        if len(idx) > 63:
            idx = f"idx_{table_i[:20]}_{col_i[:20]}_fk"
        sql = f"CREATE INDEX IF NOT EXISTS {idx} ON public.{table_i} ({col_i});"
        try:
            run_sql(token, sql)
            created.append({"index": idx, "table": table_i, "column": col_i})
        except SystemExit as exc:
            created.append({"index": idx, "error": str(exc)[:200]})
    out = ROOT / "docs" / "delivery" / "phase3-fk-indexes-created.json"
    out.write_text(json.dumps({"created": created}, indent=2), encoding="utf-8")
    print(json.dumps({"created": len(created), "out": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
