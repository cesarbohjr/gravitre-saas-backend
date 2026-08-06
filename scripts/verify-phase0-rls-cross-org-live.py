#!/usr/bin/env python3
"""Phase 0 live proof: authenticated JWT cannot read other-org rows on F1 tables."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "docs" / "delivery" / "phase0-rls-cross-org-live.json"

# Named F1 set + the 3 remaining advisor ERRORs from the live list probe.
ORG_TABLES = [
    "agent_execution_interrupts",
    "intelligence_outcome_events",
    "intelligence_learning_signals",
    "strategy_performance_records",
    "domain_segment_learning_state",
    "domain_optimization_recommendations",
    "test_credential_org_allowlist",
]
DENY_ALL_TABLES = ["restricted_test_user_ids"]

# Smoke org that owns rows we try to leak FROM as isolated actor.
SMOKE_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
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


def run_mgmt_sql(token: str, query: str):
    ref = os.environ.get("SUPABASE_PROJECT_REF", "smyeexlrqdpymwjmgzqu")
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from isolated_conversation_org import resolve_isolated_conversation_actor

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    assert org_id.lower() != SMOKE_ORG.lower(), "isolated org must differ from smoke org"

    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    user_client = create_client(env["SUPABASE_URL"], env["SUPABASE_ANON_KEY"])
    user_client.auth.set_session  # type: ignore[attr-defined]
    # PostgREST with user JWT
    headers = {
        "Authorization": f"Bearer {tok}",
        "apikey": env["SUPABASE_ANON_KEY"],
        "Content-Type": "application/json",
        "Prefer": "count=exact",
    }

    # Seed one smoke-org row per org table (service role) then attempt user read.
    seed_ids: dict[str, str] = {}
    results: list[dict] = []

    # Ensure smoke org has at least one visible row for tables that need inserts
    for table in ORG_TABLES:
        row_id = str(uuid.uuid4())
        payload: dict = {"org_id": SMOKE_ORG}
        try:
            if table == "agent_execution_interrupts":
                payload.update(
                    {
                        "id": row_id,
                        "target_type": "agent_job",
                        "target_id": str(uuid.uuid4()),
                        "signal": "pause",
                        "status": "pending",
                        "source": "api",
                        "metadata": {"phase0": True},
                    }
                )
            elif table == "intelligence_outcome_events":
                payload.update(
                    {
                        "id": row_id,
                        "outcome_event": "phase0_rls_probe",
                        "metadata": {"phase0": True},
                    }
                )
            elif table == "intelligence_learning_signals":
                payload.update(
                    {
                        "id": row_id,
                        "strategy_key": "phase0",
                        "signal_type": "probe",
                        "payload": {"phase0": True},
                    }
                )
            elif table == "strategy_performance_records":
                payload.update(
                    {
                        "id": row_id,
                        "strategy_key": "phase0",
                        "segment_key": "probe",
                        "metrics": {"phase0": True},
                    }
                )
            elif table == "domain_segment_learning_state":
                payload.update(
                    {
                        "id": row_id,
                        "segment_key": f"phase0-{row_id[:8]}",
                        "meta_learning_state": {},
                        "optimization_snapshot": {},
                    }
                )
            elif table == "domain_optimization_recommendations":
                payload.update(
                    {
                        "id": row_id,
                        "status": "proposed",
                        "recommendation": {"phase0": True},
                    }
                )
            elif table == "test_credential_org_allowlist":
                # Do not mutate allowlist with fake orgs — use SELECT-only probe
                # against existing smoke allowlist rows if present.
                payload = {}
            if payload:
                # Strip unknown columns by trying insert; fall back to select-only
                try:
                    sb.table(table).upsert(payload).execute()
                    seed_ids[table] = row_id
                except Exception as exc:  # noqa: BLE001
                    # Column mismatch — select-only against any smoke row
                    seed_ids[table] = f"select-only:{exc.__class__.__name__}"
        except Exception as exc:  # noqa: BLE001
            seed_ids[table] = f"seed-error:{exc}"

        # Authenticated user tries to read smoke-org rows
        r = httpx.get(
            f"{url}/rest/v1/{table}",
            headers=headers,
            params={"org_id": f"eq.{SMOKE_ORG}", "select": "*", "limit": "5"},
            timeout=60,
        )
        body = r.text
        try:
            data = r.json()
        except Exception:
            data = body
        leaked = isinstance(data, list) and len(data) > 0
        results.append(
            {
                "table": table,
                "http": r.status_code,
                "row_count": len(data) if isinstance(data, list) else None,
                "blocked": (r.status_code in {200, 206} and not leaked)
                or r.status_code in {401, 403},
                "leaked": leaked,
                "seed": seed_ids.get(table),
            }
        )

    for table in DENY_ALL_TABLES:
        r = httpx.get(
            f"{url}/rest/v1/{table}",
            headers=headers,
            params={"select": "*", "limit": "5"},
            timeout=60,
        )
        try:
            data = r.json()
        except Exception:
            data = []
        leaked = isinstance(data, list) and len(data) > 0
        results.append(
            {
                "table": table,
                "http": r.status_code,
                "row_count": len(data) if isinstance(data, list) else None,
                "blocked": (r.status_code in {200, 206} and not leaked)
                or r.status_code in {401, 403},
                "leaked": leaked,
                "seed": "deny-all-policy",
            }
        )

    # Policy inventory via management SQL
    policies = []
    token = env.get("SUPABASE_ACCESS_TOKEN")
    if token:
        policies = run_mgmt_sql(
            token,
            """
            SELECT tablename, policyname, cmd, qual IS NOT NULL AS has_using,
                   with_check IS NOT NULL AS has_check
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename IN (
                'agent_execution_interrupts',
                'intelligence_outcome_events',
                'intelligence_learning_signals',
                'strategy_performance_records',
                'domain_segment_learning_state',
                'domain_optimization_recommendations',
                'test_credential_org_allowlist',
                'restricted_test_user_ids'
              )
            ORDER BY 1, 2;
            """,
        )
        rls_state = run_mgmt_sql(
            token,
            """
            SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
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
            """,
        )
    else:
        rls_state = []

    # Service-role still can read (bypass)
    svc_ok = True
    try:
        sb.table("intelligence_outcome_events").select("id").limit(1).execute()
    except Exception:
        svc_ok = False

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "isolated_org_id": org_id,
        "isolated_user_id": user_id,
        "foreign_org_id": SMOKE_ORG,
        "policies": policies,
        "rls_enabled": rls_state,
        "cross_org_probes": results,
        "service_role_still_reads": svc_ok,
        "pass": all(r.get("blocked") and not r.get("leaked") for r in results)
        and svc_ok
        and all(bool(x.get("rls_enabled")) for x in (rls_state or [])),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("wrote", OUT)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
