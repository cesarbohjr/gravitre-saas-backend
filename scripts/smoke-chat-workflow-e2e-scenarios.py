#!/usr/bin/env python3
"""Run multi-step AI Chat workflow E2E scenarios.

Usage:
  python scripts/smoke-chat-workflow-e2e-scenarios.py
  python scripts/smoke-chat-workflow-e2e-scenarios.py --live
  python scripts/smoke-chat-workflow-e2e-scenarios.py --live --enable-writes
  python scripts/smoke-chat-workflow-e2e-scenarios.py --scenario hubspot_contacts_summarize_asana_tasks
  python scripts/smoke-chat-workflow-e2e-scenarios.py --json docs/delivery/chat-workflow-e2e-latest.json
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.chat_workflow_e2e_live import LiveWorkflowOptions  # noqa: E402
from app.services.chat_workflow_e2e_scenarios import (  # noqa: E402
    CHAT_WORKFLOW_E2E_SCENARIOS,
    export_workflow_e2e_csv,
    export_workflow_e2e_json,
    run_all_chat_workflow_e2e_scenarios,
)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        merged.update({k: v for k, v in dotenv_values(path).items() if v})
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _resolve_org(env: dict[str, str], client) -> tuple[str, str]:
    org_id = (
        env.get("CHAT_WORKFLOW_E2E_ORG_ID")
        or env.get("CHAT_E2E_ORG_ID")
        or env.get("OAUTH_SMOKE_ORG_ID")
        or env.get("SMOKE_ORG_ID")
        or ""
    ).strip()
    user_id = env.get("CHAT_WORKFLOW_E2E_USER_ID") or env.get("CHAT_E2E_USER_ID") or "chat-workflow-e2e"
    if org_id:
        return org_id, user_id
    members = (
        client.table("organization_members")
        .select("org_id, user_id")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit("Set CHAT_WORKFLOW_E2E_ORG_ID or connect an admin org")
    row = members.data[0]
    return str(row["org_id"]), str(row.get("user_id") or user_id)


async def _async_main() -> int:
    parser = argparse.ArgumentParser(description="Multi-step AI Chat workflow E2E scenarios")
    parser.add_argument("--live", action="store_true", help="Execute real connector tools via stored OAuth")
    parser.add_argument(
        "--enable-writes",
        action="store_true",
        help="Allow sandbox write steps (requires sandbox env or OAUTH_SMOKE_FORCE_SANDBOX_WRITES=1)",
    )
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Allow destructive workflow steps and auto cleanup deletes",
    )
    parser.add_argument(
        "--auto-cleanup",
        action="store_true",
        help="Attempt automated cleanup for tagged test records (requires --allow-destructive)",
    )
    parser.add_argument("--environment", default=os.environ.get("CHAT_WORKFLOW_E2E_ENVIRONMENT", "production"))
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--scenario", action="append", default=[], help="Scenario id filter")
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--csv", dest="csv_path", default=None)
    args = parser.parse_args()

    env = _load_env()
    if args.org_id:
        env["CHAT_WORKFLOW_E2E_ORG_ID"] = args.org_id
    for key, value in env.items():
        os.environ.setdefault(key, value)

    settings = get_settings()
    client = _supabase_client(env)
    org_id, user_id = _resolve_org(env, client)
    live_options = LiveWorkflowOptions(
        enable_writes=args.enable_writes,
        allow_destructive=args.allow_destructive,
        auto_cleanup=args.auto_cleanup,
        env=env,
    )

    report = await run_all_chat_workflow_e2e_scenarios(
        org_id=org_id,
        user_id=user_id,
        client=client,
        settings=settings,
        environment_name=args.environment,
        live_execute=args.live,
        live_options=live_options,
        scenario_ids=args.scenario or None,
    )

    print(
        f"Chat workflow E2E run {report['runId']} org={org_id} "
        f"live={args.live} writes={args.enable_writes}"
    )
    print(
        f"  scenarios passed={report['summary'].get('passed', 0)} "
        f"failed={report['summary'].get('failed', 0)} "
        f"blocked={report['summary'].get('blocked', 0)}"
    )
    for row in report["scenarios"]:
        if row["status"] != "passed":
            print(f"  {row['status'].upper()} {row['scenarioId']}")
            for check in row["checks"]:
                if check["status"] == "failed":
                    print(f"    - {check['check']}: {check['detail'][:120]}")
            for instruction in row.get("cleanupInstructions") or []:
                print(f"    cleanup: {instruction[:120]}")

    json_path = args.json_path or str(REPO / "docs" / "delivery" / "chat-workflow-e2e-latest.json")
    csv_path = args.csv_path or str(REPO / "docs" / "delivery" / "chat-workflow-e2e-latest.csv")
    export_workflow_e2e_json(json_path, report)
    export_workflow_e2e_csv(csv_path, report)
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    return 1 if report["summary"].get("failed") else 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
