"""Structured continuation for offered READ inspections.

A prose offer ("I can check connector health…") is presentation. The
actionable intent must live on task_state.offered_action so a later
confirm token can execute without re-planning the business problem.

Does not own write confirmation. pending_task awaiting_confirm still
owns yes/no for writes.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from app.core.logging import get_logger
from app.services.conversational_execution_service import CONFIRM_PATTERN, DECLINE_PATTERN

logger = get_logger(__name__)

OfferedStatus = Literal[
    "awaiting_user_confirmation",
    "confirmed",
    "executing",
    "completed",
    "failed",
    "declined",
    "cancelled",
]

ContinuationKind = Literal[
    "execute_read",
    "decline",
    "topic_change",
    "none",
]

READ_TOOLS_BY_SCOPE: dict[str, str] = {
    "connectors": "connector_status",
    "workflows": "workflow_runs",
    "agents": "agent_status",
    "analytics": "analytics",
}

SCOPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("connectors", re.compile(r"\bconnectors?\b|\bconnector health\b|\boauth\b", re.I)),
    ("workflows", re.compile(r"\bworkflows?\b|\brun(?:s| history)?\b|\bautomations?\b", re.I)),
    ("agents", re.compile(r"\bagents?\b|\bagent status\b", re.I)),
    ("analytics", re.compile(r"\banalytics\b|\bkpis?\b|\bbusiness activity\b|\borg analytics\b", re.I)),
)

_OFFER_RE = re.compile(
    r"(?i)("
    r"if you want.{0,80}(?:i can|i could|want me to)|"
    r"i can check|"
    r"i could check|"
    r"want me to|"
    r"would you like me to|"
    r"shall i|"
    r"should i (?:check|look|pull)|"
    r"happy to check"
    r")"
)

_CLAIMS_FUTURE_RE = re.compile(
    r"(?i)\b("
    r"i(?:['’]ll| will) (?:check|look|pull|pull up|inspect|review)|"
    r"let me check|"
    r"i(?:['’]m| am) (?:going to|gonna) check|"
    r"checking now|"
    r"i(?:['’]ll| will) take a look"
    r")\b"
)

_WRITE_OFFER_RE = re.compile(
    r"(?i)\b(send|create|update|post|delete|publish|execute the write|approve this send)\b"
)

PROGRESS_ACK = "Checking now…"
TOOL_TIMEOUT_S = 8.0
TURN_TIMEOUT_S = 25.0

ContinuationTerminal = Literal[
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "CANCELLED",
    "CLARIFICATION_REQUIRED",
]


@dataclass
class OfferedAction:
    id: str
    type: str = "business_health_check"
    scope: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    status: OfferedStatus = "awaiting_user_confirmation"
    source: str = "assistant_offer"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "scope": list(self.scope),
            "tools": list(self.tools),
            "confirmation_required": bool(self.confirmation_required),
            "status": self.status,
            "source": self.source,
        }


@dataclass
class ContinuationDecision:
    kind: ContinuationKind
    offered: OfferedAction | None = None
    reason: str = ""


def is_confirm_utterance(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(CONFIRM_PATTERN.match(text) or text.lower() in {"yes", "y", "ok", "okay", "confirm"})


def is_decline_utterance(message: str) -> bool:
    return bool(DECLINE_PATTERN.match((message or "").strip()))


def claims_future_action(text: str) -> bool:
    return bool(_CLAIMS_FUTURE_RE.search(text or ""))


def last_assistant_text(history: list[dict[str, Any]] | None) -> str:
    for row in reversed(history or []):
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").strip().lower()
        if role != "assistant":
            continue
        return str(row.get("content") or row.get("text") or "")
    return ""


def _scopes_from_text(text: str) -> list[str]:
    found: list[str] = []
    for scope, pattern in SCOPE_PATTERNS:
        if pattern.search(text or "") and scope not in found:
            found.append(scope)
    return found


def extract_offered_action(text: str) -> OfferedAction | None:
    """Parse an assistant offer into structured READ continuation state.

    Returns None when the text is not an offer, or when it is a write offer
    (those stay on pending_task / write gates).
    """
    body = (text or "").strip()
    if not body or not _OFFER_RE.search(body):
        return None
    if _WRITE_OFFER_RE.search(body) and not _OFFER_RE.search(body):
        return None
    if re.search(r"(?i)\b(send|create|post|delete)\b.{0,40}\b(email|message|campaign|workflow)\b", body):
        return None
    scopes = _scopes_from_text(body)
    if not scopes:
        scopes = list(READ_TOOLS_BY_SCOPE.keys())
    tools = [READ_TOOLS_BY_SCOPE[s] for s in scopes if s in READ_TOOLS_BY_SCOPE]
    if not tools:
        return None
    return OfferedAction(
        id=str(uuid4()),
        scope=scopes,
        tools=tools,
        confirmation_required=False,
        status="awaiting_user_confirmation",
    )


def offered_from_state(task_state: dict[str, Any] | None) -> OfferedAction | None:
    raw = (task_state or {}).get("offered_action") if isinstance(task_state, dict) else None
    if not isinstance(raw, dict):
        return None
    status = str(raw.get("status") or "").strip()
    if status not in {
        "awaiting_user_confirmation",
        "confirmed",
        "executing",
    }:
        return None
    tools = [str(t) for t in (raw.get("tools") or []) if str(t) in READ_TOOLS_BY_SCOPE.values()]
    scope = [str(s) for s in (raw.get("scope") or []) if str(s) in READ_TOOLS_BY_SCOPE]
    if not tools and scope:
        tools = [READ_TOOLS_BY_SCOPE[s] for s in scope]
    if not tools:
        return None
    return OfferedAction(
        id=str(raw.get("id") or uuid4()),
        type=str(raw.get("type") or "business_health_check"),
        scope=scope or [k for k, v in READ_TOOLS_BY_SCOPE.items() if v in tools],
        tools=tools,
        confirmation_required=bool(raw.get("confirmation_required")),
        status=status,  # type: ignore[arg-type]
        source=str(raw.get("source") or "assistant_offer"),
    )


def pending_write_owns_confirm(task_state: dict[str, Any] | None) -> bool:
    from app.services.pending_reply_classifier import PENDING_AWAITING_STATUSES, has_pending_family

    if not has_pending_family(task_state):
        return False
    pending = (task_state or {}).get("pending_task") if isinstance(task_state, dict) else None
    if not isinstance(pending, dict) or not pending:
        return True
    status = str(pending.get("status") or "")
    return status in PENDING_AWAITING_STATUSES or bool(
        (task_state or {}).get("current_plan")
    )


def resolve_offered_action_turn(
    message: str,
    *,
    task_state: dict[str, Any] | None,
    conversation_history: list[dict[str, Any]] | None = None,
) -> ContinuationDecision:
    if pending_write_owns_confirm(task_state):
        return ContinuationDecision(kind="none", reason="pending_write_owns_confirm")
    stored = offered_from_state(task_state)
    offered = stored or extract_offered_action(last_assistant_text(conversation_history))
    if offered is None:
        return ContinuationDecision(kind="none", reason="no_offered_action")
    if is_decline_utterance(message):
        offered.status = "declined"
        return ContinuationDecision(kind="decline", offered=offered, reason="user_declined")
    if is_confirm_utterance(message):
        offered.status = "confirmed"
        return ContinuationDecision(kind="execute_read", offered=offered, reason="user_confirmed")
    return ContinuationDecision(kind="topic_change", offered=offered, reason="user_changed_topic")


def progress_steps_for_scopes(scope: list[str], *, current: str | None = None) -> list[str]:
    labels = {
        "connectors": "Checking connectors",
        "workflows": "Checking workflows",
        "agents": "Checking agents",
        "analytics": "Checking analytics",
    }
    steps: list[str] = []
    seen_current = current is None
    for name in scope:
        label = labels.get(name)
        if not label:
            continue
        if not seen_current and name == current:
            steps.append(f"Running: {label}")
            seen_current = True
        elif not seen_current:
            steps.append(f"Completed: {label}")
        else:
            steps.append(label)
    return steps


def _connector_attention_lines(output: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    connectors = output.get("connectors") if isinstance(output.get("connectors"), list) else []
    for row in connectors:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("display_name") or row.get("vendor") or "Connector")
        status = str(row.get("status") or row.get("state") or row.get("health") or "").lower()
        message = str(row.get("message") or row.get("error") or row.get("reason") or "").strip()
        attention = status in {
            "error",
            "failed",
            "disconnected",
            "token_expired",
            "pending_auth",
            "misconfigured",
            "degraded",
            "expired",
        }
        if attention:
            detail = message or status.replace("_", " ")
            lines.append(f"**{name}** — {detail}")
        elif message and "expir" in message.lower():
            lines.append(f"**{name}** — {message}")
    return lines[:6]


def _workflow_attention_lines(output: dict[str, Any]) -> list[str]:
    runs = output.get("runs") if isinstance(output.get("runs"), list) else []
    failed = [
        row
        for row in runs
        if isinstance(row, dict)
        and str(row.get("status") or "").lower() in {"failed", "error", "cancelled"}
    ]
    if not failed:
        return []
    grouped: dict[str, int] = {}
    for row in failed:
        name = str(row.get("workflowName") or row.get("workflowId") or "Workflow")
        grouped[name] = grouped.get(name, 0) + 1
    lines = [
        f"**{name}** — {count} failed run{'s' if count != 1 else ''} in recent history."
        for name, count in list(grouped.items())[:5]
    ]
    return lines


def _agent_attention_lines(output: dict[str, Any]) -> list[str]:
    agents = output.get("agents") if isinstance(output.get("agents"), list) else []
    lines: list[str] = []
    for row in agents:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "Agent")
        status = str(row.get("status") or "").lower()
        rate = row.get("successRate")
        if status in {"error", "failed", "paused", "degraded"}:
            lines.append(f"**{name}** — status is {status}.")
        elif isinstance(rate, (int, float)) and rate < 80:
            lines.append(f"**{name}** — success rate is {int(rate)}%.")
    return lines[:5]


def _analytics_attention_lines(output: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if output.get("error"):
        lines.append(f"Business analytics were unavailable ({output.get('error')}).")
        return lines
    alerts = output.get("openAlerts")
    if isinstance(alerts, int) and alerts > 0:
        lines.append(f"**Org alerts** — {alerts} open alert{'s' if alerts != 1 else ''}.")
    last7 = output.get("last7Days") if isinstance(output.get("last7Days"), dict) else {}
    breakdown = last7.get("statusBreakdown") if isinstance(last7.get("statusBreakdown"), dict) else {}
    failed = int(breakdown.get("failed") or 0)
    if failed:
        lines.append(f"**Workflow volume** — {failed} failed runs in the last 7 days.")
    return lines


def synthesize_health_findings(
    tool_results: list[dict[str, Any]],
    *,
    partial: bool = False,
    timed_out: list[str] | None = None,
) -> str:
    findings: list[str] = []
    failures: list[str] = []
    for row in tool_results:
        name = str(row.get("name") or "")
        output = row.get("output") if isinstance(row.get("output"), dict) else {}
        if output.get("error"):
            label = {
                "connector_status": "connector health",
                "workflow_runs": "workflow runs",
                "agent_status": "agent status",
                "analytics": "business analytics",
            }.get(name, name)
            failures.append(label)
            continue
        if name == "connector_status":
            findings.extend(_connector_attention_lines(output))
        elif name == "workflow_runs":
            findings.extend(_workflow_attention_lines(output))
        elif name == "agent_status":
            findings.extend(_agent_attention_lines(output))
        elif name == "analytics":
            findings.extend(_analytics_attention_lines(output))

    timeout_note = ""
    if timed_out:
        labels = ", ".join(timed_out)
        timeout_note = f" {labels} timed out."

    if findings:
        bullets = "\n".join(f"- {line}" for line in findings[:8])
        prefix = "I found things that need attention:"
        if partial:
            prefix = "I couldn't finish every check, but here is what I can see:"
        return f"{prefix}\n\n{bullets}{timeout_note}".strip()

    if failures and not tool_results:
        return "I couldn't complete the health check because the required systems didn't respond."
    if failures:
        joined = ", ".join(failures)
        return (
            f"I couldn't complete the full check. {joined} did not respond."
            f"{timeout_note}"
        ).strip()
    if timed_out:
        return (
            "I couldn't complete the health check because the required systems didn't respond."
            f"{timeout_note}"
        ).strip()
    return "I checked the available systems and didn't find anything urgent right now."


async def execute_offered_read(
    offered: OfferedAction,
    *,
    org_id: str,
    settings: Any,
    user_id: str | None = None,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Run the offered READ tools. Never invents findings."""
    from app.services.assistant_tools import run_assistant_tools

    offered.status = "executing"
    started = time.perf_counter()
    timed_out: list[str] = []
    collected: list[dict[str, Any]] = []

    async def _one(name: str) -> dict[str, Any]:
        try:
            rows = await asyncio.wait_for(
                run_assistant_tools(
                    [name],
                    org_id,
                    "what needs attention",
                    settings,
                    user_id=user_id,
                    environment_name=environment_name,
                ),
                timeout=TOOL_TIMEOUT_S,
            )
            return rows[0] if rows else {"name": name, "output": {"error": "empty_tool_result"}}
        except TimeoutError:
            timed_out.append(name)
            return {"name": name, "output": {"error": "timeout"}}
        except Exception as exc:  # noqa: BLE001
            logger.warning("offered_read_tool_failed tool=%s error=%s", name, exc)
            return {"name": name, "output": {"error": str(exc)[:200]}}

    try:
        collected = await asyncio.wait_for(
            asyncio.gather(*[_one(name) for name in offered.tools]),
            timeout=TURN_TIMEOUT_S,
        )
    except TimeoutError:
        timed_out = list(offered.tools)
        if not collected:
            collected = [{"name": name, "output": {"error": "timeout"}} for name in offered.tools]

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    failed = [row for row in collected if isinstance(row.get("output"), dict) and row["output"].get("error")]
    terminal: ContinuationTerminal = "COMPLETED"
    if failed and len(failed) == len(collected):
        terminal = "FAILED"
        offered.status = "failed"
    else:
        offered.status = "completed"
    message = synthesize_health_findings(
        list(collected),
        partial=bool(failed) and terminal == "COMPLETED",
        timed_out=[
            {
                "connector_status": "connector health",
                "workflow_runs": "workflow runs",
                "agent_status": "agent status",
                "analytics": "analytics",
            }.get(name, name)
            for name in timed_out
        ],
    )
    return {
        "message": message,
        "tool_results": list(collected),
        "offered_action": offered.as_dict(),
        "terminal_state": terminal,
        "elapsed_ms": elapsed_ms,
        "progress_steps": [
            f"Completed: Checking {scope}" if scope != offered.scope[-1] or terminal == "COMPLETED" else f"Running: Checking {scope}"
            for scope in offered.scope
        ],
    }


