"""Mandatory Response Composer — sole writer of user-facing chat/TTS text.

Symmetric with the Intent Gateway: every INPUT reaches real reasoning; every
OUTPUT reaches the model's own voice before the UI. Raw backend text, stack
traces, error codes, and internal identifiers must not reach the bubble.

Streaming LIVE tokens that are already model-generated pass through adopt/
leak-filter only (re-composing every token would add a second LLM call on the
voice path). Canned, shortcut, error, timeout, permission, validation, and
clarify outcomes are always model-composed from the typed envelope.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

from app.core.logging import get_logger
from app.operators.assistant_sse import (
    sse_error,
    sse_text_delta,
    sse_text_end,
    sse_text_start,
)
from app.operators.stream_events import AssistantStreamEvent
from app.services.conversational_behavior import CONVERSATIONAL_BEHAVIOR_SECTION
from app.services.first_token_honesty import (
    envelope_allows_completion_claim,
    reject_premature_done,
)
from app.services.module_d_unified_voice_spec import MODULE_D_UNIFIED_SYSTEM_SPEC
from app.services.response_envelope import coerce_user_envelope, envelope_kind
from app.services.user_facing_copy_guard import (
    collapse_spaces_keep_lines,
    finalize_user_facing_message,
)
from app.workflows.audit import submit_audit_off_loop, write_audit_event

logger = get_logger(__name__)

AUDIT_ACTION_COMPOSER_COMPLETED = "response.composer.completed"

MUST_COMPOSE_KINDS = frozenset(
    {
        "error",
        "timeout",
        "permission",
        "validation",
        "clarify",
        "canned",
        "shortcut",
        "correction",
        "request_failed",
        "stopped",
    }
)

# Last-resort blocked-register copy if the compose LLM itself fails.
# Never include the underlying error_detail. Internally labeled composer_fallback.
_FALLBACK_BY_KIND: dict[str, str] = {
    "permission": "You don't have access to do that yet. If that permission changes, I can pick it back up.",
    "timeout": "That took too long and didn't finish. You can try it again.",
    "validation": "I'm missing one detail before I can do that.",
    "clarify": "I need one detail before I can continue — what's the target?",
    "error": "That didn't go through, and I didn't complete the action.",
    "request_failed": "I couldn't finish that just now. Try it again in a moment.",
    "shortcut": "Here's the short version.",
    "correction": "Got it — I'll use that from here.",
    "canned": "I have that.",
    "progress": "I'm working on it now.",
    "workflow_waiting": "This is waiting for your input before it can continue.",
    "success": "Done.",
    "stopped": "You stopped me before I finished that. I didn't complete anything from that turn, so we can pick it back up from where we left off.",
}

_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Traceback \(most recent call last\)", re.I),
    re.compile(r"sqlalchemy\.", re.I),
    re.compile(r"psycopg(?:2)?|asyncpg", re.I),
    re.compile(r"SQLSTATE", re.I),
    re.compile(r"statement timeout", re.I),
    re.compile(r"CognitiveTurnKernel"),
    re.compile(r"intent_gateway:"),
    re.compile(r"kernel\.\.\.info", re.I),
    re.compile(r"\b(?:File|file) \"[^\"]+\.py\", line \d+", re.I),
    re.compile(r"backend[/\\]app"),
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]+Error:"),
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]+Exception:"),
    re.compile(r"\b0x[0-9a-fA-F]{8,}\b"),
    re.compile(r"\bassistant_[a-z0-9_]+\b", re.I),
    re.compile(r"\bgetConnectorStatus\b"),
    re.compile(r"\btool_call\b", re.I),
    re.compile(r"\bfunction\s+schema\b", re.I),
    re.compile(r"\bcapability__[a-z0-9_]+\b", re.I),
)

_LIFECYCLE_LEAK = re.compile(
    r"\b(?:PREPARED|AWAITING_APPROVAL|APPROVED|EXECUTING|EXECUTED_UNVERIFIED|"
    r"VERIFIED|COMPLETED|REJECTED|CANCELLED|FAILED|OUTCOME_UNCERTAIN|"
    r"AWAITING_RECONCILIATION)\b"
)
_REFUSAL_CLAIM = re.compile(
    r"\b(?:not permitted|isn't permitted|isn['’]t permitted|won't create|"
    r"won['’]t create|cannot create|can['’]t create|will not (?:create|run|execute))\b",
    re.I,
)
# Lifecycle alignment (failed / rejected / awaiting approval): only unmistakable
# claims, so ordinary prose such as "completed deals" is never rewritten.
_SUCCESS_CLAIM = re.compile(r"\b(?:is confirmed|I created|successfully created|all set|it's done)\b", re.I)

# Completion paraphrases, checked only on turns that carry a consequential action.
_COMPLETION_CLAIM = re.compile(
    r"\b(?:done|completed|complete|finished|is confirmed|I(?:'ve| have)? (?:created|updated|sent|posted|added)|"
    r"successfully (?:created|updated|sent|posted|completed|added)|all set|it's done|"
    r"it is done|went through|has been (?:created|updated|sent|completed|added|posted))\b",
    re.I,
)
# A claim word governed by one of these is not a completion claim
# ("not done yet", "once it's complete", "will be finished").
_CLAIM_NEGATION = re.compile(
    r"(?:\bnot\b|n't\b|\bnever\b|\bonce\b|\bwhen\b|\buntil\b|\bafter\b|\bbefore\b|\bwill\b|"
    r"\bif\b|\bwhether\b|\byet to\b|\bto be\b|\bnot yet\b)[^.!?]{0,24}$",
    re.I,
)
_ACTION_PENDING_TYPES = frozenset(
    {
        "connector_action",
        "connector_orchestration",
        "create_agent",
        "create_workflow",
        "execute_workflow",
        "run_agent_task",
    }
)


def has_completion_claim(text: str | None) -> bool:
    """True when text asserts that something finished (negation/future aware)."""
    body = text or ""
    for match in _COMPLETION_CLAIM.finditer(body):
        lead = body[max(0, match.start() - 40) : match.start()]
        if _CLAIM_NEGATION.search(lead):
            continue
        return True
    return False


def envelope_has_consequential_action(envelope: dict[str, Any] | None) -> bool:
    """Only turns that executed (or staged) a write can make a false completion claim."""
    env = envelope if isinstance(envelope, dict) else {}
    data = env.get("data") if isinstance(env.get("data"), dict) else {}
    if env.get("canonical_lifecycle") or data.get("canonical_lifecycle"):
        return True
    from app.services.outcome_verification import is_write_action

    for container in (env, data):
        if "execution_verified" in container:
            return True
        action = container.get("invoke_action") or container.get("action")
        if isinstance(action, str) and "." in action and is_write_action(action):
            return True
        pending = container.get("pending_task")
        if isinstance(pending, dict) and str(pending.get("type") or "") in _ACTION_PENDING_TYPES:
            return True
    return False

_CODE_AS_MESSAGE = re.compile(r"^[a-z][a-z0-9_]{2,}$")

# Bare orchestration/lifecycle words are implementation state, not useful dialogue.
# Force them through the Response Composer instead of surfacing strings such as
# "Stopped.", "Failed.", or "Pending." directly in the conversation.
_SYSTEM_STATE_ONLY = re.compile(
    r"^\s*(?:stopped|failed|pending|blocked|cancelled|canceled|not started|"
    r"did not complete|complete|completed)\.?\s*$",
    re.IGNORECASE,
)


def looks_like_system_state_only(text: str | None) -> bool:
    return bool(_SYSTEM_STATE_ONLY.match((text or "").strip()))



def align_composed_text_to_lifecycle(
    text: str,
    envelope: dict[str, Any] | None,
    *,
    draft: str | None = None,
) -> str:
    """Keep Composer prose unless it contradicts canonical execution state."""
    env = envelope if isinstance(envelope, dict) else {}
    data = env.get("data") if isinstance(env.get("data"), dict) else {}
    stage = str(env.get("canonical_lifecycle") or data.get("canonical_lifecycle") or "").strip()
    verified = bool(env.get("execution_verified") is True or data.get("execution_verified") is True)
    success = env.get("success") is not False
    cleaned = _LIFECYCLE_LEAK.sub("", text or "")
    cleaned = collapse_spaces_keep_lines(cleaned)
    fallback = (draft or "").strip()
    if fallback and looks_like_raw_backend(fallback):
        fallback = ""
    if verified and success and _REFUSAL_CLAIM.search(cleaned):
        if fallback and not _REFUSAL_CLAIM.search(fallback):
            return fallback
    # A lifecycle stage means this turn is about an action, so paraphrased
    # completion claims are checked too; without one only unmistakable claims are.
    claims_done = has_completion_claim(cleaned) if stage else bool(_SUCCESS_CLAIM.search(cleaned))
    if stage in {"FAILED", "REJECTED", "CANCELLED"} or success is False:
        if claims_done and fallback:
            return fallback
    if stage in {"AWAITING_APPROVAL", "EXECUTED_UNVERIFIED", "VERIFYING"} and claims_done and fallback:
        return fallback
    if stage == "OUTCOME_UNCERTAIN" and (claims_done or _REFUSAL_CLAIM.search(cleaned)):
        if fallback:
            return fallback
    return cleaned or (text or "")

_INTERNAL_IDS = re.compile(
    r"\b(?:org_id|user_id|connector_id|run_id|task_id|conversation_id)\b",
    re.I,
)

ComposeFn = Callable[..., Awaitable[str]]

TTS_SAFE_ERROR = _FALLBACK_BY_KIND["request_failed"]

CHIP_STATUS: dict[str, str] = {
    "permission_denied": "You don't have permission for this step.",
    "missing_scope": "This step needs a bit more access.",
    "auth_expired": "You'll need to sign in to this tool again.",
    "connector_timeout": "This step took too long.",
    "timeout": "This step took too long.",
    "statement_timeout": "This step took too long.",
    "validation_error": "This step is missing something it needs.",
    "connector_not_connected": "That tool isn't connected yet.",
    "channel_not_found": "I couldn't find where to send that.",
    "rate_limited": "Too many requests at once. Try again in a moment.",
    "tool_not_available": "That tool isn't connected yet.",
    "tool_error": "This step didn't finish.",
}


def align_draft_to_compiled_timeframe(text: str, envelope: dict[str, Any] | None) -> str:
    """Composer owns presentation of compiled time; never keep last-30-days when the task window is not that."""
    env = envelope if isinstance(envelope, dict) else {}
    payload = env.get("analytics_result")
    if not isinstance(payload, dict) and isinstance(env.get("data"), dict):
        payload = env["data"].get("analytics_result")
    if not isinstance(payload, dict):
        return text
    label = str(payload.get("timeframe") or "").strip()
    if not label or not text:
        return text
    if "30" in label.replace(" ", "").lower():
        return text
    return re.sub(r"(?i)\b(?:the\s+)?last\s+30\s+days\b", label, text)


def looks_like_raw_backend(text: str | None) -> bool:
    """True when text looks like a stack, SQL, exception, or internal identifier."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _CODE_AS_MESSAGE.fullmatch(raw) and raw.lower() in {
        "permission_denied",
        "tool_error",
        "validation_error",
        "connector_timeout",
        "statement_timeout",
        "auth_expired",
        "missing_scope",
        "connector_not_connected",
        "channel_not_found",
        "action_not_found",
        "rate_limited",
        "org_write_isolation",
    }:
        return True
    for pattern in _LEAK_PATTERNS:
        if pattern.search(raw):
            return True
    if _INTERNAL_IDS.search(raw) and ("=" in raw or ":" in raw):
        return True
    from app.services.first_token_honesty import looks_like_tool_payload

    return looks_like_tool_payload(raw)


