"""Shared 7-way pending-reply classifier (Module B structural fix).

Runs before connector / orch / platform status-specific traps. Replaces scattered
CONFIRM_PATTERN + awaiting_params 3-bucket + orch reminder/supersede classification
with one ontology every pending family shares.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.parameter_ledger import (
    EMAIL_RE,
    _is_meta_field_clarify_question,
    _is_side_question_not_slot_answer,
    format_awaiting_params_meta_answer,
    get_ledger,
    is_awaiting_params,
)

logger = get_logger(__name__)

PendingReplyIntent = Literal[
    "slot_answer",
    "confirm",
    "reject",
    "meta_clarify",
    "modify",
    "unrelated",
    "ambiguous",
]

_VALID_INTENTS: frozenset[str] = frozenset(
    {
        "slot_answer",
        "confirm",
        "reject",
        "meta_clarify",
        "modify",
        "unrelated",
        "ambiguous",
    }
)


_CANCEL_ONLY_PHRASES: frozenset[str] = frozenset(
    {
        "cancel",
        "cancel it",
        "cancel that",
        "cancel this",
        "cancel for now",
        "drop it",
        "drop that",
        "drop this",
        "forget it",
        "forget that",
        "forget about it",
        "never mind",
        "nevermind",
        "not now",
        "not right now",
        "scratch that",
        "abort",
        "abort it",
        "abort that",
        "abort this",
        "stop",
        "stop it",
        "stop that",
        "stop this",
        "don't",
        "dont",
        "do not",
    }
)

PENDING_AWAITING_STATUSES = frozenset(
    {
        "awaiting_params",
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_admin_approval",
        "awaiting_step_confirm",
        "collecting",
    }
)


class PendingReplyIntentResult(BaseModel):
    intent: PendingReplyIntent = "ambiguous"
    reason: str = ""


@dataclass
class PendingSnapshot:
    """Normalized view of whatever is pending for classification + answers."""

    status: str = ""
    pending_type: str = ""
    action_label: str = ""
    invoke_action: str = ""
    integration: str = ""
    pending_missing: list[str] = field(default_factory=list)
    plan_goal: str = ""
    has_current_plan: bool = False
    hold_prompt_active: bool = False
    action_args: dict[str, str] = field(default_factory=dict)

    def summary_for_model(self) -> str:
        bits = [
            f"status={self.status or '(none)'}",
            f"type={self.pending_type or '(none)'}",
            f"action={self.action_label or self.invoke_action or '(none)'}",
            f"integration={self.integration or '(none)'}",
        ]
        if self.pending_missing:
            bits.append(f"missing={', '.join(self.pending_missing)}")
        if self.plan_goal:
            bits.append(f"plan_goal={self.plan_goal[:200]}")
        if self.hold_prompt_active:
            bits.append("hold_prompt_active=true")
        if self.action_args.get("to") or self.action_args.get("email"):
            bits.append(f"to={self.action_args.get('to') or self.action_args.get('email')}")
        if self.action_args.get("subject"):
            bits.append(f"subject={self.action_args['subject'][:80]}")
        return "; ".join(bits)


def _pending_action_args(state: dict[str, Any], params: dict[str, Any]) -> dict[str, str]:
    """Best-effort to/subject/body for confirmation reminders (never invent)."""
    args = params.get("args") if isinstance(params.get("args"), dict) else {}
    clarified = state.get("clarified_params") if isinstance(state.get("clarified_params"), dict) else {}
    clarified_args = clarified.get("args") if isinstance(clarified.get("args"), dict) else {}
    ledger = get_ledger(state)
    out: dict[str, str] = {}
    for key in ("to", "email", "subject", "body", "text"):
        value = args.get(key) or clarified_args.get(key) or ledger.get(key)
        if value is not None and str(value).strip():
            out[key] = str(value).strip()
    return out


def _pending_action_proof_line(snap: PendingSnapshot) -> str:
    args = snap.action_args or {}
    to = str(args.get("to") or args.get("email") or "").strip()
    subject = str(args.get("subject") or "").strip()
    if not to and not subject:
        return ""
    bits: list[str] = []
    if to:
        bits.append(f"**To:** {to}")
    if subject:
        bits.append(f"**Subject:** {subject}")
    return "- " + " · ".join(bits)


def build_pending_snapshot(task_state: dict[str, Any] | None) -> PendingSnapshot:
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    params = safe_normalize_stored_dict(pending, key="params") if pending else {}
    current_plan = state.get("current_plan") if isinstance(state.get("current_plan"), dict) else None
    ledger = get_ledger(state)
    missing = list(ledger.pending_missing or [])
    if not missing and pending:
        for key in ("missing", "missing_fields", "pending_missing"):
            raw = params.get(key) or pending.get(key)
            if isinstance(raw, (list, tuple)):
                missing = [str(x) for x in raw if str(x).strip()]
                break
    invoke = str(params.get("invoke_action") or "")
    integration = str(params.get("integration") or "")
    if not integration and "." in invoke:
        integration = invoke.split(".", 1)[0]
    return PendingSnapshot(
        status=str(pending.get("status") or ""),
        pending_type=str(pending.get("type") or ""),
        action_label=str(params.get("label") or params.get("invoke_action") or ""),
        invoke_action=invoke,
        integration=integration.lower(),
        pending_missing=missing,
        plan_goal=str((current_plan or {}).get("goal") or (current_plan or {}).get("summary") or ""),
        has_current_plan=bool(current_plan),
        hold_prompt_active=bool(state.get("pending_hold_prompt")),
        action_args=_pending_action_args(state, params),
    )


def has_pending_family(task_state: dict[str, Any] | None) -> bool:
    snap = build_pending_snapshot(task_state)
    if snap.hold_prompt_active:
        return True
    if snap.has_current_plan:
        return True
    if snap.status in PENDING_AWAITING_STATUSES:
        return True
    if snap.pending_type in {"connector_action", "connector_orchestration"} and snap.status:
        # Exclude terminal statuses that should already be cleared.
        if snap.status not in {"completed", "failed", "cancelled", "executed"}:
            return True
    return False


def _looks_like_slot_answer(text: str, snap: PendingSnapshot) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if EMAIL_RE.search(t):
        return True
    lower = t.lower()
    if re.search(
        r"\b(subject|body|message|channel|recipient|to|email)\s*(?:is|=|:)\s*\S",
        lower,
    ):
        return True
    # Short non-question free text while awaiting_params → treat as slot fill attempt.
    if snap.status == "awaiting_params" and not t.endswith("?") and len(t) >= 2:
        if not re.match(
            r"^(what|which|who|how|why|when|where|are|is|do|does|can|could|should)\b",
            lower,
        ):
            if not _is_side_question_not_slot_answer(t):
                return True
    return False


def _modify_hint(text: str) -> bool:
    return bool(
        re.search(
            r"\b(skip|instead|just|only|change|modify|rather|don't|dont|without|"
            r"forget\s+step|go\s+straight|actually\s+make|update\s+the|"
            r"use\s+.+\s+instead)\b",
            text or "",
            re.I,
        )
    )


def is_clear_pending_cancel_intent(message: str) -> bool:
    """True for clear natural-language cancellation utterances."""
    from app.services.conversational_execution_service import DECLINE_PATTERN

    text = (message or "").strip()
    if not text:
        return False
    if DECLINE_PATTERN.match(text):
        return True
    lower = re.sub(r"[.!?]+$", "", text.lower()).strip()
    if not lower:
        return False
    if re.fullmatch(
        r"no\s+(?:cancel|drop|forget|scratch|abort|stop)"
        r"(?:\s+(?:it|that|this|the\s+plan|this\s+plan|the\s+pending\s+plan|for\s+now|about\s+it))?",
        lower,
    ):
        return True
    if lower in _CANCEL_ONLY_PHRASES:
        return True
    if re.fullmatch(
        r"(?:please\s+)?(?:cancel|drop|forget|scratch|abort|stop)"
        r"(?:\s+(?:it|that|this|the\s+plan|this\s+plan|the\s+pending\s+plan|for\s+now|about\s+it))?",
        lower,
    ):
        return True
    if re.fullmatch(
        r"(?:let'?s|lets)\s+(?:cancel|drop|abort|scratch|stop)\s+"
        r"(?:it|that|this|the\s+plan|this\s+plan)",
        lower,
    ):
        return True
    return False


def classify_pending_reply_fast(
    message: str,
    snap: PendingSnapshot,
) -> PendingReplyIntent | None:
    """Deterministic fast path. Returns None when model classification is needed."""
    from app.services.chat_message_normalize import strip_assistant_scope_prefix
    from app.services.conversational_execution_service import CONFIRM_PATTERN, DECLINE_PATTERN

    text = strip_assistant_scope_prefix(message or "").strip()
    if not text:
        return "ambiguous"

    # Active hold/abandon prompt — map confirm-ish to abandon/proceed via reject/confirm.
    if snap.hold_prompt_active:
        lower = text.lower()
        if is_clear_pending_cancel_intent(text) or re.search(
            r"\b(abandon|drop|discard|forget)\b", lower
        ):
            return "reject"
        if CONFIRM_PATTERN.match(text) or re.search(
            r"\b(hold|keep|pause|aside|new\s+request|proceed)\b", lower
        ):
            return "confirm"
        if _is_meta_field_clarify_question(text):
            return "meta_clarify"
        return "ambiguous"

    if is_clear_pending_cancel_intent(text):
        return "reject"

    if CONFIRM_PATTERN.match(text) or text.lower() in {
        "yes",
        "y",
        "ok",
        "okay",
        "confirm",
        "approved",
        "go ahead",
        "do it",
        "sounds good",
    }:
        # Bare yes while awaiting_params with missing fields is not a slot answer.
        if snap.status == "awaiting_params" and snap.pending_missing:
            return "ambiguous"
        return "confirm"

    if _is_meta_field_clarify_question(text) or re.search(
        r"\b(why (?:do you )?need|what format|which one|what should i (?:put|send|provide))\b",
        text,
        re.I,
    ):
        return "meta_clarify"

    # Modify before slot_answer — "actually make the subject Q3" is a change, not a fill.
    if _modify_hint(text):
        return "modify"

    # Clear unrelated: connector inventory / status while another action is pending.
    if snap.status in {
        "awaiting_params",
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_step_confirm",
        "awaiting_admin_approval",
    }:
        lower = text.lower()
        if re.search(
            r"\b(what|which)\s+connectors?\b|\bconnectors?\s+(?:are|is)\s+connected\b|\bconnected right now\b",
            lower,
        ):
            return "unrelated"

    # Different-connector / run-history imperatives before broad free-text slot fill.
    if snap.status in {
        "awaiting_params",
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_step_confirm",
        "awaiting_admin_approval",
    }:
        lower = text.lower()
        other_connectors = {
            "hubspot",
            "apollo",
            "slack",
            "gmail",
            "asana",
            "salesforce",
            "notion",
        }
        if snap.integration:
            other_connectors.discard(snap.integration)
        mentions_other = any(re.search(rf"\b{re.escape(c)}\b", lower) for c in other_connectors)
        run_history_ish = bool(
            re.search(r"\b(how many|what workflows|run history|workflows?\s+have)\b", lower)
        )
        if (mentions_other or run_history_ish) and not EMAIL_RE.search(text):
            if not re.search(
                r"\b(subject|body|message|channel|recipient|to|email)\s*(?:is|=|:)\s*\S",
                lower,
            ):
                return "unrelated"

    # Clear unrelated: side-question while something is pending.
    if _is_side_question_not_slot_answer(text):
        if not _is_meta_field_clarify_question(text):
            return "unrelated"

    if _looks_like_slot_answer(text, snap) and snap.status in {
        "awaiting_params",
        "collecting",
    }:
        return "slot_answer"

    # Pure social/banter while pending → ambiguous (warm ack + pending note), not model free-form.
    try:
        from app.services.conversational_turn_gate import heuristic_turn_shape

        shape = heuristic_turn_shape(text)
        if shape and shape.shape == "conversational":
            return "ambiguous"
    except Exception:  # noqa: BLE001
        pass

    return None


def _format_conversation_for_classifier(
    conversation_turns: list[dict[str, Any]] | None,
    *,
    max_turns: int = 24,
) -> str:
    """Full recent conversation for model fallback — not a retrieval cut."""
    if not conversation_turns:
        return ""
    lines: list[str] = []
    for turn in conversation_turns[-max_turns:]:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or turn.get("speaker") or "user").strip().lower()
        content = str(turn.get("content") or turn.get("text") or turn.get("message") or "").strip()
        if not content:
            continue
        label = "Assistant" if role in {"assistant", "ai", "model"} else "User"
        lines.append(f"{label}: {content[:1200]}")
    return "\n".join(lines)


async def classify_pending_reply(
    message: str,
    *,
    task_state: dict[str, Any] | None,
    settings: Settings | None = None,
    org_id: str | None = None,
    use_model: bool = True,
    conversation_turns: list[dict[str, Any]] | None = None,
) -> PendingReplyIntent:
    """Classify pending reply.

    Fast path (regex/keyword) is high-confidence only. On miss, when ``use_model``
    is True, a real LLM call reads the pending snapshot plus full recent
    conversation. Never silently default to execute / search / new-query.
    LLM failure → ``ambiguous`` (ask), not a guessed action.
    """
    snap = build_pending_snapshot(task_state)
    if not has_pending_family(task_state):
        return "ambiguous"

    fast = classify_pending_reply_fast(message, snap)
    if fast is not None:
        return fast

    if use_model:
        modeled = await _model_pending_reply_intent(
            message,
            snap=snap,
            settings=settings,
            org_id=org_id,
            conversation_turns=conversation_turns,
        )
        if modeled in _VALID_INTENTS:
            return modeled  # type: ignore[return-value]

    # Conservative default: ask, don't guess or re-emit status.
    return "ambiguous"


async def _model_pending_reply_intent(
    message: str,
    *,
    snap: PendingSnapshot,
    settings: Settings | None,
    org_id: str | None,
    conversation_turns: list[dict[str, Any]] | None = None,
) -> PendingReplyIntent:
    try:
        from app.services.model_router import TaskType, get_model_router

        history = _format_conversation_for_classifier(conversation_turns)
        history_block = (
            f"Full recent conversation (unfiltered):\n{history}\n\n"
            if history
            else "Full recent conversation: (not provided — use pending + reply only)\n\n"
        )
        prompt = (
            "A user has a pending assistant action/plan. Read the FULL conversation "
            "and decide what their latest reply means in context. Do not invent a "
            "default; if unsure, choose ambiguous.\n"
            "Labels (pick exactly one):\n"
            "- slot_answer: supplying a missing field value\n"
            "- confirm: approve / proceed with the pending action\n"
            "- reject: cancel / abandon the pending action\n"
            "- meta_clarify: asking what is needed, why, or what format\n"
            "- modify: changing the pending plan or fields (not a bare yes/no)\n"
            "- unrelated: a new request that is not answering the pending ask\n"
            "- ambiguous: unclear; assistant should ask a specific follow-up\n\n"
            f"{history_block}"
            f"Pending: {snap.summary_for_model()}\n"
            f"Latest user reply: {message}\n"
        )
        response = await get_model_router().complete(
            task_type=TaskType.CLASSIFICATION,
            prompt=prompt,
            system_prompt=(
                "You are classifying user intent against a pending action. "
                "Regex did not match with confidence — comprehend the conversation. "
                'Respond as JSON: {"intent":"slot_answer|confirm|reject|meta_clarify|'
                'modify|unrelated|ambiguous","reason":"..."}'
            ),
            temperature=0.0,
            max_tokens=120,
            response_format=PendingReplyIntentResult,
            org_id=org_id,
        )
        parsed = response.parsed if isinstance(response.parsed, dict) else None
        if not parsed:
            import json

            try:
                parsed = json.loads(response.content or "{}")
            except Exception:  # noqa: BLE001
                return "ambiguous"
        intent = str((parsed or {}).get("intent") or "ambiguous").lower().strip()
        if intent in _VALID_INTENTS:
            return intent  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001
        logger.warning("pending_reply model classify skipped: %s", exc)
    return "ambiguous"


def format_pending_meta_answer(snap: PendingSnapshot) -> str:
    if snap.status == "awaiting_params" or snap.pending_missing:
        return format_awaiting_params_meta_answer(
            snap.pending_missing,
            action_label=snap.action_label or snap.invoke_action or "this action",
        )
    if snap.status in {"awaiting_confirm", "awaiting_admin_approval"}:
        label = snap.action_label or "the pending write"
        proof = _pending_action_proof_line(snap)
        base = (
            f"I'm waiting for your approval to run **{label}**."
            + (f"\n{proof}" if proof else "")
            + "\nReply **yes** to proceed, **cancel** to abort, or tell me what to change."
        )
        return base
    if snap.status in {"awaiting_plan_confirm", "awaiting_step_confirm"} or snap.has_current_plan:
        goal = snap.plan_goal or "the pending plan"
        return (
            f"There's a pending plan: **{goal}**. "
            "Reply **yes** to continue, **cancel** to drop it, or describe the change "
            "(for example skip a step or change the target)."
        )
    return (
        "I still have a pending request open. Tell me the missing value, "
        "say **yes** to proceed, **cancel** to abandon, or ask what I need."
    )


def format_unrelated_hold_prompt(snap: PendingSnapshot, *, new_request: str) -> str:
    pending_label = (
        snap.action_label
        or snap.invoke_action
        or snap.plan_goal
        or "the previous pending request"
    )
    clipped = (new_request or "").strip()
    if len(clipped) > 160:
        clipped = clipped[:157] + "…"
    return (
        f"You have a pending item (**{pending_label}**) that isn't finished. "
        f"Your new message looks like a different request{f' (“{clipped}”)' if clipped else ''}.\n\n"
        "Should I **abandon** the pending item and handle this new request, "
        "or **hold** the pending item aside and proceed with the new request? "
        "Reply `abandon` or `hold`."
    )


def format_ambiguous_clarify(snap: PendingSnapshot) -> str:
    if snap.pending_missing:
        pretty = ", ".join(snap.pending_missing)
        label = snap.action_label or "this action"
        return (
            f"I'm not sure how to apply that to **{label}**. "
            f"Still needed: **{pretty}**. "
            "Reply with those values, ask what format I need, or say **cancel**."
        )
    if snap.status in {"awaiting_confirm", "awaiting_admin_approval"}:
        label = snap.action_label or "the pending write"
        proof = _pending_action_proof_line(snap)
        return (
            f"I still have **{label}** waiting for approval."
            + (f"\n{proof}" if proof else "")
            + "\nSay **yes** to run it, **cancel** to drop it, or describe a change."
        )
    if snap.plan_goal or snap.status in {"awaiting_plan_confirm", "awaiting_step_confirm"}:
        goal = snap.plan_goal or "the pending plan"
        return (
            f"I still have a plan open (**{goal}**). "
            "Say **yes** to continue, **cancel** to drop it, or tell me what to change."
        )
    return (
        "I didn't catch whether that answers the pending request, changes it, "
        "or starts something new. Please clarify in one short sentence."
    )


def emit_pending_reply_audit(
    *,
    client: Any,
    org_id: str,
    actor_id: str,
    conversation_id: str,
    intent: PendingReplyIntent,
    snap: PendingSnapshot,
) -> None:
    if client is None or not org_id:
        return
    try:
        from app.workflows.audit import write_audit_event

        write_audit_event(
            client,
            org_id,
            actor_id or org_id,
            "pending_reply.classified",
            "conversation",
            conversation_id or org_id,
            {
                "intent": intent,
                "pending_status": snap.status,
                "pending_type": snap.pending_type,
                "invoke_action": (snap.invoke_action or "")[:120],
                "has_current_plan": snap.has_current_plan,
                "missing_count": len(snap.pending_missing),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("pending_reply audit skipped: %s", exc)


def map_legacy_plan_intent(intent: PendingReplyIntent) -> str:
    """Bridge for callers still reading PendingPlanIntent."""
    return {
        "confirm": "continue",
        "reject": "cancel",
        "modify": "modify",
        "unrelated": "unclear",
        "ambiguous": "unclear",
        "meta_clarify": "unclear",
        "slot_answer": "continue",
    }.get(intent, "unclear")
