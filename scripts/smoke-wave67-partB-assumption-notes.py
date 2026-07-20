#!/usr/bin/env python3
"""Part B — causal assumption_notes: omit list name → inferred_fields → panel payload.

Message deliberately omits the list name. System must infer it (default hint path).
Captures plan before/after inference and ExecutionResult.assumption_notes.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
import sys

sys.path.insert(0, str(BACKEND))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if p.is_file():
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)

from app.config import get_settings  # noqa: E402
from app.services.chat_connector_execution_service import (  # noqa: E402
    ChatConnectorExecutionService,
    _assumption_notes_from_plan,
    get_chat_connector_execution_service,
)
from app.services.chat_connector_models import ConnectorActionPlan, LIST_CREATE_INTENT  # noqa: E402
from app.services.conversation_state_service import get_conversation_state_service  # noqa: E402
from app.workflows.repository import get_supabase_client  # noqa: E402

ORG = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
# Deliberately NO list name — inference must supply default "MSP Prospects".
# LIST_CREATE_INTENT requires create/new + (contact) list; avoid trailing text after
# "list" or the planned-details regex treats it as a name.
USER_MESSAGE = "In Apollo, create a contact list."


async def main() -> None:
    settings = get_settings()
    client = get_supabase_client(settings)
    actor = str(
        (client.table("organization_members").select("user_id").eq("org_id", ORG).limit(1).execute().data or [{}])[
            0
        ].get("user_id")
        or ""
    )
    conv = str(uuid.uuid4())
    svc = get_chat_connector_execution_service(settings)
    evidence: dict = {
        "part": "B",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conv,
        "user_message": USER_MESSAGE,
        "causation_setup": {
            "user_supplied_list_name": False,
            "list_create_intent_matches": bool(LIST_CREATE_INTENT.search(USER_MESSAGE)),
        },
    }

    # --- Before inference: what the message itself yields ---
    planned_before = ChatConnectorExecutionService._planned_details_from_message(USER_MESSAGE, "apollo")
    evidence["plan_before_inference"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "planned_details_from_message": planned_before,
        "explicit_list_name_in_message": bool(planned_before.get("List name") or planned_before.get("Name")),
        "note": "Empty List name here is required for causal inference (default hint path).",
    }
    print("BEFORE", json.dumps(evidence["plan_before_inference"], indent=2))

    if evidence["plan_before_inference"]["explicit_list_name_in_message"]:
        evidence["claim_4"] = {
            "status": "FAIL",
            "reason": "Message unexpectedly contained an explicit list name — not a causal omit-name turn",
        }
        _write(evidence)
        raise SystemExit(1)

    # --- Run governed connector turn (auto-plan + inferred_fields) ---
    turn_at = datetime.now(timezone.utc).isoformat()
    turn = await svc.process_turn(
        org_id=ORG,
        user_id=actor,
        conversation_id=conv,
        message=USER_MESSAGE,
        classification={"intent": "connector_action", "requires_action": True},
        task_state={},
        connected_integrations=["apollo", "hubspot"],
        client=client,
        environment_name="production",
    )
    evidence["process_turn"] = {
        "at": turn_at,
        "dialogue_mode": (turn or {}).get("dialogue_mode"),
        "stop_pipeline": (turn or {}).get("stop_pipeline"),
        "message_preview": str((turn or {}).get("message") or "")[:240],
        "keys": sorted((turn or {}).keys()),
    }

    pending = ((turn or {}).get("task_state") or {}).get("pending_task") or {}
    plan_payload = pending.get("plan") or pending.get("params") or {}
    # pending structure uses plan key in auto-plan path
    if "invoke_action" not in plan_payload and isinstance(pending.get("params"), dict):
        plan_payload = pending["params"]
    evidence["pending_task_raw"] = {
        "status": pending.get("status"),
        "type": pending.get("type"),
        "plan_keys": sorted(plan_payload.keys()) if isinstance(plan_payload, dict) else None,
    }

    evidence["plan_after_inference"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "pending_status": pending.get("status"),
        "invoke_action": plan_payload.get("invoke_action"),
        "args": plan_payload.get("args"),
        "inferred_fields": plan_payload.get("inferred_fields"),
        "inference_sources": plan_payload.get("inference_sources"),
    }
    print("AFTER", json.dumps(evidence["plan_after_inference"], indent=2))

    inferred = plan_payload.get("inferred_fields") or []
    inferred_name = (plan_payload.get("args") or {}).get("name")
    causal_ok = (
        "name" in [str(x) for x in inferred]
        and bool(inferred_name)
        and not evidence["plan_before_inference"]["explicit_list_name_in_message"]
    )
    evidence["causation"] = {
        "inferred_fields_populated_because_name_missing": causal_ok,
        "inferred_name": inferred_name,
        "inference_source": (plan_payload.get("inference_sources") or {}).get("name"),
    }

    if not causal_ok:
        evidence["claim_4"] = {
            "status": "FAIL",
            "reason": "inferred_fields/name not populated from omitted input",
            "causation": evidence["causation"],
            "process_turn": evidence["process_turn"],
        }
        _write(evidence)
        raise SystemExit(1)

    # Rebuild plan object for execute_plan (include inferred metadata)
    plan = ConnectorActionPlan(
        tool_name=str(plan_payload.get("tool_name") or "apollo_lists_create"),
        invoke_action=str(plan_payload.get("invoke_action") or "apollo.lists.create"),
        integration=str(plan_payload.get("integration") or "apollo"),
        kind=str(plan_payload.get("kind") or "write"),
        label=str(plan_payload.get("label") or "Create contact list"),
        args=dict(plan_payload.get("args") or {}),
        requires_approval=True,
        inferred_fields=tuple(str(x) for x in inferred),
        inference_sources=dict(plan_payload.get("inference_sources") or {}),
    )
    notes_preview = _assumption_notes_from_plan(plan)
    evidence["assumption_notes_from_plan"] = notes_preview

    state = get_conversation_state_service(settings)
    await state.update_task_state(
        conv,
        ORG,
        {
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {
                    **ChatConnectorExecutionService.plan_to_dict(plan),
                    "status": "awaiting_confirm",
                    "source": "part_b_causal_inference",
                },
            }
        },
        client=client,
    )

    approve_at = datetime.now(timezone.utc).isoformat()
    result = await svc.execute_plan(
        org_id=ORG,
        user_id=actor,
        conversation_id=conv,
        plan=plan,
        client=client,
        classification={"intent": "connector_action", "requires_approval": True},
        environment_name="production",
    )
    done_at = datetime.now(timezone.utc).isoformat()

    execution_payload = {
        "success": result.success,
        "error_code": result.error_code,
        "result_url": result.result_url,
        "body": (result.body or "")[:300],
        "assumption_notes": result.assumption_notes,
        "entity_id": result.entity_id,
    }
    evidence["execution"] = {
        "approve_at": approve_at,
        "completed_at": done_at,
        **execution_payload,
    }

    # Panel contract: ChatExecutionPanel renders Assumptions when assumption_notes non-empty
    panel_would_render = bool(result.assumption_notes) and any(
        str(n).strip() for n in (result.assumption_notes or [])
    )
    evidence["panel_contract"] = {
        "ChatExecutionPanel_reads": "executionResult.assumption_notes",
        "assumption_notes_present": panel_would_render,
        "notes": result.assumption_notes,
        "ui_file": "apps/web/components/gravitre/assistant/chat-execution-panel.tsx",
    }

    claim4_pass = (
        causal_ok
        and panel_would_render
        and any(inferred_name in str(n) for n in (result.assumption_notes or []))
    )
    evidence["claim_4"] = {
        "status": "PASS" if claim4_pass else ("PARTIAL" if causal_ok and panel_would_render else "FAIL"),
        "causation": evidence["causation"],
        "execution_assumption_notes": result.assumption_notes,
        "result_url": result.result_url,
        "success": result.success,
        "note": (
            "PASS requires: omit-name message → inferred_fields → execute_plan.assumption_notes "
            "containing the inferred value (panel contract)."
        ),
    }
    if result.success is False:
        evidence["claim_4"]["status"] = "PARTIAL" if causal_ok and notes_preview else "FAIL"
        evidence["claim_4"]["note"] += f" Live execute failed ({result.error_code}); notes_from_plan={notes_preview}"

    print("EXEC", json.dumps(evidence["execution"], indent=2))
    print("CLAIM4", json.dumps(evidence["claim_4"], indent=2))
    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write(evidence)


def _write(evidence: dict) -> None:
    out = REPO / "docs" / "delivery" / "wave67-partB-assumption-notes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print("WROTE", out)


if __name__ == "__main__":
    asyncio.run(main())
