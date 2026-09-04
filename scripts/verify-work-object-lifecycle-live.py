#!/usr/bin/env python3
"""Live verification for WorkObject lifecycle continuity."""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from app.core.safe_dict import safe_normalize_stored_dict  # noqa: E402
from app.services.work_object_service import (  # noqa: E402
    list_work_object_events,
    record_execution_work_object,
)

OUT = REPO / "docs" / "delivery" / "work-object-lifecycle-live.json"
TERMINAL = {"completed", "partial_success", "failed", "flagged_for_review", "cancelled"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        loaded: dict[str, str | None] | None = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_run_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    params = safe_normalize_stored_dict(row.get("parameters"))
    verified = safe_normalize_stored_dict(params, key="verified_output")
    entity_type = str(verified.get("entity_type") or "").strip().lower()
    entity_id = str(verified.get("entity_id") or "").strip()
    invoke_action = str(params.get("invoke_action") or params.get("tool_name") or "").strip().lower()
    conversation_id = str(params.get("conversation_id") or "").strip()
    if entity_type in {"connector", "workflow_run", "execution"}:
        entity_type = ""
        entity_id = ""
    return (str(row.get("org_id") or ""), entity_type, entity_id, invoke_action, conversation_id)


def main() -> int:
    env = load_env()
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 2
    client = create_client(url, key)

    rows = (
        client.table("workflow_runs")
        .select("id, org_id, workflow_id, status, created_at, parameters")
        .order("created_at", desc=False)
        .limit(1200)
        .execute()
        .data
        or []
    )
    runs = [row for row in rows if isinstance(row, dict) and str(row.get("status") or "").lower() in TERMINAL]

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    convo_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    actions_by_group: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    actions_by_convo: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in runs:
        org_id, entity_type, entity_id, invoke_action, conversation_id = _parse_run_key(row)
        if not org_id or not entity_type or not entity_id:
            if conversation_id:
                key2 = (org_id, conversation_id)
                convo_groups[key2].append(row)
                if invoke_action:
                    actions_by_convo[key2].add(invoke_action)
            continue
        key3 = (org_id, entity_type, entity_id)
        groups[key3].append(row)
        if invoke_action:
            actions_by_group[key3].add(invoke_action)
        if conversation_id:
            key2 = (org_id, conversation_id)
            convo_groups[key2].append(row)
            if invoke_action:
                actions_by_convo[key2].add(invoke_action)

    best_key: tuple[str, str, str] | None = None
    best_convo: tuple[str, str] | None = None
    best_score = -1.0
    best_days = 0.0
    for key3, items in groups.items():
        if len(items) < 2:
            continue
        created = [str(item.get("created_at") or "") for item in items if item.get("created_at")]
        if len(created) < 2:
            continue
        dates = sorted(_to_dt(ts) for ts in created)
        span_days = (dates[-1] - dates[0]).total_seconds() / 86400
        unique_actions = len(actions_by_group.get(key3, set()))
        score = (len(items) * 10) + (unique_actions * 4) + span_days
        if score > best_score and (unique_actions >= 2 or span_days >= 1.0):
            best_score = score
            best_key = key3
            best_days = span_days

    if best_key is None:
        for key2, items in convo_groups.items():
            if len(items) < 3:
                continue
            actions = actions_by_convo.get(key2, set())
            if len(actions) < 2:
                continue
            created = [str(item.get("created_at") or "") for item in items if item.get("created_at")]
            if len(created) < 2:
                continue
            dates = sorted(_to_dt(ts) for ts in created)
            span_days = (dates[-1] - dates[0]).total_seconds() / 86400
            score = (len(items) * 10) + (len(actions) * 5) + span_days
            if score > best_score:
                best_score = score
                best_convo = key2
                best_days = span_days

    if best_key is None and best_convo is None:
        print("No eligible historical multi-step entity found for lifecycle verification")
        return 1

    if best_key is not None:
        org_id, entity_type, entity_id = best_key
        picked = sorted(groups[best_key], key=lambda row: str(row.get("created_at") or ""))
        mode = "entity"
    else:
        org_id, conversation_id = best_convo or ("", "")
        entity_type, entity_id = "conversation", conversation_id
        picked = sorted(convo_groups[(org_id, conversation_id)], key=lambda row: str(row.get("created_at") or ""))
        mode = "conversation"
    attribution: list[dict[str, Any]] = []
    work_object_id = None
    for row in picked:
        params = safe_normalize_stored_dict(row.get("parameters"))
        verified = safe_normalize_stored_dict(params, key="verified_output")
        if work_object_id:
            params["work_object_id"] = work_object_id
        if mode == "conversation":
            params.setdefault("work_object_title", f"Conversation lifecycle {entity_id[:8]}")
            params.setdefault("work_object_type", "objective")
        ref = record_execution_work_object(
            client,
            org_id=org_id,
            run_id=str(row.get("id") or ""),
            terminal_status=str(row.get("status") or "").lower(),
            metadata=params,
            verified_output=verified,
            workflow_id=str(row.get("workflow_id") or "") or None,
        )
        if ref and ref.get("work_object_id"):
            work_object_id = str(ref["work_object_id"])
        attribution.append(
            {
                "run_id": row.get("id"),
                "created_at": row.get("created_at"),
                "status": row.get("status"),
                "invoke_action": params.get("invoke_action") or params.get("tool_name"),
                "work_object_id": ref.get("work_object_id") if ref else None,
                "event_id": ref.get("event_id") if ref else None,
            }
        )

    if not work_object_id:
        print("Failed to attribute runs to a WorkObject")
        return 1

    events = list_work_object_events(client, org_id=org_id, work_object_id=work_object_id, limit=500)
    unique_actions = sorted({str((event.get("actionName") or "")).strip() for event in events if event.get("actionName")})
    calendar_days = sorted(
        {
            str(item.get("created_at") or "")[:10]
            for item in attribution
            if str(item.get("created_at") or "")
        }
    )

    payload = {
        "recorded_at": utcnow(),
        "selection_mode": mode,
        "entity_anchor": {"org_id": org_id, "entity_type": entity_type, "entity_id": entity_id},
        "work_object_id": work_object_id,
        "picked_runs": attribution,
        "event_count": len(events),
        "unique_actions": unique_actions,
        "span_days": round(best_days, 3),
        "calendar_days": calendar_days,
        "pass": len(events) >= 3 and len(unique_actions) >= 2 and len(calendar_days) >= 3,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        f"work_object_id={work_object_id} event_count={len(events)} unique_actions={len(unique_actions)} span_days={payload['span_days']}"
    )
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
