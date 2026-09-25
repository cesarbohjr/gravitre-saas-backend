"""Natural-language READ-only browser session on the canonical plan.

EXTEND computer_execution + Playwright. Not a second agent runtime.
No provider WRITE. Form fill stays on approval-gated interact.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.services.computer_execution import (
    classify_execution_strategy,
    execute_playwright_browser_read,
)
from app.services.execution_plan_service import (
    ExecutionPlan,
    ExecutionStep,
    execution_plan_patch,
    mark_plan_terminal,
    observations_patch,
)

_START_URL = "https://example.com/"
_FOLLOW_TEXT = "More information"

_BROWSER_PUBLIC = re.compile(
    r"(?is)(?=.*\b(example\.com|iana\.org)\b)"
    r"(?=.*\b(browser|playwright|navigate|open|visit|browse|follow|click)\b)"
)
_WANTS_FRESH = re.compile(r"(?is)\b(refresh|reload|latest|rerun|re-run|recheck)\b")
_NEGATED_REPLAY = re.compile(r"(?is)\bdo not (?:browse|open|run) again\b")
_REPLAY = re.compile(r"(?is)\bbrowse again\b")
_SHOW_BOUND = re.compile(
    r"(?is)\b(show|open)\b.{0,40}\b(report|table|artifact|deliverable|brief|summary)\b"
)
_FOLLOWUP = re.compile(
    r"(?is)\b("
    r"second page"
    r"|what (?:was|is) the (?:second |final )?(?:page )?(?:title|url)"
    r"|what did (?:you|the browser) (?:see|observe)"
    r"|iana"
    r"|more information"
    r"|those pages"
    r"|that page"
    r")\b"
)
_HUBSPOT = re.compile(r"(?is)\bhubspot\b")
_BARE_WRITE = re.compile(r"(?is)\b(create|update|delete|submit|purchase|checkout)\b")


def match_computer_browser_intent(message: str) -> bool:
    text = message or ""
    if not _BROWSER_PUBLIC.search(text):
        return False
    if _HUBSPOT.search(text) and not re.search(r"(?is)\bdo not (?:use |open |call )?hubspot\b", text):
        return False
    if _BARE_WRITE.search(text) and not re.search(r"(?is)\bdo not (?:create|update|delete|submit)\b", text):
        return False
    return True


def match_computer_browser_resume_phrase(message: str) -> bool:
    text = message or ""
    if _HUBSPOT.search(text):
        return False
    if _WANTS_FRESH.search(text):
        return False
    if _REPLAY.search(text) and not _NEGATED_REPLAY.search(text):
        return False
    return bool(_SHOW_BOUND.search(text) or _FOLLOWUP.search(text))


def match_computer_browser_followup(message: str, task_state: dict[str, Any] | None) -> bool:
    text = message or ""
    if not match_computer_browser_resume_phrase(text):
        return False
    plan = ExecutionPlan.from_dict((task_state or {}).get("execution_plan"))
    return plan is not None and plan.source == "computer_execution"


def _user_summary(visits: list[dict[str, Any]], *, success: bool, error: str | None) -> str:
    if not success and error:
        return error
    if not visits:
        return "The browser session did not capture a page."
    lines = [
        "I opened a real browser (not an HTTP fetch) and recorded what loaded.",
    ]
    for index, visit in enumerate(visits, start=1):
        title = str(visit.get("title") or "").strip() or "(no title)"
        url = str(visit.get("url") or "").strip()
        action = str(visit.get("action") or "goto")
        err = str(visit.get("error") or "").strip()
        if err:
            lines.append(f"Step {index} ({action}) failed: {err}")
            continue
        lines.append(f"Step {index} ({action}): {title} — {url}")
    return "\n".join(lines)


async def try_computer_browser_read_turn(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    settings: Settings | None = None,
    conversation_id: str | None = None,
    org_id: str | None = None,
    client: Any = None,
) -> dict[str, Any] | None:
    state = dict(task_state or {})
    if match_computer_browser_resume_phrase(message or "") and not match_computer_browser_followup(
        message or "", state
    ):
        if conversation_id and org_id and client is not None:
            try:
                from app.services.conversation_state_service import get_conversation_state_service

                loaded = await get_conversation_state_service(settings).get_task_state(
                    conversation_id, org_id, client=client
                )
                if isinstance(loaded, dict) and loaded:
                    state = loaded
            except Exception:  # noqa: BLE001
                pass
    if match_computer_browser_followup(message or "", state):
        from app.services.durable_work_session import reconstruct_execution_result

        deliv = state.get("durable_deliverable") if isinstance(state.get("durable_deliverable"), dict) else None
        diagnosis = str((deliv or {}).get("diagnosis") or "")
        reconstructed = reconstruct_execution_result(state, body=diagnosis)
        plan = ExecutionPlan.from_dict(state.get("execution_plan"))
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": diagnosis
            or str((reconstructed or {}).get("body") or "I still have that browser report."),
            "task_state": state,
            "workflow_status": "completed",
            "execution_path": "computer_browser_read_resume",
            "execution_result": reconstructed,
            "provider_reinvoked": False,
            "writes_started": False,
            "plan_id": plan.plan_id if plan is not None else None,
        }
    if not match_computer_browser_intent(message or ""):
        return None
    strategy = classify_execution_strategy(requires_graphical_ui=True, has_action_spec=False)
    existing = ExecutionPlan.from_dict((task_state or {}).get("execution_plan"))
    plan_id = existing.plan_id if existing is not None else str(uuid4())
    step = ExecutionStep(
        step_id="computer_primary",
        title="Public browser READ",
        kind="read",
        connector_id="browser",
        action_key="browser_agent.playwright_session",
    )
    plan = ExecutionPlan(
        plan_id=plan_id,
        summary="Browse example.com then follow More information",
        objective=str(message or "")[:240],
        steps=[step],
        source="computer_execution",
        execution_strategy=strategy,
        continuation_of_plan_id=existing.plan_id if existing is not None else None,
    )
    if existing is not None:
        plan.plan_id = existing.plan_id
    raw, obs = await execute_playwright_browser_read(
        _START_URL,
        follow_link_text=_FOLLOW_TEXT,
        plan=plan,
        settings=settings or get_settings(),
    )
    visits = list(raw.get("visits") or [])
    success = bool(raw.get("success"))
    summary = _user_summary(visits, success=success, error=str(raw.get("message") or "") or None)
    obs.summary = summary.split("\n", 1)[0][:500]
    structured = dict(obs.structured)
    structured["rows"] = [
        {
            "step": str(index),
            "title": str(row.get("title") or ""),
            "url": str(row.get("url") or ""),
            "action": str(row.get("action") or ""),
        }
        for index, row in enumerate(visits, start=1)
        if isinstance(row, dict)
    ]
    obs.structured = structured
    if success:
        terminal = "completed"
    elif visits:
        terminal = "partial"
    else:
        terminal = "failed"
    plan = mark_plan_terminal(plan, terminal)
    from app.services.durable_work_session import bind_finished_work, execution_result_from_finished_work

    merged = {
        **(task_state or {}),
        **execution_plan_patch(plan),
        **observations_patch([obs]),
        "computer_browser_evidence": {
            "strategy": strategy,
            "mode": raw.get("mode"),
            "cdp_trace_id": raw.get("cdp_trace_id"),
            "screenshot_digest": raw.get("screenshot_digest"),
            "visits": visits,
        },
    }
    merged = bind_finished_work(merged, body=summary, title="Public web research summary")
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": summary,
        "task_state": merged,
        "workflow_status": "completed" if success else "failed",
        "execution_path": "computer_browser_read",
        "execution_result": execution_result_from_finished_work(merged, body=summary, success=success),
        "writes_started": False,
        "provider_reinvoked": True,
        "plan_id": plan.plan_id,
        "execution_strategy": strategy,
    }
