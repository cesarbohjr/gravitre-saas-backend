#!/usr/bin/env python3
import json
import os
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REF = "smyeexlrqdpymwjmgzqu"


def load_env():
    merged = {}
    for p in (ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main():
    env = load_env()
    q = """
    SELECT c.relname, c.relrowsecurity AS rls
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
      AND c.relname IN (
        'agent_execution_interrupts',
        'intelligence_outcome_events',
        'intelligence_learning_signals',
        'strategy_performance_records',
        'domain_segment_learning_state',
        'domain_optimization_recommendations',
        'test_credential_org_allowlist',
        'restricted_test_user_ids'
      )
    ORDER BY 1;
    """
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={
            "Authorization": f"Bearer {env['SUPABASE_ACCESS_TOKEN']}",
            "Content-Type": "application/json",
        },
        json={"query": q},
        timeout=60,
    )
    print(r.status_code)
    print(json.dumps(r.json(), indent=2))


if __name__ == "__main__":
    main()
