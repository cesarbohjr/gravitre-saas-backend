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
_ASKS_OBSERVED_PAGE = re.compile(
    r"(?is)\b("
    r"second page|first page|final page|last page"
    r"|(?:page|site) (?:url|title|link)"
    r"|(?:url|title|link) of the (?:second |first |final |last )?page"
    r"|ended up on"
    r"|the page we"
    r"|pages we (?:opened|visited|loaded)"
    r"|what did (?:you|we|the browser) (?:see|observe|open|load)"
    r"|those pages|that page"
    r"|visited urls?"
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
    if _HUBSPOT.search(text) and not re.search(r"(?is)\bdo not (?:use |open |call )?hubspot\b", text):
        return False
    if _WANTS_FRESH.search(text):
        return False
    if _REPLAY.search(text) and not _NEGATED_REPLAY.search(text):
        return False
    return bool(_SHOW_BOUND.search(text) or _ASKS_OBSERVED_PAGE.search(text))


def visits_from_computer_state(task_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    state = task_state if isinstance(task_state, dict) else {}
    evidence = state.get("computer_browser_evidence")
    if isinstance(evidence, dict):
        rows = evidence.get("visits")
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict)]
    observations = state.get("execution_observations") or []
    for row in reversed(list(observations)):
        if not isinstance(row, dict):
            continue
        blob = row.get("structured") if isinstance(row.get("structured"), dict) else {}
        visits = blob.get("visits")
        if isinstance(visits, list) and visits:
            return [item for item in visits if isinstance(item, dict)]
        nested_rows = blob.get("rows")
        if isinstance(nested_rows, list) and nested_rows:
            return [item for item in nested_rows if isinstance(item, dict)]
    return []


def has_completed_computer_session(task_state: dict[str, Any] | None) -> bool:
    if visits_from_computer_state(task_state):
        return True
    evidence = (task_state or {}).get("computer_browser_evidence") if isinstance(task_state, dict) else None
    return isinstance(evidence, dict) and str(evidence.get("mode") or "") == "playwright_session_read"


def match_computer_browser_followup(message: str, task_state: dict[str, Any] | None) -> bool:
    if not match_computer_browser_resume_phrase(message or ""):
        return False
    return has_completed_computer_session(task_state)


def _pick_visit(message: str, visits: list[dict[str, Any]]) -> dict[str, Any]:
    text = (message or "").lower()
    if re.search(r"(?is)\b(first|started|initial)\b", text):
        return visits[0]
    if re.search(r"(?is)\b(second|final|last|ended up)\b", text) or len(visits) > 1:
        return visits[-1]
    return visits[0]


def answer_from_computer_visits(message: str, visits: list[dict[str, Any]]) -> str:
    """Answer from stored visits only. Never invent a URL or title."""
    if not visits:
        return "I still have the browser report, but it does not include page visits."
    target = _pick_visit(message, visits)
    title = str(target.get("title") or "").strip()
    url = str(target.get("url") or "").strip()
    text = (message or "").lower()
    wants_url = bool(re.search(r"(?is)\b(url|link|address)\b", text))
    wants_title = bool(re.search(r"(?is)\btitle\b", text) or "ended up" in text)
    if wants_url and not wants_title:
        return url or "That browser visit did not record a URL."
    if wants_title and not wants_url:
        return title or "That browser visit did not record a title."
    if url and title:
        return f"{title} — {url}"
    return url or title or _user_summary(visits, success=True, error=None)


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

        visits = visits_from_computer_state(state)
        body = answer_from_computer_visits(message or "", visits)
        if (not visits) or body.startswith("I still have the browser report"):
            deliv = state.get("durable_deliverable") if isinstance(state.get("durable_deliverable"), dict) else None
            diagnosis = str((deliv or {}).get("diagnosis") or "").strip()
            if diagnosis:
                body = diagnosis
        reconstructed = reconstruct_execution_result(state, body=body)
        plan = ExecutionPlan.from_dict(state.get("execution_plan"))
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": body,
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