def safe_voice_text(text: str | None) -> str:
    """Last gate before spoken output: substitute anything that reads as backend.

    The AST guard checks the *shape* of an emission site -- it rejects text built
    inline -- but a local variable holding raw text still satisfies that shape.
    Rather than reach for dataflow analysis to prove where a string came from,
    check what it actually says at the moment it leaves. Content is the thing
    that matters to the listener, and it is cheap to inspect.

    Deliberately fails closed: unrecognised or empty text becomes the safe line,
    because on the voice path the alternative to a wrong sentence is silence,
    and silence during a failure reads as the product hanging.
    """
    candidate = (text or "").strip()
    if not candidate or looks_like_raw_backend(candidate):
        return TTS_SAFE_ERROR
    return candidate


def adopt_model_delta(delta: str) -> str:
    """Pass already-generated model tokens through after dropping leaky chunks."""
    piece = delta or ""
    if not piece:
        return ""
    if looks_like_raw_backend(piece):
        logger.warning("response_composer_dropped_leaky_delta chars=%s", len(piece))
        return ""
    try:
        from app.services.user_facing_copy_guard import scrub_raw_catalog_keys

        return scrub_raw_catalog_keys(piece)
    except Exception:  # noqa: BLE001
        return piece


def emit_text_start(text_id: str | None = None) -> tuple[str, AssistantStreamEvent]:
    return sse_text_start(text_id)


