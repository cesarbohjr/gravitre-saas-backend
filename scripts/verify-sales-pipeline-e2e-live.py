#!/usr/bin/env python3
"""Live E2E probe: Sales pipeline stages on deployed tip (Apollo → HubSpot sync path)."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "docs" / "delivery" / "sales-pipeline-e2e-live.json"


def _load_env() -> dict[str, str]:
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for path in (ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local", ROOT / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main() -> int:
    import httpx

    from app.services.tool_registry import get_tool_registry
    from app.services.tool_types import ToolContext
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    env = _load_env()
    for key, value in env.items():
        os.environ.setdefault(key, value)
    org_id = env.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
    actor_id = env.get("F6_ACTOR_ID", "a9f1240f-910a-42ca-aebf-38caeac288c3")
    backend_url = env.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")

    report: dict = {"pass": False, "gates": {}, "probes": {}}

    try:
        health = httpx.get(f"{backend_url}/health", timeout=30).json()
        report["prod_health_sha"] = health.get("git_sha")
        report["gates"]["prod_health"] = "PASS" if health.get("status") == "ok" else "FAIL"
    except Exception as exc:  # noqa: BLE001
        report["gates"]["prod_health"] = "NOT RUN"
        report["prod_health_error"] = str(exc)[:200]

    settings = get_settings()
    client = get_supabase_client(settings)
    reg = get_tool_registry()
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
    )
    connected = reg.list_connected_integrations(client, org_id, environment_name="production")
    report["connected_integrations"] = connected

    def _probe(action: str, args: dict) -> dict:
        from app.services.tool_service import invoke_tool

        try:
            result = invoke_tool(ctx, action, args)
            return {
                "success": bool(result.success),
                "error_code": getattr(result, "error_code", None),
                "action": action,
            }
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "action": action, "error": str(exc)[:200]}

    probes: dict[str, dict] = {}
    if "apollo" in connected:
        probes["apollo_people_search"] = _probe("apollo.people.search", {"q_keywords": "ceo", "page": 1, "per_page": 1})
    if "hubspot" in connected:
        probes["hubspot_campaigns_list"] = _probe("hubspot.campaigns.list", {"limit": 1})
        marker = uuid.uuid4().hex[:8]
        probes["hubspot_contact_create"] = _probe(
            "hubspot.contacts.create",
            {
                "properties": {
                    "email": f"sales-pipe-{marker}@gravitre-smoke.invalid",
                    "firstname": "SalesPipe",
                }
            },
        )

    report["probes"] = probes
    report["gates"]["apollo_search"] = (
        "PASS" if probes.get("apollo_people_search", {}).get("success") else "NOT RUN" if "apollo" not in connected else "FAIL"
    )
    report["gates"]["hubspot_campaigns_list"] = (
        "PASS"
        if probes.get("hubspot_campaigns_list", {}).get("success")
        else "NOT RUN"
        if "hubspot" not in connected
        else "FAIL"
    )
    report["gates"]["hubspot_sync_write"] = (
        "PASS"
        if probes.get("hubspot_contact_create", {}).get("success")
        else "NOT RUN"
        if "hubspot" not in connected
        else "FAIL"
    )

    required = [v for k, v in report["gates"].items() if k != "prod_health"]
    report["pass"] = report["gates"].get("prod_health") == "PASS" and all(
        v in {"PASS", "NOT RUN"} for v in required
    ) and any(v == "PASS" for v in required)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