def live_payload_for_execution(
    executed: dict[str, Any],
    task_state: dict[str, Any] | None,
) -> dict[str, Any]:
    state = dict(task_state or {})
    offered = executed.get("offered_action")
    state["offered_action"] = offered
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": executed.get("message") or "",
        "task_state": state,
        "pending_task": None,
        "answer_explanation": "Offered READ continuation",
        "model": "offered_action_continuation",
        "unified_outcome_kind": "connector_tool_proposal"
        if executed.get("tool_results")
        else "conversational_reply",
        "tool_results": executed.get("tool_results") or [],
        "offered_action_executed": True,
        "turn_terminal_state": executed.get("terminal_state") or "COMPLETED",
        "progress_steps": executed.get("progress_steps") or [
            "Completed: Checking systems",
        ],
    }


def patch_task_state_offered(
    task_state: dict[str, Any] | None,
    offered: OfferedAction | None,
) -> dict[str, Any]:
    state = dict(task_state or {})
    state["offered_action"] = offered.as_dict() if offered else None
    return state


async def persist_offered_action(
    *,
    conversation_id: str | None,
    org_id: str,
    offered: dict[str, Any] | None,
    client: Any = None,
    settings: Any = None,
) -> None:
    if not conversation_id or not org_id:
        return
    try:
        from app.services.conversation_state_service import get_conversation_state_service

        await get_conversation_state_service(settings).update_task_state(
            conversation_id,
            org_id,
            {"offered_action": offered},
            client=client,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("persist_offered_action failed conversation_id=%s error=%s", conversation_id, exc)