def emit_text_delta(text_id: str, delta: str) -> AssistantStreamEvent:
    cleaned = adopt_model_delta(delta)
    return sse_text_delta(text_id, cleaned)


def emit_text_end(text_id: str) -> AssistantStreamEvent:
    return sse_text_end(text_id)


def emit_stream_error(kind: str = "request_failed", *, detail: str | None = None) -> AssistantStreamEvent:
    """SSE error event. Never forwards raw exception text to errorText."""
    del detail  # raw detail is never a user-facing payload
    message = _FALLBACK_BY_KIND.get(kind) or _FALLBACK_BY_KIND["request_failed"]
    return sse_error(message)


def chip_status_text(envelope: dict[str, Any] | None) -> str:
    """Non-leaking tool-chip status. The bubble, not the chip, is the prose."""
    env = coerce_user_envelope(envelope or {})
    if env.get("success") is not False:
        return ""
    code = str(env.get("error_code") or "tool_error").strip().lower()
    integration = str(env.get("integration") or "").strip()
    if code == "auth_expired":
        if integration:
            return f"Your {_product_label(integration)} sign-in expired. Reconnect it and I'll pick this up."
        return "That sign-in expired. Reconnect it and I'll pick this up."
    if code == "tool_not_available":
        if integration:
            return f"{_product_label(integration)} isn't connected yet."
        return CHIP_STATUS["tool_not_available"]
    return CHIP_STATUS.get(code, CHIP_STATUS["tool_error"])


def _product_label(integration: str | None) -> str:
    """Product name for a vendor slug (``google_analytics`` -> Google Analytics)."""
    slug = str(integration or "").strip()
    if not slug:
        return ""
    try:
        from app.services.connector_semantic_registry import connector_display_name

        return connector_display_name(slug) or slug
    except Exception:  # noqa: BLE001 — copy only; never fail the turn over a label
        return slug.replace("_", " ").title()


def _prompt_safe_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    env = coerce_user_envelope(envelope)
    data = env.get("data") if isinstance(env.get("data"), dict) else {}
    data_keys = sorted(str(k) for k in list(data.keys())[:24])
    detail = env.get("error_detail")
    if looks_like_raw_backend(str(detail or "")):
        detail = None
    summary = None
    if env.get("success") is not False:
        for key in ("text", "summary", "answer", "message", "label"):
            value = data.get(key)
            if isinstance(value, str) and value.strip() and not looks_like_raw_backend(value):
                summary = value.strip()[:400]
                break
    return {
        "success": bool(env.get("success")),
        "error_code": env.get("error_code"),
        "error_detail": detail,
        "action": env.get("action") or env.get("tool"),
        "data_keys": data_keys,
        "data_summary": summary,
    }


def _history_excerpt(history: Iterable[dict[str, Any]] | None, *, limit: int = 4) -> str:
    rows: list[str] = []
    for row in list(history or [])[-limit:]:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or row.get("speaker") or "").strip() or "turn"
        text = str(row.get("content") or row.get("text") or row.get("task") or row.get("summary") or "").strip()
        if not text:
            continue
        rows.append(f"{role}: {text[:240]}")
    return "\n".join(rows)


