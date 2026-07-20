"""Gravitree Voice Layer (Module D).

Single source of truth for product persona — calm expert, facts-first,
Connected/Healthy/Executable/Verified vocabulary. Chat, ReAct, canvas turn
copy, errors, notifications, and Meson MUST call into this module rather than
pasting per-surface VOICE prose.

Pattern mirrors catalog_write_authority: one module, every surface calls in.
Module B (conversation_turn_controller) is the planner ownership point for
connector-turn user-facing strings; Meson calls this module directly until it
enters B.

Behavioral range (not tone alone):
- Confidence register: certain | estimate | blocked
- Humor budget: rare, never on errors/governance; opt-in via allow_humor
- House phrasing: curated Gravitree-specific lines for recurring moments

Executive Digest: format_outcome_digest() shapes Module A outcome batches
(intelligence_outcome_events / outcome_event_bus payloads) in this voice.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

VOICE_SECTION_HEADER = "## Voice"

ConfidenceRegister = Literal["certain", "estimate", "blocked"]

# Canonical readiness / verification vocabulary (CHEV + Verified).
CHEV_TERMS: dict[str, str] = {
    "connected": "Connected",
    "healthy": "Healthy",
    "executable": "Executable",
    "verified": "Verified",
    "configured": "Configured",
    "authenticated": "Authenticated",
}

# Curated house style — recognizably Gravitree, not generic LLM hedges.
HOUSE_PHRASING: dict[str, str] = {
    "insufficient_info": (
        "I don't have enough information yet. Tell me the missing detail and I'll continue."
    ),
    "assumption_flag": (
        "Assumption — based on what's Connected so far; say if that is wrong."
    ),
    "success_win": "Done. Verified output is ready.",
    "success_win_light": "Done — clean run.",
    "blocked_generic": "Blocked. {blocker} Next: {next_action}",
    "estimate_prefix": "Estimate — based on what's Connected so far:",
    "connector_connect_to_run": (
        "Connect {integration} at /connectors to run this action."
    ),
    "skipped_unsupported": "Skipped — no Executable action matched this step.",
    "no_executable_action": "No Executable action matched this request.",
    "skipped_connector": "Skipped — {integration} is not Connected.",
    "canvas_write_blocked": (
        "Write blocked: this canvas step needs an approved run "
        "(required_approvals>=1). In-graph approval alone is not enough."
    ),
}

GRAVITREE_VOICE_RULES: tuple[str, ...] = (
    "Calm expert: capable operator, not a chatbot persona. Smart, cool geek — precise, not cute.",
    "Lead with the fact, then the implication, then the one best next move.",
    "Show your work when a fact comes from a tool or connector result — cite the source briefly in plain language.",
    "State uncertainty plainly when you do not know; never invent connector states, metrics, or agent names.",
    "Never hedge with \"I think\" when you have a real answer from tools or state.",
    "Never over-apologize; refuse safety and governance limits plainly.",
    "Use Connected / Healthy / Executable / Verified (and Configured / Authenticated when describing readiness) — not vague \"working\" or \"smart\".",
    "Avoid buzzwords entirely (synergy, leverage, unlock, seamless, delightful, magical).",
    "Humor is light and rare; never cute; never during errors, approvals, or governance moments.",
    "Complete sentences in chat; short bullets only for 3+ items. No report headers like \"Workflow health:\".",
)

_CONFIDENCE_REGISTER_RULES = (
    "Confidence register (match phrasing to certainty):\n"
    "- certain: short, declarative; no fake hedges.\n"
    "- estimate: label it (\"Estimate — based on what's Connected so far\") and allow "
    "\"likely\" / \"based on what's Connected so far\" — never present as Verified.\n"
    "- blocked: name the blocker, state the next action, no apology loop."
)

_HUMOR_BUDGET_RULES = (
    "Humor budget: rare and contextual only. Never joke on errors, write approvals, "
    "governance refusals, or blocked states. Allowed only on low-stakes clean success "
    "or idle moments when the surface explicitly permits flourish."
)

_HOUSE_PHRASE_RULES = (
    "House phrasing (prefer these exact shapes when they fit):\n"
    f"- Insufficient info: \"{HOUSE_PHRASING['insufficient_info']}\"\n"
    f"- Flagging an assumption: \"{HOUSE_PHRASING['assumption_flag']}\"\n"
    f"- Reporting a win: \"{HOUSE_PHRASING['success_win']}\""
)

_VOICE_SECTION_BODY = (
    "You are Gravitre — a calm expert operator for enterprise automation.\n"
    "Speak the same way on every surface (chat, ReAct, canvas, Meson, errors, notifications).\n"
    "- Lead with the fact. Show your work when citing tools. State uncertainty plainly.\n"
    "- Never hedge with \"I think\" when you have a real answer. Never over-apologize.\n"
    "- Use Connected / Healthy / Executable / Verified for readiness and outcomes.\n"
    "- No buzzwords. Humor light and rare; never cute.\n"
    "- Refuse safety or governance limits plainly. Never invent names, states, or metrics."
)

_TOOL_ERROR_TEMPLATES: dict[str, str] = {
    "auth_expired": (
        "{integration} authentication expired. "
        "Reconnect it at /connectors, then try again."
    ),
    "permission_denied": (
        "You do not have permission to run this action"
        "{action_suffix}. Ask an admin to grant access, or pick a different tool."
    ),
    "connector_not_connected": (
        "{integration} is not Connected for this organization. "
        "Connect it at /connectors, then try again."
    ),
    "channel_not_found": (
        "That Slack channel was not found (or the bot is not a member). "
        "Use a public channel name/id the bot can access, invite the bot, then try again."
    ),
    "missing_scope": (
        "{integration} is Connected but missing required permissions"
        "{action_suffix}. Reconnect it at /connectors and approve the requested scopes."
    ),
    "validation_error": (
        "Invalid parameters for this {integration} action{action_suffix}. "
        "Check required fields and try again."
    ),
    "rate_limited": (
        "{integration} rate-limited the request. Wait a moment and try again."
    ),
    "connector_timeout": (
        "{integration} did not respond in time. Try again shortly."
    ),
    "write_approval_required": ("This write needs your approval before it runs."),
    "tool_not_available": (
        "That tool is not Connected or permitted for this agent. "
        "Connect it at /connectors or switch mode."
    ),
    "action_not_found": ("This action is not implemented yet for {integration}."),
    "tool_error": (
        "{integration} returned an error{action_suffix}. "
        "Check connector health at /connectors — it may not be Healthy."
    ),
    "unverifiable_output": (
        "The connector action completed but returned no Verified output "
        "(missing body and result link)."
    ),
    "canvas_write_authority_blocked": HOUSE_PHRASING["canvas_write_blocked"],
}

# Kinds that never allow humor (governance / error / blocked).
_HUMOR_FORBIDDEN_KINDS = frozenset(
    {
        "tool_error",
        "write_approval",
        "canvas_write_blocked",
        "connector_connect_to_run",
        "pending_plan_cancelled",
        "approval_needed_requester",
        "approval_needed_requester_title",
        "notification_run_title",
        "notification_run_body",
        "audit_failure_summary",
        "failure_alert_title",
        "failure_alert_body",
        "insufficient_info",
        "assumption_flag",
        "blocked",
        "skipped_unsupported",
        "no_executable_action",
        "skipped_connector",
    }
)


@dataclass(frozen=True)
class OutcomeDigestItem:
    """One terminal outcome for an Executive Digest batch.

    Map from finalize_execution_outcome / intelligence_outcome_events /
    outcome_event_bus payloads — do not invent fields.
    """

    status: str
    summary: str
    source: str | None = None
    verified: bool = False
    run_id: str | None = None
    measured_at: str | None = None


def coerce_outcome_digest_item(raw: OutcomeDigestItem | dict[str, Any]) -> OutcomeDigestItem:
    """Normalize a stream/DB row or dict into OutcomeDigestItem."""
    if isinstance(raw, OutcomeDigestItem):
        return raw
    if not isinstance(raw, dict):
        raise TypeError(f"OutcomeDigestItem requires dict or dataclass, got {type(raw)!r}")
    meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    status = str(
        raw.get("status")
        or raw.get("terminal_status")
        or meta.get("terminal_status")
        or raw.get("outcome_event")
        or ""
    ).strip().lower()
    if status in {"workflow_failed", "run_failed"}:
        status = "failed"
    elif status in {"workflow_cancelled", "run_cancelled"}:
        status = "cancelled"
    elif status in {"workflow_executed", "workflow_completed", "run_completed"}:
        status = "completed"
    elif status == "partial_success":
        status = "partial_success"
    summary = str(
        raw.get("summary")
        or raw.get("error_summary")
        or meta.get("error")
        or meta.get("verified_summary")
        or raw.get("outcome_event")
        or status
        or "outcome"
    ).strip()
    source = raw.get("source") or meta.get("source")
    verified_output = raw.get("verified_output")
    if isinstance(verified_output, dict) and verified_output.get("summary") and not raw.get("summary"):
        summary = str(verified_output.get("summary") or summary)
    verified = bool(
        raw.get("verified")
        or (isinstance(verified_output, dict) and verified_output.get("summary"))
        or meta.get("verified_summary")
    )
    run_id = raw.get("run_id") or raw.get("workflow_run_id") or meta.get("run_id")
    measured_at = raw.get("measured_at") or raw.get("timestamp") or raw.get("created_at")
    return OutcomeDigestItem(
        status=status or "unknown",
        summary=summary[:400],
        source=str(source).strip() if source else None,
        verified=verified,
        run_id=str(run_id).strip() if run_id else None,
        measured_at=str(measured_at).strip() if measured_at else None,
    )


def chev_term(status: str | None) -> str:
    """Return canonical CHEV / Verified label for a readiness or outcome status."""
    key = str(status or "").strip().lower()
    if key in CHEV_TERMS:
        return CHEV_TERMS[key]
    return str(status or "").strip()


def house_phrase(key: str, **ctx: Any) -> str:
    """Return a curated house-style line; raises KeyError for unknown keys."""
    template = HOUSE_PHRASING[key]
    if "{" in template:
        return template.format(**{k: (v if v is not None else "") for k, v in ctx.items()})
    return template


def confidence_register_hint(register: ConfidenceRegister | str | None) -> str:
    """Short phrasing constraint for the named confidence register."""
    key = str(register or "certain").strip().lower()
    if key == "estimate":
        return (
            "Register=estimate: lead with "
            f"\"{HOUSE_PHRASING['estimate_prefix']}\" "
            "and use likely/based-on-Connected hedges. Do not claim Verified."
        )
    if key == "blocked":
        return (
            "Register=blocked: name the blocker, state the one next action, "
            "no apology loop, no humor."
        )
    return "Register=certain: short declarative facts; no fake hedges."


def humor_permitted(*, kind: str | None = None, allow_humor: bool = False) -> bool:
    """Humor budget gate — false for errors, approvals, and governance kinds."""
    key = str(kind or "").strip().lower()
    if key in _HUMOR_FORBIDDEN_KINDS:
        return False
    return bool(allow_humor)


def voice_system_prompt_section() -> str:
    """The one VOICE block for LLM system prompts (includes behavioral range)."""
    rules = "\n".join(f"- {rule}" for rule in GRAVITREE_VOICE_RULES)
    return (
        f"{VOICE_SECTION_HEADER}\n{_VOICE_SECTION_BODY}\n\n"
        f"Rules:\n{rules}\n\n"
        f"{_CONFIDENCE_REGISTER_RULES}\n\n"
        f"{_HUMOR_BUDGET_RULES}\n\n"
        f"{_HOUSE_PHRASE_RULES}"
    )


def apply_voice(system_prompt: str | None) -> str:
    """Idempotently ensure the canonical Voice section is present exactly once."""
    section = voice_system_prompt_section().strip()
    text = (system_prompt or "").strip()
    if not text:
        return section

    cleaned_lines: list[str] = []
    skipping_voice = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("VOICE:"):
            skipping_voice = True
            continue
        if skipping_voice:
            if stripped.startswith("OUTPUT:") or stripped.startswith("ROLE:") or stripped.startswith("SECURITY"):
                skipping_voice = False
                cleaned_lines.append(line)
            continue
        if stripped == VOICE_SECTION_HEADER or stripped.startswith(f"{VOICE_SECTION_HEADER} "):
            skipping_voice = True
            continue
        if skipping_voice:
            if stripped.startswith("## ") and stripped != VOICE_SECTION_HEADER:
                skipping_voice = False
                cleaned_lines.append(line)
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()
    if not cleaned:
        return section
    return f"{cleaned}\n\n{section}"


def domain_focus_section(modifier: str | None) -> str:
    """Wrap a department persona overlay — domain focus only, never replaces Voice."""
    text = (modifier or "").strip()
    if not text:
        return ""
    return f"## Domain focus\n{text}"


def _integration_label(integration: str | None) -> str:
    value = str(integration or "").strip().replace("_", " ")
    if not value:
        return "the connector"
    return value.title()


def _action_suffix(action: str | None) -> str:
    value = str(action or "").strip()
    if not value:
        return ""
    return f" ({value})"


def _apply_register(text: str, register: ConfidenceRegister | str | None) -> str:
    key = str(register or "certain").strip().lower()
    body = (text or "").strip()
    if not body:
        return body
    if key == "estimate" and not body.lower().startswith("estimate"):
        return f"{HOUSE_PHRASING['estimate_prefix']} {body}"
    return body


def format_confidence_for_voice(
    value: float | None,
    *,
    source: str | None = None,
    is_estimate: bool = True,
) -> str:
    """Module C honesty through Module D — never emit an unlabeled confidence number."""
    from app.services.confidence_honesty import (
        CONFIDENCE_SOURCE_HEURISTIC,
        label_confidence,
    )

    labeled = label_confidence(
        value,
        source=source or CONFIDENCE_SOURCE_HEURISTIC,
        is_estimate=is_estimate,
    )
    conf = labeled.get("confidence")
    if conf is None:
        return format_operator_message("insufficient_info")
    detail = f"{float(conf):.0%} confidence"
    if labeled.get("confidence_is_estimate", True) or is_estimate:
        return format_operator_message("estimate", detail=detail)
    return detail


def format_operator_message(
    kind: str,
    *,
    confidence_register: ConfidenceRegister | str | None = None,
    allow_humor: bool = False,
    **ctx: Any,
) -> str:
    """Shared shaper for approval / error / notification / turn / canvas user strings.

    ``allow_humor`` is ignored (forced off) for governance/error/blocked kinds.
    ``confidence_register`` shapes estimate/blocked phrasing where applicable.
    Numeric ``confidence`` in ``ctx`` is always routed through Module C labeling.
    """
    key = str(kind or "").strip().lower()
    # Module C gate: a bare float in voice context must be labeled before emission.
    if "confidence" in ctx and isinstance(ctx.get("confidence"), (int, float)):
        return format_confidence_for_voice(
            float(ctx["confidence"]),
            source=str(ctx.get("confidence_source") or "") or None,
            is_estimate=bool(ctx.get("confidence_is_estimate", True)),
        )
    register = str(confidence_register or "").strip().lower() or None
    if register not in {None, "certain", "estimate", "blocked"}:
        register = "certain"
    # Default register by kind when caller omits it.
    if register is None:
        if key in {
            "tool_error",
            "canvas_write_blocked",
            "connector_connect_to_run",
            "blocked",
            "skipped_connector",
            "write_approval",
        }:
            register = "blocked"
        elif key in {"assumption_flag", "estimate"}:
            register = "estimate"
        else:
            register = "certain"

    flourish_ok = humor_permitted(kind=key, allow_humor=allow_humor)

    if key == "pending_plan_cancelled":
        return "Cancelled the pending plan. What should we do instead?"

    if key == "house" or key == "house_phrase":
        phrase_key = str(ctx.get("phrase") or ctx.get("key") or "").strip()
        return house_phrase(phrase_key, **{k: v for k, v in ctx.items() if k not in {"phrase", "key"}})

    if key == "insufficient_info":
        return HOUSE_PHRASING["insufficient_info"]

    if key == "assumption_flag":
        detail = str(ctx.get("detail") or "").strip()
        base = HOUSE_PHRASING["assumption_flag"]
        return f"{base} {detail}".strip() if detail else base

    if key == "success_win":
        if flourish_ok:
            return HOUSE_PHRASING["success_win_light"]
        return HOUSE_PHRASING["success_win"]

    if key == "connector_connect_to_run":
        return house_phrase(
            "connector_connect_to_run",
            integration=_integration_label(ctx.get("integration")),
        )

    if key == "skipped_connector":
        return house_phrase(
            "skipped_connector",
            integration=_integration_label(ctx.get("integration")),
        )

    if key == "skipped_unsupported":
        return HOUSE_PHRASING["skipped_unsupported"]

    if key == "no_executable_action":
        return HOUSE_PHRASING["no_executable_action"]

    if key == "canvas_write_blocked":
        return HOUSE_PHRASING["canvas_write_blocked"]

    if key == "blocked":
        blocker = str(ctx.get("blocker") or "This action cannot run.").strip()
        next_action = str(ctx.get("next_action") or "Fix the blocker, then retry.").strip()
        return house_phrase("blocked_generic", blocker=blocker, next_action=next_action)

    if key == "tool_error":
        code = str(ctx.get("error_code") or "").strip().lower()
        template = _TOOL_ERROR_TEMPLATES.get(code)
        if template:
            return template.format(
                integration=_integration_label(ctx.get("integration")),
                action_suffix=_action_suffix(ctx.get("action")),
            ).strip()
        detail = str(ctx.get("error_message") or "").strip()
        if detail:
            if len(detail) > 400:
                detail = detail[:397] + "..."
            label = _integration_label(ctx.get("integration"))
            if label != "the connector":
                return f"{label} action failed: {detail}"
            return detail
        return "The connector action failed."

    if key == "write_approval":
        # Governance — humor always off regardless of allow_humor.
        return _format_write_approval(**ctx)

    if key == "notification_run_title":
        status = str(ctx.get("status") or "").strip().lower()
        source = str(ctx.get("source") or "").strip().lower()
        if source == "chat_orch":
            if status == "failed":
                return "Orchestration run failed"
            if status == "cancelled":
                return "Orchestration run cancelled"
            return "Orchestration run completed"
        if status == "failed":
            return "Workflow run failed"
        if status == "cancelled":
            return "Workflow run cancelled"
        if status == "partial_success":
            return "Workflow run finished with partial success"
        return "Workflow run completed"

    if key == "notification_run_body":
        status = str(ctx.get("status") or "").strip().lower()
        explicit = str(ctx.get("body") or "").strip()
        if explicit:
            # Failures: reshape through blocked register unless already voiced.
            if status == "failed":
                lowered = explicit.lower()
                if lowered.startswith(("blocked", "write blocked", "connect ")):
                    return explicit[:2000]
                return house_phrase(
                    "blocked_generic",
                    blocker=explicit[:400],
                    next_action="Open the failed run, fix the blocker, then retry.",
                )[:2000]
            return explicit[:2000]
        error_summary = str(ctx.get("error_summary") or "").strip()
        if status == "failed":
            detail = error_summary or "Review the run details for step-level errors."
            lowered = detail.lower()
            if lowered.startswith(("blocked", "write blocked", "connect ")):
                return detail[:2000]
            return house_phrase(
                "blocked_generic",
                blocker=detail[:400],
                next_action="Open the failed run, fix the blocker, then retry.",
            )[:2000]
        if status == "cancelled":
            return (error_summary or "Run was cancelled.")[:2000]
        verified_summary = str(ctx.get("verified_summary") or "").strip()
        if verified_summary:
            return verified_summary[:2000]
        return f"Run finished with status {status or 'completed'}."

    if key == "audit_failure_summary":
        err = str(ctx.get("error_summary") or "execution failed").strip()
        lowered = err.lower()
        if lowered.startswith(("blocked", "write blocked", "failed —", "failed -")):
            return err[:500]
        return f"Failed — {err}"[:500]

    if key == "failure_alert_title":
        label = str(ctx.get("label") or "workflow").strip() or "workflow"
        if ctx.get("repeated"):
            return f"Repeated {label} failures across workflows"[:200]
        return f"Observed {label} run failure"[:200]

    if key == "failure_alert_body":
        blocker = str(ctx.get("blocker") or ctx.get("error_summary") or "run failed").strip()
        count = ctx.get("failure_count")
        prefix = f"{count} related failures. " if isinstance(count, int) and count > 1 else ""
        return house_phrase(
            "blocked_generic",
            blocker=f"{prefix}{blocker}"[:400],
            next_action="Open the failed run, fix the blocker, then retry.",
        )[:1000]

    if key == "approval_needed_requester":
        label = str(ctx.get("label") or "This write").strip()
        return f"{label} is waiting in the Decision Queue."

    if key == "approval_needed_requester_title":
        return "Request sent for approval"

    if key == "estimate":
        detail = str(ctx.get("detail") or ctx.get("message") or "").strip()
        return _apply_register(detail or "signal is incomplete.", "estimate")

    raise ValueError(f"Unknown operator message kind: {kind}")


def format_outcome_digest(
    items: Sequence[OutcomeDigestItem | dict[str, Any]],
    *,
    title: str = "Executive Digest",
    period_label: str | None = None,
    allow_humor: bool = False,
) -> str:
    """Turn a batch of Module A outcomes into one human-readable digest.

    Fact-first Gravitree voice. Failures use the blocked register (blocker + next
    action). Clean windows may use the light success flourish when ``allow_humor``.
    """
    normalized = [coerce_outcome_digest_item(item) for item in (items or [])]
    header = [str(title or "Executive Digest").strip() or "Executive Digest"]
    if period_label:
        header.append(str(period_label).strip())

    if not normalized:
        return "\n".join(header + ["", "No terminal outcomes in this window."])

    completed = [i for i in normalized if i.status in {"completed", "partial_success"}]
    failed = [i for i in normalized if i.status == "failed"]
    cancelled = [i for i in normalized if i.status == "cancelled"]
    other = [
        i
        for i in normalized
        if i.status not in {"completed", "partial_success", "failed", "cancelled"}
    ]

    lines = list(header)
    lines.append("")
    lines.append(
        f"{len(completed)} completed · {len(failed)} failed · {len(cancelled)} cancelled"
        + (f" · {len(other)} other" if other else "")
        + "."
    )

    if failed:
        lines.append("")
        lines.append("Failures (blocked — fix these next):")
        for item in failed[:8]:
            src = f" [{item.source}]" if item.source else ""
            run = f" · run {item.run_id[:8]}" if item.run_id else ""
            lines.append(f"- {item.summary}{src}{run}")
        lines.append("Next: open the failed run, fix the blocker, then retry.")

    if completed:
        lines.append("")
        lines.append("Completed:")
        for item in completed[:6]:
            label = "Verified" if item.verified else "Done"
            src = f" [{item.source}]" if item.source else ""
            lines.append(f"- {label}: {item.summary}{src}")

    if cancelled and not failed:
        lines.append("")
        lines.append(f"{len(cancelled)} run(s) cancelled — no retry needed unless you re-queue them.")

    if failed == [] and completed and humor_permitted(kind="success_win", allow_humor=allow_humor):
        lines.append("")
        lines.append(HOUSE_PHRASING["success_win_light"])
    elif failed == [] and completed:
        lines.append("")
        lines.append(HOUSE_PHRASING["success_win"])

    return "\n".join(lines).strip() + "\n"


def _format_write_approval(**ctx: Any) -> str:
    vendor = str(ctx.get("vendor") or "the connected app").strip()
    label = str(ctx.get("label") or "this action").strip()
    details = ctx.get("details") if isinstance(ctx.get("details"), dict) else {}
    list_name = str(ctx.get("list_name") or "").strip()
    invoke_action = str(ctx.get("invoke_action") or "").strip()
    is_list_create = bool(list_name) and "lists.create" in invoke_action

    if is_list_create:
        intro = f"I can create a contact list named **{list_name}** in {vendor}."
        if "segment" in label.lower():
            intro = (
                f"Apollo does not expose CRM segments over API the same way, "
                f"but I can create an equivalent contact list named **{list_name}**."
            )
        lines = [intro]
        for key, value in details.items():
            if str(key).lower() == "name":
                continue
            lines.append(f"- {key}: {value}")
        lines.extend(
            [
                "",
                "Reply **yes** to approve and create it, or say what to change "
                "(name, modality, or follow-up criteria to populate it).",
            ]
        )
        return "\n".join(lines)

    lines = [f"I'll run this in {vendor}: **{label}**."]
    if details:
        lines.append("")
        for key, value in details.items():
            lines.append(f"- {key}: {value}")
    lines.extend(["", "Reply **yes** to approve, or say what to change."])
    return "\n".join(lines)


def tool_error_template(error_code: str) -> str | None:
    """Expose voice-owned tool error templates for the error formatter adapter."""
    return _TOOL_ERROR_TEMPLATES.get(str(error_code or "").strip().lower())
