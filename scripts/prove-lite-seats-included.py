"""E1 live proof: Command included=Unlimited; Node included=2 from plan lite_users."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

for candidate in [ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"]:
    if not candidate.exists():
        continue
    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

import asyncio  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

from supabase import create_client  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.middleware.entitlements import resolve_entitlements  # noqa: E402
from app.routers import settings as settings_router  # noqa: E402

COMMAND_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"


async def _lite_seats_summary(org_id: str) -> dict:
    settings = get_settings()
    return await settings_router.get_lite_seats_route(
        _user={"user_id": "prove"},
        org_id=org_id,
        settings=settings,
    )


async def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    cmd_ent = resolve_entitlements(settings, COMMAND_ORG)
    cmd_summary = (await _lite_seats_summary(COMMAND_ORG))["summary"]

    node_org = str(uuid.uuid4())
    client.table("organizations").insert(
        {"id": node_org, "name": f"lite-included-probe-{node_org[:8]}"}
    ).execute()
    client.table("org_billing").insert(
        {
            "org_id": node_org,
            "plan_code": "node",
            "billing_status": "active",
        }
    ).execute()
    try:
        node_ent = resolve_entitlements(settings, node_org)
        node_summary = (await _lite_seats_summary(node_org))["summary"]
    finally:
        client.table("org_billing").delete().eq("org_id", node_org).execute()
        client.table("organizations").delete().eq("id", node_org).execute()

    ok = (
        cmd_ent["limits"]["lite_seats_included"] is None
        and cmd_summary.get("unlimited") is True
        and cmd_summary.get("included_display") == "Unlimited"
        and cmd_summary.get("included") is None
        and node_ent["limits"]["lite_seats_included"] == 2
        and node_summary.get("included") == 2
        and node_summary.get("included_display") == "2"
        and node_summary.get("unlimited") is False
    )
    print(
        json.dumps(
            {
                "command": {
                    "resolver_lite_seats_included": cmd_ent["limits"]["lite_seats_included"],
                    "api_summary": cmd_summary,
                },
                "node_probe_org": node_org,
                "node": {
                    "resolver_lite_seats_included": node_ent["limits"]["lite_seats_included"],
                    "api_summary": node_summary,
                },
                "pass": ok,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