def _system_prompt(*, spoken: bool) -> str:
    from app.services.cognitive_harness_behavior import (
        HARNESS_COMPOSE_RULES,
        harness_behavior_section,
    )

    spoken_note = ""
    if spoken:
        spoken_note = (
            "\n\nThis turn is SPOKEN. Use Register 5 on top of the matching register: "
            "short sentences, no markdown, no bullets, no code.\n"
        )
    harness = harness_behavior_section(HARNESS_COMPOSE_RULES)
    return (
        MODULE_D_UNIFIED_SYSTEM_SPEC
        + "\n"
        + CONVERSATIONAL_BEHAVIOR_SECTION
        + spoken_note
        + (f"\n{harness}\n" if harness else "")
        + "\n## Response Composer (mandatory)\n"
        "You are writing the only text the user will see for this turn's outcome.\n"
        "Describe the structured result in natural, register-correct language.\n"
        "Write like a friendly colleague: use contractions and everyday words. Name the "
        "product (HubSpot, Google Analytics, QuickBooks) instead of words like connector, "
        "provider, system, read, record, verified, or observation.\n"
        "Never quote stack traces, SQL, exception class names, error codes, catalog "
        "action keys, or internal ids. Never say you are an AI or a composer.\n"
        "If the outcome is a failure, say what happened and, when useful, what happens next.\n"
        "If the outcome is ambiguous, ask ONE specific clarifying question and stop.\n"
        "If the outcome is success, be concise. Same voice as a success message — "
        "never switch into a scripted-assistant or error-template register.\n"
        "Never answer with a bare lifecycle word such as 'Stopped.', 'Failed.', "
        "'Pending.', 'Blocked.', or 'Complete.'. Translate system state into normal "
        "conversation: say what happened in plain English, keep it brief, and give the "
        "next useful move only when it helps. Prefer 'You stopped me before I finished' "
        "over system-style wording such as 'The response was interrupted.' Do not expose "
        "orchestration vocabulary as dialogue.\n"
        "Never invent record counts, revenue, tickets, deals, invoices, traffic, "
        "or workflow outcomes. Only state those facts when the envelope includes "
        "provider_result_evidence from a completed provider observation.\n"
        "AUTHORITATIVE ACTION STATE in the envelope overrides conversation history. "
        "If execution_verified is true, the action completed — do not refuse it, "
        "do not say it is not permitted, and do not claim you did not run it. "
        "If the envelope says the action is waiting for approval, ask for approval "
        "without claiming it already ran. If success is false, do not claim completion.\n"
    )


def _user_prompt(
    *,
    kind: str,
    envelope: dict[str, Any],
    user_message: str,
    draft: str | None,
) -> str:
    safe = _prompt_safe_envelope(envelope)
    draft_note = ""
    if draft and not looks_like_raw_backend(draft):
        draft_note = f"\nDraft to rewrite (may be templated — do not copy robotically):\n{draft[:600]}\n"
    elif draft and looks_like_raw_backend(draft):
        draft_note = "\nA raw backend payload was suppressed. Speak from the envelope only.\n"
    if kind == "progress":
        stage = ""
        data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
        stage = str((data or {}).get("stage") or envelope.get("action") or "").strip()
        return (
            f"Kind: progress\n"
            f"Loop stage that actually started: {stage or 'unknown'}\n"
            f"User said: {(user_message or '')[:500]}\n"
            f"Envelope: {safe}\n"
            f"{draft_note}"
            "Write ONE short spoken sentence for this real loop stage. "
            "Do not invent extra work, tools, or execution. "
            "Do not say you executed anything unless the envelope says so. No preamble."
        )
    return (
        f"Kind: {kind}\n"
        f"User said: {(user_message or '')[:500]}\n"
        f"Envelope: {safe}\n"
        f"{draft_note}"
        "Write the user-facing reply now. No preamble."
    )


