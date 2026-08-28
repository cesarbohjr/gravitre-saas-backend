#!/usr/bin/env python3
"""F6 live proof: follow_up_field_assert against a real vendor.

The entity_get adapter passed 13 mocked tests and did nothing against real
HubSpot, because the mocks encoded the same wrong response shape as the code.
So this mode gets the same live treatment before any claim is made:

  1. Read real pipeline stages (no invented stage ids).
  2. Create a disposable deal at stage A.
  3. hubspot.deals.update_stage -> stage B.
  4. verify_field_assert asking for B  -> must confirm.
  5. NEGATIVE CONTROL: verify_field_assert asking for A -> must report a
     mismatch. An id read-back would have called this verified, which is the
     entire reason this mode exists.
  6. Delete the deal.

Writes docs/delivery/f6-field-assert-verify-live.json
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

ORG = os.environ.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
ACTOR = os.environ.get("F6_ACTOR_ID", "a9f1240f-910a-42ca-aebf-38caeac288c3")
OUT = REPO / "docs" / "delivery" / "f6-field-assert-verify-live.json"

ACTION = "hubspot.deals.update_stage"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update(
                    {k: v for k, v in (dotenv_values(p, encoding=enc) or {}).items() if v}
                )
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _stage_ids(payload: dict) -> list[tuple[str, str]]:
    """(pipeline_id, stage_id) pairs from whatever shape pipelines.list returns."""
    out: list[tuple[str, str]] = []
    frontier = [payload]
    while frontier:
        node = frontier.pop(0)
        if isinstance(node, dict):
            if node.get("stages") and isinstance(node.get("stages"), list):
                pid = str(node.get("id") or node.get("pipelineId") or "")
                for st in node["stages"]:
                    if isinstance(st, dict) and st.get("id"):
                        out.append((pid, str(st["id"])))
            frontier.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            frontier.extend(v for v in node if isinstance(v, (dict, list)))
    return out


def main() -> int:
    _load_env()
    import httpx
    from supabase import create_client

    from app.config import get_settings
    from app.services.field_assert_verify import verify_field_assert
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)

    report: dict = {
        "started_at": utcnow(),
        "org_id": ORG,
        "vendor": "hubspot",
        "action": ACTION,
        "pass": False,
    }
    try:
        report["live_git_sha"] = (
            httpx.get("https://api.gravitre.app/health", timeout=60).json().get("git_sha")
        )
    except Exception as exc:  # noqa: BLE001
        report["live_git_sha"] = f"unreachable:{exc.__class__.__name__}"

    rows = (
        sb.table("connectors")
        .select("id, status")
        .eq("org_id", ORG)
        .eq("type", "hubspot")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    cid = next(
        (
            str(r["id"])
            for r in rows
            if str(r.get("status") or "").lower() in {"active", "connected", "healthy"}
        ),
        None,
    )
    report["connector_id"] = cid
    if not cid:
        report["blocker"] = "no_active_hubspot_connector"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    ctx = ToolContext(
        settings=settings, client=sb, org_id=ORG, actor_id=ACTOR, connector_id=cid
    )

    pipes = invoke_tool(ctx, "hubspot.pipelines.list", {"connector_id": cid})
    pairs = _stage_ids(pipes.data if isinstance(pipes.data, dict) else {})
    by_pipeline: dict[str, list[str]] = {}
    for pid, sid in pairs:
        by_pipeline.setdefault(pid, []).append(sid)
    usable = next(((p, s) for p, s in by_pipeline.items() if len(s) >= 2), (None, []))
    pipeline_id, stages = usable
    report["pipeline_id"] = pipeline_id
    report["stages_available"] = stages[:6]
    if not pipeline_id or len(stages) < 2:
        report["blocker"] = "need_two_real_pipeline_stages"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    stage_a, stage_b = stages[0], stages[1]
    report["stage_a"], report["stage_b"] = stage_a, stage_b

    marker = uuid.uuid4().hex[:12]
    created = invoke_tool(
        ctx,
        "hubspot.deals.create",
        {
            "connector_id": cid,
            "properties": {
                "dealname": f"F6 FieldAssert {marker}",
                "pipeline": pipeline_id,
                "dealstage": stage_a,
            },
        },
    )
    report["create"] = {
        "success": bool(created.success),
        "error": (created.error_message or "")[:300] or None,
    }
    if not created.success:
        report["blocker"] = "deal_create_failed"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    from app.services.entity_get_verify import extract_entity_id

    deal_id = extract_entity_id(created.data if isinstance(created.data, dict) else {}, "id")
    report["deal_id"] = deal_id

    moved = invoke_tool(
        ctx, ACTION, {"connector_id": cid, "deal_id": deal_id, "stage": stage_b}
    )
    report["update_stage"] = {
        "success": bool(moved.success),
        "error": (moved.error_message or "")[:300] or None,
    }

    write_result = moved.data if isinstance(moved.data, dict) else {}
    if not extract_entity_id(write_result, "id"):
        write_result = {**write_result, "id": deal_id}

    positive = verify_field_assert(
        invoke_action=ACTION,
        result_data=write_result,
        request_params={"deal_id": deal_id, "stage": stage_b},
        ctx=ctx,
        settle=True,
    )
    report["positive"] = positive.as_dict()

    negative = verify_field_assert(
        invoke_action=ACTION,
        result_data=write_result,
        request_params={"deal_id": deal_id, "stage": stage_a},
        ctx=ctx,
        settle=False,
    )
    report["negative_control"] = negative.as_dict()

    cleanup = None
    if deal_id:
        try:
            d = invoke_tool(ctx, "hubspot.deals.delete", {"connector_id": cid, "deal_id": deal_id})
            cleanup = {"success": bool(d.success), "error": (d.error_message or "")[:200] or None}
        except Exception as exc:  # noqa: BLE001
            cleanup = {"success": False, "error": f"{exc.__class__.__name__}: {exc}"}
    report["cleanup_deleted_test_deal"] = cleanup

    report["pass"] = bool(
        positive.verified
        and not negative.verified
        and negative.detail == "field_value_mismatch"
    )
    report["verdict"] = (
        "PASS — the stored stage matched the requested one, and asking for the "
        "stage the deal had moved away from was correctly reported as a mismatch."
        if report["pass"]
        else "FAIL — see positive/negative_control."
    )
    report["finished_at"] = utcnow()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
