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
from app.services.module_d_unified_voice_spec import MODULE_D_UNIFIED_SYSTEM_SPEC
from app.services.response_envelope import coerce_user_envelope, envelope_kind
from app.services.user_facing_copy_guard import finalize_user_facing_message
from app.workflows.audit import write_audit_event

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
    }
)

# Last-resort blocked-register copy if the compose LLM itself fails.
# Never include the underlying error_detail. Internally labeled composer_fallback.
_FALLBACK_BY_KIND: dict[str, str] = {
    "permission": "You don't have permission to do that. Check access and I'll pick this back up.",
    "timeout": "That took too long on the system side. I didn't finish it — want me to retry?",
    "validation": "I'm missing something I need before I can do that.",
    "clarify": "I need one specific thing before I go further — what's the target?",
    "error": "That didn't go through. I can retry, or we can try a different approach.",
    "request_failed": "I couldn't complete that just now. Try again in a moment.",
    "shortcut": "Here's the short version — tell me what you want to do next.",
    "correction": "Got it, I'll use that from here.",
    "canned": "I have that. What should we do with it?",
    "progress": "I'm working through this now.",
    "success": "Done.",
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
)

_CODE_AS_MESSAGE = re.compile(r"^[a-z][a-z0-9_]{2,}$")

_INTERNAL_IDS = re.compile(
    r"\b(?:org_id|user_id|connector_id|run_id|task_id|conversation_id)\b",
    re.I,
)

ComposeFn = Callable[..., Awaitable[str]]

TTS_SAFE_ERROR = _FALLBACK_BY_KIND["request_failed"]

CHIP_STATUS: dict[str, str] = {
    "permission_denied": "This step needs permission.",
    "missing_scope": "This step needs additional access.",
    "auth_expired": "This connection needs to be signed in again.",
    "connector_timeout": "This step timed out.",
    "timeout": "This step timed out.",
    "statement_timeout": "This step timed out.",
    "validation_error": "This step is missing something required.",
    "connector_not_connected": "This system isn't connected.",
    "channel_not_found": "That destination wasn't found.",
    "rate_limited": "This step was rate-limited.",
    "tool_not_available": "This connector isn't connected.",
    "tool_error": "This step didn't complete.",
}


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
    return False


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
        who = integration or "this"
        return f"This {who} connection expired — reconnect it and I'll pick this up."
    if code == "tool_not_available":
        who = integration or "required"
        return f"The {who} connector isn't connected."
    return CHIP_STATUS.get(code, CHIP_STATUS["tool_error"])


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
    spoken_note = ""
    if spoken:
        spoken_note = (
            "\n\nThis turn is SPOKEN. Use Register 5 on top of the matching register: "
            "short sentences, no markdown, no bullets, no code.\n"
        )
    return (
        MODULE_D_UNIFIED_SYSTEM_SPEC
        + "\n"
        + CONVERSATIONAL_BEHAVIOR_SECTION
        + spoken_note
        + "\n## Response Composer (mandatory)\n"
        "You are writing the only text the user will see for this turn's outcome.\n"
        "Describe the structured result in natural, register-correct language.\n"
        "Never quote stack traces, SQL, exception class names, error codes, catalog "
        "action keys, or internal ids. Never say you are an AI or a composer.\n"
        "If the outcome is a failure, say what happened and, when useful, what happens next.\n"
        "If the outcome is ambiguous, ask ONE specific clarifying question and stop.\n"
        "If the outcome is success, be concise. Same voice as a success message — "
        "never switch into a scripted-assistant or error-template register.\n"
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
        return ""


def _fallback_text(kind: str) -> str:
    return _FALLBACK_BY_KIND.get(kind) or _FALLBACK_BY_KIND["error"]


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
    env = coerce_user_envelope(envelope or {"success": True, "data": {"text": draft or ""}})
    resolved_kind = kind or envelope_kind(env)
    must_compose = resolved_kind in MUST_COMPOSE_KINDS or looks_like_raw_backend(draft)
    if resolved_kind == "progress" and draft and not looks_like_raw_backend(draft):
        must_compose = False
    used_model = False
    fallback = False
    text = (draft or "").strip()

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
        if composed and not looks_like_raw_backend(composed):
            text = composed
            used_model = True
        elif resolved_kind == "progress" and draft and not looks_like_raw_backend(draft):
            text = draft.strip()
            fallback = True
            used_model = False
        else:
            text = _fallback_text(resolved_kind)
            fallback = True
            used_model = False
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
        if composed and not looks_like_raw_backend(composed):
            text = composed
            used_model = True
        else:
            text = _fallback_text("error")
            fallback = True

    try:
        text = finalize_user_facing_message(text, context="response_composer")
    except Exception:  # noqa: BLE001
        from app.services.user_facing_copy_guard import scrub_raw_catalog_keys

        text = scrub_raw_catalog_keys(text or "")
        if looks_like_raw_backend(text):
            text = _fallback_text(resolved_kind)
            fallback = True

    code = str(env.get("error_code") or "").strip()
    if code and len(code) >= 4:
        text = re.sub(rf"\b{re.escape(code)}\b", "", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
    if looks_like_raw_backend(text) or not text:
        if resolved_kind == "progress" and draft and not looks_like_raw_backend(draft):
            text = draft.strip()
        else:
            text = _fallback_text(resolved_kind)
        fallback = True

    _emit_composer_audit(
        client=client,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        kind=resolved_kind,
        used_model=used_model,
        fallback=fallback,
        success=bool(env.get("success")),
        error_code=env.get("error_code"),
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
) -> None:
    if client is None or not org_id:
        return
    try:
        write_audit_event(
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