async def _llm_compose(
    *,
    kind: str,
    envelope: dict[str, Any],
    user_message: str,
    spoken: bool,
    history: list[dict[str, Any]] | None,
    draft: str | None,
    settings: Any,
    org_id: str,
    compose_fn: ComposeFn | None,
) -> str:
    if compose_fn is not None:
        try:
            return await compose_fn(
                kind=kind,
                envelope=envelope,
                user_message=user_message,
                spoken=spoken,
                draft=draft,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("response_composer_fn_failed kind=%s error=%s", kind, type(exc).__name__)
            return ""
    if getattr(settings, "disable_ai", False):
        return ""
    from app.services.model_router import TaskType, get_model_router

    history_block = _history_excerpt(history)
    system = _system_prompt(spoken=spoken)
    prompt = _user_prompt(kind=kind, envelope=envelope, user_message=user_message, draft=draft)
    if history_block:
        prompt = f"Recent conversation:\n{history_block}\n\n{prompt}"
    try:
        response = await get_model_router().complete(
            TaskType.CONTENT_GENERATION,
            prompt,
            system_prompt=system,
            temperature=0.4,
            max_tokens=220 if spoken else 320,
            org_id=org_id,
        )
        return str(getattr(response, "content", "") or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("response_composer_llm_failed kind=%s error=%s", kind, type(exc).__name__)
        from app.services.ai_guardrails import AIContentFlaggedError

        if isinstance(exc, AIContentFlaggedError):
            return _GUARDRAIL_FLAGGED
        return ""


def _fallback_text(kind: str, envelope: dict[str, Any] | None = None) -> str:
    if kind == "success":
        if envelope_allows_completion_claim(envelope):
            return _FALLBACK_BY_KIND["success"]
        return _FALLBACK_BY_KIND["canned"]
    return _FALLBACK_BY_KIND.get(kind) or _FALLBACK_BY_KIND["error"]


def _compose_inputs(
    envelope: dict[str, Any] | None,
    *,
    kind: str | None,
    draft: str | None,
    settings: Any,
) -> tuple[dict[str, Any], str, bool, str, int]:
    """Decide whether this outcome needs the Composer LLM.

    Returns the coerced envelope, the resolved kind, ``must_compose``, the text
    the outcome uses without a model call, and the structured block count.
    """
    env = coerce_user_envelope(envelope or {"success": True, "data": {"text": draft or ""}})
    resolved_kind = kind or envelope_kind(env)
    from app.services.structured_assistant_response import (
        blocks_from_dicts,
        merge_blocks_with_prose,
    )

    blocks_raw = env.get("response_blocks")
    if not blocks_raw and isinstance(env.get("data"), dict):
        blocks_raw = env["data"].get("response_blocks")
    structured_blocks = blocks_from_dicts(blocks_raw if isinstance(blocks_raw, list) else None)
    system_state_only = looks_like_system_state_only(draft)
    must_compose = (
        resolved_kind in MUST_COMPOSE_KINDS
        or looks_like_raw_backend(draft)
        or system_state_only
    )
    if resolved_kind == "progress" and draft and not looks_like_raw_backend(draft):
        must_compose = False
    if resolved_kind == "plan_hold" and draft and not looks_like_raw_backend(draft):
        must_compose = False
    # P5: human-waiting workflow narration is already drafted by orchestration.
    if resolved_kind == "workflow_waiting" and draft and not looks_like_raw_backend(draft):
        must_compose = False
    # Spoken Metric B plan-hold: orchestration already composed the staged plan;
    # re-running the Composer LLM adds 3–15 s with no user value.
    if resolved_kind == "plan_hold" and draft and not looks_like_raw_backend(draft):
        must_compose = False
    # Phrase-bank greetings are already user-facing English. Composer still owns
    # leak filtering via looks_like_raw_backend / finalize; skip a second LLM rewrite.
    if resolved_kind == "shortcut" and draft and not looks_like_raw_backend(draft):
        must_compose = False
    if (
        resolved_kind == "error"
        and draft
        and not looks_like_raw_backend(draft)
        and env.get("success") is False
    ):
        must_compose = False
        if env.get("execution_verified") is True or (
            isinstance(env.get("data"), dict) and env["data"].get("execution_verified") is True
        ):
            must_compose = False
    if (
        resolved_kind == "clarify"
        and draft
        and not looks_like_raw_backend(draft)
        and str(
            env.get("canonical_lifecycle")
            or (
                env["data"].get("canonical_lifecycle")
                if isinstance(env.get("data"), dict)
                else ""
            )
            or ""
        )
        == "AWAITING_APPROVAL"
    ):
        must_compose = False
    # Bare lifecycle/system-state copy must never bypass the composer, even when
    # the surrounding outcome would normally use a prewritten canned response.
    # This check is repeated after the bypass rules below so "Stopped." cannot be
    # re-enabled by a literal/canned optimization.

    # P2: sealed operational READ already produced a complete canned draft with
    # provider evidence. A second LLM rewrite is not Composer authority — skip it.
    if (
        resolved_kind == "canned"
        and draft
        and not looks_like_raw_backend(draft)
        and bool(getattr(settings, "convergence_p2_canned_literal_v1", True))
        and (
            env.get("provider_result_evidence")
            or (isinstance(env.get("data"), dict) and env["data"].get("provider_result_evidence"))
            or env.get("execution_verified") is True
            or (isinstance(env.get("data"), dict) and env["data"].get("execution_verified") is True)
            or str(env.get("canonical_lifecycle") or "") in {
                "COMPLETED",
                "EXECUTED_UNVERIFIED",
                "OUTCOME_UNCERTAIN",
                "FAILED",
                "AWAITING_APPROVAL",
            }
        )
    ):
        must_compose = False
    path = str(
        env.get("execution_path")
        or (
            env["data"].get("execution_path")
            if isinstance(env.get("data"), dict)
            else ""
        )
        or ""
    )
    # Catalog lookup is already user-facing English. Skipping the Composer LLM
    # is still Composer-owned (leak filter + finalize); it is not a second runtime.
    if (
        resolved_kind == "canned"
        and path in {
            "catalog_search_eligible",
            "listing_f2_read",
            "listing_f2_read_resume",
            "computer_browser_read",
            "computer_browser_read_resume",
            "computer_browser_interact_compile",
            "computer_browser_interact_confirm",
            "computer_browser_interact_resume",
            "entity_join_store",
            "recent_write_observation",
        }
        and draft
        and not looks_like_raw_backend(draft)
    ):
        must_compose = False
    if system_state_only:
        must_compose = True

    text = (draft or "").strip()
    if structured_blocks:
        text = merge_blocks_with_prose(structured_blocks, text)
        must_compose = must_compose and looks_like_raw_backend(text)

    text = align_draft_to_compiled_timeframe(text, env)
    return env, resolved_kind, must_compose, text, len(structured_blocks)


# Kinds whose draft is already user-facing prose written by our own code (an
# approval prompt, a specific question, a progress line). When the Composer
# model is unavailable the draft says more than the generic line for its kind
# ("what's the target?"). Error kinds keep the generic line: their drafts can
# carry provider detail.
_DRAFT_SAFE_KINDS = frozenset(
    {"progress", "clarify", "validation", "workflow_waiting", "plan_hold", "correction", "shortcut", "canned"}
)


def _usable_draft(draft: str | None, resolved_kind: str, user_message: str = "") -> str | None:
    text = (draft or "").strip()
    if not text or resolved_kind not in _DRAFT_SAFE_KINDS:
        return None
    if looks_like_raw_backend(text) or looks_like_system_state_only(text):
        return None
    if user_message and text.lower() == user_message.strip().lower():
        # Some callers pass the user's own words as the draft.
        return None
    return text


# Returned by ``_llm_compose`` when a guardrail refused the turn (not an outage).
_GUARDRAIL_FLAGGED = "\x00guardrail_flagged"


def _resolve_composed(
    composed: str,
    *,
    draft: str | None,
    resolved_kind: str,
    env: dict[str, Any],
    user_message: str = "",
    guardrail_flagged: bool = False,
) -> tuple[str, bool, bool]:
    """(text, used_model, fallback) for a Composer LLM result (empty = failed).

    A guardrail refusal always takes the generic line for the kind; only a
    model outage may fall back to a safe draft.
    """
    if composed == _GUARDRAIL_FLAGGED:
        composed, guardrail_flagged = "", True
    if composed and not looks_like_raw_backend(composed):
        return composed, True, False
    usable = None if guardrail_flagged else _usable_draft(draft, resolved_kind, user_message)
    if usable:
        return usable, False, True
    return _fallback_text(resolved_kind, env), False, True


def _postprocess_composed_text(
    text: str,
    *,
    env: dict[str, Any],
    resolved_kind: str,
    draft: str | None,
) -> tuple[str, bool]:
    """Every check composed prose passes before anyone sees or hears it.

    Pure (no I/O), so a spoken stream can run it on each sentence prefix.
    Returns the text and whether a fallback replaced it.
    """
    fallback = False
    try:
        identity = env.get("identity_literals")
        if not identity and isinstance(env.get("data"), dict):
            identity = env["data"].get("identity_literals")
        text = finalize_user_facing_message(
            text,
            context="response_composer",
            identity_literals=identity if isinstance(identity, list) else None,
        )
    except Exception:  # noqa: BLE001
        from app.services.user_facing_copy_guard import scrub_raw_catalog_keys

        text = scrub_raw_catalog_keys(text or "")
        if looks_like_raw_backend(text):
            text = _fallback_text(resolved_kind, env)
            fallback = True
    text = align_draft_to_compiled_timeframe(text, env)

    code = str(env.get("error_code") or "").strip()
    if code and len(code) >= 4:
        text = re.sub(rf"\b{re.escape(code)}\b", "", text)
        text = collapse_spaces_keep_lines(text)
    if looks_like_raw_backend(text) or not text:
        if resolved_kind in {"progress", "plan_hold"} and draft and not looks_like_raw_backend(
            draft
        ):
            text = draft.strip()
        else:
            text = _fallback_text(resolved_kind, env)
        fallback = True

    if resolved_kind == "success":
        text = reject_premature_done(
            text,
            env,
            fallback=_fallback_text("success", env),
        )
        # Outcome Ownership: completion language is a class of claims, not only
        # the literal "Done.". A model may paraphrase success, so mechanically
        # bound every completion-shaped claim to verified execution evidence.
        if (
            envelope_has_consequential_action(env)
            and has_completion_claim(text)
            and not envelope_allows_completion_claim(env)
        ):
            text = (
                (draft or "").strip()
                if draft and not has_completion_claim(draft) and not looks_like_raw_backend(draft)
                else (
                    f"That ran, but I haven't been able to confirm it in "
                    f"{_product_label(str(env.get('integration') or '')) or 'the other tool'} yet."
                )
            )
    from app.services.provider_result_grounding import apply_provider_result_grounding

    text = apply_provider_result_grounding(text, env)
    text = align_composed_text_to_lifecycle(text, env, draft=draft)
    return text, fallback


def _composer_turn_id(env: dict[str, Any]) -> Any:
    trace = env.get("cognitive_turn_trace")
    if isinstance(trace, dict):
        return trace.get("turn_id")
    if isinstance(env.get("data"), dict):
        return env["data"].get("turn_id")
    return None


async def compose_user_reply(
    envelope: dict[str, Any] | None = None,
    *,
    kind: str | None = None,
    draft: str | None = None,
    spoken: bool = False,
    history: list[dict[str, Any]] | None = None,
    user_message: str = "",
    settings: Any = None,
    org_id: str = "",
    compose_fn: ComposeFn | None = None,
    client: Any = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """Return the only user-visible prose for this outcome."""
    env, resolved_kind, must_compose, text, n_blocks = _compose_inputs(
        envelope, kind=kind, draft=draft, settings=settings
    )
    used_model = False
    fallback = False
    if must_compose or not text:
        composed = await _llm_compose(
            kind=resolved_kind,
            envelope=env,
            user_message=user_message,
            spoken=spoken,
            history=history,
            draft=draft,
            settings=settings,
            org_id=org_id,
            compose_fn=compose_fn,
        )
        text, used_model, fallback = _resolve_composed(
            composed, draft=draft, resolved_kind=resolved_kind, env=env, user_message=user_message
        )
    elif looks_like_raw_backend(text):
        composed = await _llm_compose(
            kind=resolved_kind if resolved_kind != "success" else "error",
            envelope=env,
            user_message=user_message,
            spoken=spoken,
            history=history,
            draft=None,
            settings=settings,
            org_id=org_id,
            compose_fn=compose_fn,
        )
        if composed and composed != _GUARDRAIL_FLAGGED and not looks_like_raw_backend(composed):
            text = composed
            used_model = True
        else:
            text = _fallback_text("error")
            fallback = True

    text, post_fallback = _postprocess_composed_text(
        text, env=env, resolved_kind=resolved_kind, draft=draft
    )
    _emit_composer_audit(
        client=client,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        kind=resolved_kind,
        used_model=used_model,
        fallback=fallback or post_fallback,
        success=bool(env.get("success")),
        error_code=env.get("error_code"),
        turn_id=_composer_turn_id(env),
        structured_blocks=n_blocks,
    )
    return text


def _emit_composer_audit(
    *,
    client: Any,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    kind: str,
    used_model: bool,
    fallback: bool,
    success: bool,
    error_code: str | None,
    turn_id: str | None = None,
    structured_blocks: int = 0,
) -> None:
    if client is None or not org_id:
        return
    try:
        submit_audit_off_loop(
            write_audit_event,
            client,
            org_id=org_id,
            actor_id=str(user_id or org_id),
            action=AUDIT_ACTION_COMPOSER_COMPLETED,
            resource_type="conversation" if conversation_id else "response_composer",
            resource_id=str(conversation_id or org_id),
            metadata={
                "kind": kind,
                "usedModel": used_model,
                "fallback": fallback,
                "success": success,
                "errorCode": error_code,
                "turnId": turn_id,
                "structuredBlocks": structured_blocks,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("response_composer_audit_skipped error=%s", exc)


@dataclass
class ComposerPacked:
    text: str
    text_id: str
    events: list[AssistantStreamEvent] = field(default_factory=list)
    kind: str = "success"
    used_model: bool = False
    fallback: bool = False


def events_for_text(
    text: str,
    *,
    existing_text_id: str | None = None,
    close: bool = True,
) -> tuple[str, list[AssistantStreamEvent]]:
    events: list[AssistantStreamEvent] = []
    if existing_text_id:
        text_id = existing_text_id
    else:
        text_id, start = emit_text_start()
        events.append(start)
    if text:
        events.append(emit_text_delta(text_id, text))
    if close:
        events.append(emit_text_end(text_id))
    return text_id, events


async def compose_reply_events(
    envelope: dict[str, Any] | None = None,
    *,
    kind: str = "canned",
    draft: str | None = None,
    spoken: bool = False,
    history: list[dict[str, Any]] | None = None,
    user_message: str = "",
    settings: Any = None,
    org_id: str = "",
    compose_fn: ComposeFn | None = None,
    client: Any = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
    existing_text_id: str | None = None,
    close: bool = True,
) -> ComposerPacked:
    text = await compose_user_reply(
        envelope,
        kind=kind,
        draft=draft,
        spoken=spoken,
        history=history,
        user_message=user_message,
        settings=settings,
        org_id=org_id,
        compose_fn=compose_fn,
        client=client,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    text_id, events = events_for_text(text, existing_text_id=existing_text_id, close=close)
    return ComposerPacked(text=text, text_id=text_id, events=events, kind=kind, used_model=True)


# Sentence boundary for spoken streaming: terminal punctuation (optionally
# closed by a quote or bracket) followed by whitespace.
_SPOKEN_SENTENCE_BOUNDARY = re.compile(r"[.!?][\"')\]]*\s+")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@dataclass
class StreamedComposerReply:
    """Filled in by ``stream_compose_reply_events`` once its events are drained."""

    text: str = ""
    text_id: str | None = None
    streamed: bool = False


async def stream_compose_reply_events(
    envelope: dict[str, Any] | None = None,
    *,
    result: StreamedComposerReply,
    kind: str = "canned",
    draft: str | None = None,
    history: list[dict[str, Any]] | None = None,
    user_message: str = "",
    settings: Any = None,
    org_id: str = "",
    client: Any = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
    existing_text_id: str | None = None,
    close: bool = True,
):
    """Spoken ``compose_reply_events``: the Composer LLM's reply, sentence by sentence.

    Same decision, prompts, guardrails and checks as ``compose_user_reply``;
    only the delivery changes. The model call goes through the router's
    streaming path (``prepare_stream``: kill switch, rate limit, budget, input
    moderation). A sentence is released only when

    - ``_postprocess_composed_text`` leaves everything released so far plus
      this sentence unchanged (so no whole-text check would rewrite it), and
    - output moderation passes for that sentence.

    The first sentence that fails either stops the release. When the model is
    done, the full text runs through the full pipeline exactly as before: if
    nothing was released it is sent whole (the old behavior); if it still
    begins with what was released, the rest follows; otherwise nothing more is
    said and the turn's text is what was released. Unchecked text never leaves.
    Outcomes that need no model call (or any failure before a sentence is
    released) take the existing non-streamed path.
    """
    env, resolved_kind, must_compose, text, n_blocks = _compose_inputs(
        envelope, kind=kind, draft=draft, settings=settings
    )
    if not (must_compose or not text) or getattr(settings, "disable_ai", False):
        packed = await compose_reply_events(
            envelope,
            kind=kind,
            draft=draft,
            spoken=True,
            history=history,
            user_message=user_message,
            settings=settings,
            org_id=org_id,
            client=client,
            user_id=user_id,
            conversation_id=conversation_id,
            existing_text_id=existing_text_id,
            close=close,
        )
        result.text, result.text_id = packed.text, packed.text_id
        for event in packed.events:
            yield event
        return

    from app.services.ai_guardrails import AIContentFlaggedError, moderate_output
    from app.services.model_router import TaskType, get_model_router

    router = get_model_router()
    history_block = _history_excerpt(history)
    prompt = _user_prompt(kind=resolved_kind, envelope=env, user_message=user_message, draft=draft)
    if history_block:
        prompt = f"Recent conversation:\n{history_block}\n\n{prompt}"

    text_id = existing_text_id
    released = ""
    accepted = ""  # released + sentences waiting on moderation
    pending: list[tuple[str, asyncio.Task[None]]] = []
    stopped = False  # no further sentence is accepted
    blocked = False  # moderation flagged a sentence: nothing more is released
    flagged = False  # a guardrail refused input or output (not an outage)
    buffer = ""
    composed = ""

    def _start_text() -> AssistantStreamEvent | None:
        nonlocal text_id
        if text_id is not None:
            return None
        text_id, start = emit_text_start()
        return start

    def _accept(sentence: str) -> None:
        nonlocal accepted, stopped
        candidate = accepted + sentence
        checked, _ = _postprocess_composed_text(
            candidate, env=env, resolved_kind=resolved_kind, draft=draft
        )
        if looks_like_raw_backend(sentence) or _squash(checked) != _squash(candidate):
            stopped = True
            return
        accepted = candidate
        task = asyncio.ensure_future(moderate_output(sentence, settings, router._openai))
        task.add_done_callback(lambda t: t.cancelled() or t.exception())
        pending.append((sentence, task))

    async def _release(*, wait: bool):
        """Yield moderated sentences in order; stop at the first flagged one."""
        nonlocal released, stopped, blocked
        while pending:
            sentence, task = pending[0]
            if not task.done():
                if not wait:
                    return
                await asyncio.wait({task})
            pending.pop(0)
            if blocked or task.cancelled() or task.exception() is not None:
                if not task.cancelled() and isinstance(task.exception(), AIContentFlaggedError):
                    logger.warning("response_composer_spoken_sentence_flagged org_id=%s", org_id)
                    flagged = True
                stopped = blocked = True
                continue
            start = _start_text()
            if start is not None:
                yield start
            released += sentence
            yield emit_text_delta(text_id, sentence)

    def _take_sentences(delta: str) -> None:
        nonlocal buffer
        buffer += delta
        if stopped:
            return
        cut = 0
        for match in _SPOKEN_SENTENCE_BOUNDARY.finditer(buffer):
            cut = match.end()
        if not cut:
            return
        ready, buffer = buffer[:cut], buffer[cut:]
        for sentence in re.findall(r".+?[.!?][\"')\]]*\s+", ready, flags=re.S):
            if stopped:
                return
            piece = sentence if accepted else sentence.lstrip()
            if piece:
                _accept(piece)

    stream_iter = None
    next_chunk: asyncio.Future[Any] | None = None
    try:
        prepared = await router.prepare_stream(
            TaskType.CONTENT_GENERATION,
            prompt,
            system_prompt=_system_prompt(spoken=True),
            temperature=0.4,
            max_tokens=220,
            org_id=org_id,
        )
        stream_iter = router.stream(prepared).__aiter__()
        next_chunk = asyncio.ensure_future(stream_iter.__anext__())
        while True:
            # Wake for the next token or for the oldest sentence's moderation,
            # so a checked sentence is spoken as soon as it clears.
            waiters: set[asyncio.Future[Any]] = {next_chunk}
            if pending and not pending[0][1].done():
                waiters.add(pending[0][1])
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
            async for event in _release(wait=False):
                yield event
            if not next_chunk.done():
                continue
            try:
                chunk = next_chunk.result()
            except StopAsyncIteration:
                next_chunk = None
                break
            next_chunk = asyncio.ensure_future(stream_iter.__anext__())
            if chunk.response is not None:
                composed = str(chunk.response.content or "").strip()
            elif chunk.delta:
                _take_sentences(chunk.delta)
            async for event in _release(wait=False):
                yield event
    except Exception as exc:  # noqa: BLE001 - same contract as _llm_compose: failure = no model text
        logger.warning("response_composer_stream_failed kind=%s error=%s", resolved_kind, type(exc).__name__)
        composed = ""
        stopped = blocked = True
        flagged = flagged or isinstance(exc, AIContentFlaggedError)
        for _sentence, task in pending:
            task.cancel()
    finally:
        if next_chunk is not None and not next_chunk.done():
            next_chunk.cancel()
            await asyncio.wait({next_chunk})
        aclose = getattr(stream_iter, "aclose", None)
        if aclose is not None:
            with contextlib.suppress(Exception):
                await aclose()
    async for event in _release(wait=True):
        yield event

    text, used_model, fallback = _resolve_composed(
        composed,
        draft=draft,
        resolved_kind=resolved_kind,
        env=env,
        user_message=user_message,
        guardrail_flagged=flagged,
    )
    text, post_fallback = _postprocess_composed_text(
        text, env=env, resolved_kind=resolved_kind, draft=draft
    )
    _emit_composer_audit(
        client=client,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        kind=resolved_kind,
        used_model=used_model,
        fallback=fallback or post_fallback,
        success=bool(env.get("success")),
        error_code=env.get("error_code"),
        turn_id=_composer_turn_id(env),
        structured_blocks=n_blocks,
    )
    if not released:
        # Nothing was spoken early: deliver exactly what the old path would.
        start = _start_text()
        if start is not None:
            yield start
        if text:
            yield emit_text_delta(text_id, text)
        result.text = text
    else:
        result.streamed = True
        head, final = _squash(released), _squash(text)
        if not blocked and final.startswith(head):
            # The rest passed the whole-text checks and the router's output
            # moderation of the full reply (a flag there raises above).
            rest = final[len(head) :].strip()
            if rest:
                yield emit_text_delta(text_id, rest)
            result.text = f"{head} {rest}".strip()
        else:
            logger.info(
                "response_composer_spoken_stream_truncated kind=%s released_chars=%s",
                resolved_kind,
                len(head),
            )
            result.text = head
    result.text_id = text_id
    if close and text_id is not None:
        yield emit_text_end(text_id)
