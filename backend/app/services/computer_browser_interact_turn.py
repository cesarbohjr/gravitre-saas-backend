"""Governed public-browser interact WRITE on the canonical HMAC path.

EXTEND computer_execution + Playwright. Not a second agent runtime.
API-native HubSpot/Gmail writes stay on ActionSpec connectors.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.services.conversational_execution_service import CONFIRM_PATTERN
from app.services.execution_plan_service import (
    ExecutionPlan,
    ExecutionStep,
    execution_plan_patch,
    mark_plan_terminal,
    observations_patch,
)
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.read_preflight import PreflightResult
from app.services.tool_types import ToolContext, ToolValidationError

from datetime import datetime, timezone

ACTION_KEY = "browser_agent.interact"
_PUBLIC_FORM_URL = "https://httpbin.org/forms/post"
_HUBSPOT = re.compile(r"(?is)\bhubspot\b")
_INTERACT = re.compile(
    r"(?is)(?=.*\bhttpbin\.org\b)(?=.*\b(fill|submit|form|post)\b)"
)
_BARE_API_WRITE = re.compile(r"(?is)\b(create a hubspot|update a hubspot|gmail|send an email)\b")
_SECRET_FIELD = re.compile(r"(?i)(password|passwd|secret|token|ssn|api[_-]?key|authorization)")
_NAME_IN_SELECTOR = re.compile(r"""name\s*=\s*['"]([^'"]+)['"]""", re.I)
_WANTS_FRESH = re.compile(r"(?is)\b(refresh|reload|latest|rerun|re-run|recheck|fill again)\b")
_SHOW_ARTIFACT = re.compile(
    r"(?is)\b(show|open)\b.{0,40}\b(report|table|artifact|deliverable|brief|summary|form)\b"
)
_ASKS_SUBMITTED = re.compile(
    r"(?is)\b("
    r"email|name|custname|custemail|submitted|field"
    r"|what (?:did we|was) (?:submit|fill|post)"
    r"|which (?:email|name)"
    r"|form result|result url|endpoint"
    r")\b"
)


def match_computer_browser_interact(message: str) -> bool:
    text = message or ""
    if _HUBSPOT.search(text) and not re.search(r"(?is)\bdo not (?:use |open |call )?hubspot\b", text):
        return False
    if _BARE_API_WRITE.search(text):
        return False
    return bool(_INTERACT.search(text))


def computer_interact_pending_params(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    pending = (task_state or {}).get("pending_task") if isinstance(task_state, dict) else None
    if not isinstance(pending, dict):
        return None
    status = str(pending.get("status") or "").strip()
    if status not in {"awaiting_confirm", "awaiting_admin_approval"}:
        return None
    params = pending.get("params") if isinstance(pending.get("params"), dict) else pending
    invoke = str(params.get("invoke_action") or pending.get("invoke_action") or "").strip()
    if invoke != ACTION_KEY:
        return None
    return params if isinstance(params, dict) else None


def _field_from_selector(selector: str) -> str:
    match = _NAME_IN_SELECTOR.search(selector or "")
    if match:
        return str(match.group(1) or "").strip()
    return str(selector or "").strip()[:80]


def submitted_field_rows(
    *,
    args: dict[str, Any] | None,
    result_url: str | None,
    outcome: str,
    recorded_at: str,
) -> list[dict[str, Any]]:
    """Only sealed fill values. Never invent fields or keep secrets."""
    actions = (args or {}).get("actions") if isinstance(args, dict) else None
    rows: list[dict[str, Any]] = []
    if isinstance(actions, list):
        for step in actions:
            if not isinstance(step, dict):
                continue
            if str(step.get("type") or "").lower() not in {"fill", "type"}:
                continue
            field = _field_from_selector(str(step.get("selector") or ""))
            if not field or _SECRET_FIELD.search(field):
                continue
            value = str(step.get("value") or "")
            if _SECRET_FIELD.search(value):
                continue
            rows.append({"field": field, "value": value})
    target = str((args or {}).get("url") or "").strip()
    if target:
        rows.append({"field": "target", "value": target})
    if result_url:
        rows.append({"field": "result_url", "value": str(result_url)})
    rows.append({"field": "outcome", "value": outcome})
    rows.append({"field": "recorded_at", "value": recorded_at})
    return rows


def has_interact_artifact(task_state: dict[str, Any] | None) -> bool:
    state = task_state if isinstance(task_state, dict) else {}
    evidence = state.get("computer_browser_evidence")
    if isinstance(evidence, dict) and str(evidence.get("mode") or "") == "playwright_interact":
        return True
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    invoke = str(pending.get("invoke_action") or "")
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    if str(params.get("invoke_action") or invoke) == ACTION_KEY and str(pending.get("status") or "") in {
        "executed",
        "failed",
        "completed",
    }:
        return True
    for art in state.get("work_artifacts") or []:
        if not isinstance(art, dict):
            continue
        title = str(art.get("title") or "").lower()
        if "form" in title or "submitted" in title:
            return True
        meta = art.get("metadata") if isinstance(art.get("metadata"), dict) else {}
        if str(meta.get("execution_path") or "") == "computer_browser_interact_confirm":
            return True
    return False


def match_computer_interact_followup(message: str, task_state: dict[str, Any] | None) -> bool:
    text = message or ""
    if _HUBSPOT.search(text) and not re.search(r"(?is)\bdo not (?:use |open |call )?hubspot\b", text):
        return False
    if _WANTS_FRESH.search(text):
        return False
    if not (_SHOW_ARTIFACT.search(text) or _ASKS_SUBMITTED.search(text)):
        return False
    return has_interact_artifact(task_state)


def computer_interact_should_compile(message: str, task_state: dict[str, Any] | None) -> bool:
    if match_computer_browser_interact(message or ""):
        return True
    if CONFIRM_PATTERN.match((message or "").strip()) and computer_interact_pending_params(task_state):
        return True
    if match_computer_interact_followup(message or "", task_state):
        return True
    return False


def _rows_from_interact_state(task_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    state = task_state if isinstance(task_state, dict) else {}
    evidence = state.get("computer_browser_evidence")
    if isinstance(evidence, dict):
        rows = evidence.get("submitted_fields")
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict) and row.get("field")]
    for obs in reversed(list(state.get("execution_observations") or [])):
        if not isinstance(obs, dict):
            continue
        blob = obs.get("structured") if isinstance(obs.get("structured"), dict) else {}
        rows = blob.get("rows")
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict) and row.get("field")]
    return []


def answer_from_interact_artifact(message: str, task_state: dict[str, Any] | None) -> str:
    """Answer only from persisted submitted fields. Never invent a value."""
    rows = _rows_from_interact_state(task_state)
    by_field = {
        str(row.get("field") or "").strip().lower(): str(row.get("value") or "")
        for row in rows
        if str(row.get("field") or "").strip()
    }
    text = (message or "").lower()
    if re.search(r"(?is)\bemail\b", text) and "custemail" in by_field:
        return by_field["custemail"]
    if re.search(r"(?is)\bname\b", text) and "custname" in by_field:
        return by_field["custname"]
    if re.search(r"(?is)\b(url|endpoint|page)\b", text):
        return by_field.get("result_url") or by_field.get("target") or "That form result did not record a URL."
    if rows:
        lines = ["Submitted public form fields:"]
        for row in rows:
            lines.append(f"- {row.get('field')}: {row.get('value')}")
        return "\n".join(lines)
    arts = (task_state or {}).get("work_artifacts") if isinstance(task_state, dict) else None
    if isinstance(arts, list) and arts:
        meta = arts[-1].get("metadata") if isinstance(arts[-1], dict) else {}
        code = str((meta or {}).get("code") or "").strip()
        if code:
            return code
    return "I still have the form task, but it does not include submitted field values."


def _frozen_form_args() -> dict[str, Any]:
    return {
        "url": _PUBLIC_FORM_URL,
        "actions": [
            {"type": "fill", "selector": "input[name='custname']", "value": "Gravitre isolated test"},
            {"type": "fill", "selector": "input[name='custemail']", "value": "isolated@gravitre.test"},
            {"type": "click", "selector": "text=Submit order"},
        ],
    }


def _proof_from_pending(raw: dict[str, Any] | None) -> PreflightResult | None:
    if not isinstance(raw, dict):
        return None
    status = str(raw.get("status") or "")
    digest = str(raw.get("proof_digest") or "")
    if status != "ready" or not digest:
        return None
    return PreflightResult(
        status="ready",
        plan_id=raw.get("plan_id"),
        step_id=raw.get("step_id"),
        action_key=str(raw.get("action_key") or ACTION_KEY),
        connector_id=str(raw.get("connector_id") or "browser_agent"),
        resource=raw.get("resource") if isinstance(raw.get("resource"), dict) else None,
        compiled_parameters=safe_normalize_stored_dict(raw.get("compiled_parameters")),
        org_id=str(raw.get("org_id") or ""),
        spec_revision=str(raw.get("spec_revision") or ""),
        proof_digest=digest,
        capability_id=raw.get("capability_id"),
    )


async def try_computer_browser_interact_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any] | None:
    del connected_integrations
    state = dict(task_state or {})
    pending_params = computer_interact_pending_params(state)
    if pending_params and CONFIRM_PATTERN.match((message or "").strip()):
        return await _execute_confirmed_interact(
            org_id=org_id,
            client=client,
            settings=settings,
            task_state=state,
            pending_params=pending_params,
            user_id=user_id,
            conversation_id=conversation_id,
        )
    if match_computer_interact_followup(message or "", state):
        from app.services.durable_work_session import reconstruct_execution_result

        body = answer_from_interact_artifact(message or "", state)
        reconstructed = reconstruct_execution_result(state, body=body)
        plan = ExecutionPlan.from_dict(state.get("execution_plan"))
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": body,
            "task_state": state,
            "workflow_status": "completed",
            "execution_path": "computer_browser_interact_resume",
            "execution_result": reconstructed,
            "provider_reinvoked": False,
            "writes_started": False,
            "plan_id": plan.plan_id if plan is not None else None,
        }
    if not match_computer_browser_interact(message or ""):
        return None
    return _compile_interact(
        message=message or "",
        org_id=org_id,
        client=client,
        settings=settings,
        task_state=state,
        user_id=user_id,
        conversation_id=conversation_id,
    )


def _compile_interact(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    task_state: dict[str, Any],
    user_id: str | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    from app.services.sealed_read_execution import attributable_read_actor_id
    from app.services.write_preflight import compile_write_for_context

    existing = ExecutionPlan.from_dict(task_state.get("execution_plan"))
    plan_id = existing.plan_id if existing is not None else str(uuid4())
    step = ExecutionStep(
        step_id="computer_interact",
        title="Public browser form fill",
        kind="write",
        connector_id="browser_agent",
        action_key=ACTION_KEY,
    )
    plan = ExecutionPlan(
        plan_id=plan_id,
        summary="Fill the public httpbin form after approval",
        objective=message[:240],
        steps=[step],
        source="computer_execution",
        execution_strategy="browser_cdp",
        capability_id="computer.browser.interact",
    )
    actor_id = attributable_read_actor_id(user_id) or "computer-interact"
    ctx = ToolContext(
        settings=settings or get_settings(),
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id=plan.capability_id,
        conversation_id=conversation_id,
        step_id=step.step_id,
    )
    proposed = _frozen_form_args()
    proof = compile_write_for_context(
        ctx=ctx,
        invoke_action=ACTION_KEY,
        args=proposed,
        user_message=message,
        connected_integrations=["browser_agent"],
        task_state=task_state,
    )
    if not proof.ok:
        plan = mark_plan_terminal(plan, "blocked")
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": proof.user_message()
            or "I couldn't compile that public form fill. Nothing was submitted.",
            "task_state": {**task_state, **execution_plan_patch(plan)},
            "workflow_status": "blocked",
            "execution_path": "computer_browser_interact_compile",
            "writes_started": False,
            "provider_reinvoked": False,
        }
    from app.services.spoken_write_approval import stamp_pending_write_binding

    pending_task = stamp_pending_write_binding(
        {
            "status": "awaiting_confirm",
            "type": "connector_action",
            "invoke_action": ACTION_KEY,
            "kind": "write",
            "params": {
                "invoke_action": ACTION_KEY,
                "integration": "browser_agent",
                "kind": "write",
                "requires_approval": True,
                "args": dict(proof.compiled_parameters),
                "preflight_proof": {
                    **proof.as_dict(),
                    "org_id": proof.org_id,
                    "proof_digest": proof.proof_digest,
                    "spec_revision": proof.spec_revision,
                },
            },
        },
        org_id=org_id,
        actor_id=user_id,
        conversation_id=conversation_id,
        invoke_action=ACTION_KEY,
    )
    plan = mark_plan_terminal(plan, "awaiting_confirm")
    return {
        "stop_pipeline": True,
        "dialogue_mode": "confirm",
        "message": (
            "I can fill the public httpbin.org form with the isolated test name and email, "
            "then submit it. Nothing has been submitted yet. Say yes to approve."
        ),
        "task_state": {
            **task_state,
            **execution_plan_patch(plan),
            "pending_task": pending_task,
        },
        "workflow_status": "awaiting_confirm",
        "execution_path": "computer_browser_interact_compile",
        "writes_started": False,
        "provider_reinvoked": False,
        "selected_action": ACTION_KEY,
        "plan_id": plan.plan_id,
    }


async def _execute_confirmed_interact(
    *,
    org_id: str,
    client: Any,
    settings: Settings | None,
    task_state: dict[str, Any],
    pending_params: dict[str, Any],
    user_id: str | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    from app.services.browser_agent_service import BrowserAgentError, browser_agent_interact
    from app.services.computer_execution import observation_from_browser_result
    from app.services.durable_work_session import bind_finished_work, execution_result_from_finished_work
    from app.services.sealed_read_execution import attributable_read_actor_id
    from app.services.write_preflight import enforce_invoke_write_preflight

    proof = _proof_from_pending(pending_params.get("preflight_proof"))
    args = safe_normalize_stored_dict(pending_params.get("args"))
    if proof is None:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": "That browser form fill wasn't compiled before confirmation. Nothing was submitted.",
            "task_state": task_state,
            "workflow_status": "blocked",
            "execution_path": "computer_browser_interact_confirm",
            "writes_started": False,
        }
    actor_id = attributable_read_actor_id(user_id) or "computer-interact"
    ctx = ToolContext(
        settings=settings or get_settings(),
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=proof.plan_id,
        capability_id=proof.capability_id,
        conversation_id=conversation_id,
        step_id=proof.step_id,
        preflight_result=proof,
    )
    try:
        sealed = enforce_invoke_write_preflight(ctx, ACTION_KEY, args)
    except ToolValidationError as exc:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": str(exc) or "The compiled form fill no longer matches. Nothing was submitted.",
            "task_state": task_state,
            "workflow_status": "blocked",
            "execution_path": "computer_browser_interact_confirm",
            "writes_started": False,
        }
    url = str(sealed.get("url") or "")
    actions = sealed.get("actions")
    try:
        raw = await browser_agent_interact(
            url,
            actions=actions if isinstance(actions, list) else [],
            settings=settings or get_settings(),
            approval_id=str(proof.proof_digest),
            hmac_verified=True,
        )
    except BrowserAgentError as exc:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": str(exc) or "The public form fill did not complete. Nothing further was submitted.",
            "task_state": {
                **task_state,
                "pending_task": {
                    **safe_normalize_stored_dict(task_state.get("pending_task")),
                    "status": "failed",
                },
            },
            "workflow_status": "failed",
            "execution_path": "computer_browser_interact_confirm",
            "writes_started": True,
            "provider_reinvoked": True,
        }
    plan = ExecutionPlan.from_dict(task_state.get("execution_plan")) or ExecutionPlan(
        plan_id=str(proof.plan_id or uuid4()),
        summary="Public browser form fill",
        source="computer_execution",
        steps=[
            ExecutionStep(
                step_id="computer_interact",
                title="Public browser form fill",
                kind="write",
                action_key=ACTION_KEY,
            )
        ],
    )
    obs = observation_from_browser_result(
        plan=plan,
        result={
            **raw,
            "strategy": "browser_cdp",
            "success": bool(raw.get("success", not raw.get("pending_approval"))),
        },
        approval_id=str(proof.proof_digest),
    )
    success = bool(obs.success)
    plan = mark_plan_terminal(plan, "completed" if success else "failed")
    result_url = str(raw.get("url") or url or "")
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    outcome = "completed" if success else "failed"
    field_rows = submitted_field_rows(
        args=args if isinstance(args, dict) else {},
        result_url=result_url or None,
        outcome=outcome,
        recorded_at=recorded_at,
    )
    structured = dict(obs.structured)
    structured["rows"] = field_rows
    structured["plan_id"] = plan.plan_id
    structured["observation_id"] = obs.observation_id
    structured["verified"] = success
    obs.structured = structured
    summary = (
        f"Submitted the public httpbin form. Current URL: {result_url}."
        if success
        else str(raw.get("message") or "The public form fill did not complete.")
    )
    obs.summary = summary[:500]
    merged = {
        **task_state,
        **execution_plan_patch(plan),
        **observations_patch([obs]),
        "pending_task": {
            **safe_normalize_stored_dict(task_state.get("pending_task")),
            "status": "executed" if success else "failed",
        },
        "pending_action": {"status": "executed", "action": ACTION_KEY, "write_allowed": False},
        "computer_browser_evidence": {
            "strategy": "browser_cdp",
            "mode": raw.get("mode"),
            "url": result_url,
            "steps": raw.get("steps") or [],
            "submitted_fields": field_rows,
            "recorded_at": recorded_at,
        },
    }
    merged = bind_finished_work(merged, body=summary, title="Submitted public form fields")
    arts = merged.get("work_artifacts")
    if isinstance(arts, list) and arts and isinstance(arts[-1], dict):
        meta = arts[-1].get("metadata") if isinstance(arts[-1].get("metadata"), dict) else {}
        arts[-1]["metadata"] = {
            **meta,
            "execution_path": "computer_browser_interact_confirm",
            "verified": success,
            "recorded_at": recorded_at,
            "rows": field_rows,
        }
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": summary,
        "task_state": merged,
        "workflow_status": "completed" if success else "failed",
        "execution_path": "computer_browser_interact_confirm",
        "execution_result": execution_result_from_finished_work(merged, body=summary, success=success),
        "writes_started": True,
        "provider_reinvoked": True,
        "plan_id": plan.plan_id,
    }
