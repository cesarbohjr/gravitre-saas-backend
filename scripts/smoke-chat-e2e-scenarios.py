#!/usr/bin/env python3
"""Run end-to-end AI Chat connector scenarios against stored OAuth connectors.

Usage:
  python scripts/smoke-chat-e2e-scenarios.py
  python scripts/smoke-chat-e2e-scenarios.py --live
  python scripts/smoke-chat-e2e-scenarios.py --json docs/delivery/chat-e2e-scenarios-latest.json
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
from app.services.chat_e2e_scenarios import (  # noqa: E402
    CHAT_E2E_SCENARIOS,
    export_chat_e2e_csv,
    export_chat_e2e_json,
    run_all_chat_e2e_scenarios,
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
    """Isolated conversation test org only — never inherit OAUTH_SMOKE_ORG_ID."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gravitre_test_client import require_isolated_org, resolve_test_actor

    org_id, user_id, _email = resolve_test_actor(env, client)
    override = (env.get("CHAT_E2E_ORG_ID") or env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or "").strip()
    if override:
        org_id = require_isolated_org(override)
    return org_id, user_id


async def _async_main() -> int:
    parser = argparse.ArgumentParser(description="AI Chat E2E connector scenarios")
    parser.add_argument("--live", action="store_true", help="Execute real connector tools")
    parser.add_argument("--environment", default=os.environ.get("CHAT_E2E_ENVIRONMENT", "production"))
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--scenario", action="append", default=[], help="Scenario id filter")
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--csv", dest="csv_path", default=None)
    args = parser.parse_args()

    env = _load_env()
    if args.org_id:
        env["CHAT_E2E_ORG_ID"] = args.org_id
    for key, value in env.items():
        os.environ.setdefault(key, value)

    settings = get_settings()
    client = _supabase_client(env)
    org_id, user_id = _resolve_org(env, client)

    report = await run_all_chat_e2e_scenarios(
        org_id=org_id,
        user_id=user_id,
        client=client,
        settings=settings,
        environment_name=args.environment,
        live_execute=args.live,
        env=env,
        scenario_ids=args.scenario or None,
    )

    print(f"Chat E2E run {report['runId']} org={org_id} live={args.live}")
    print(f"  scenarios passed={report['summary'].get('passed', 0)} failed={report['summary'].get('failed', 0)}")
    for row in report["scenarios"]:
        if row["status"] != "passed":
            print(f"  FAIL {row['scenarioId']}: {row['message']}")
            for check in row["checks"]:
                if check["status"] == "failed":
                    print(f"    - {check['check']}: {check['detail'][:120]}")

    json_path = args.json_path or str(REPO / "docs" / "delivery" / "chat-e2e-scenarios-latest.json")
    csv_path = args.csv_path or str(REPO / "docs" / "delivery" / "chat-e2e-scenarios-latest.csv")
    export_chat_e2e_json(json_path, report)
    export_chat_e2e_csv(csv_path, report)
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    return 1 if report["summary"].get("failed") else 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
