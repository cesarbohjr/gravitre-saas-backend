"""Intent Gateway — sole Policy Enforcement Point before CognitiveTurnKernel.

Industry pattern: one deterministic AI Gateway between every user turn and
full reasoning. Candidates may *propose*. Only this module may *accept*.

Phase 0 inventory (code search 2026-09-10, not memory):

  1. IA nav FAQ          frontend_ia_nav_faq.match_frontend_ia_nav_faq
  2. Response cache       assistant._RESPONSE_CACHE / _response_cache_eligible
  3. Ambiguous-open       conversational_turn_gate.ambiguous_open_clarify_reply
  4. Venting detector      conversational_turn_gate.is_human_moment_venting_no_ask
  5. Definition brief     conversational_turn_gate.definition_brief_reply
  6. Channel override      unified_turn_pending_live.resolve_unified_live_channel_override_reply
  7. Meta-capability       unified_turn_pending_live.resolve_unified_live_meta_capability_reply
  8. Spoken lite-path     operator_task_intent.use_spoken_lite_path (deleted as independent decision)
  9. Spoken LIVE stream    operator_task_intent.spoken_should_stream_live_deltas (modality after kernel)
 10. KB-empty skip         cognitive_turn_kernel conversational spoken KNOWLEDGE skip
 11. Pending-reply         unified_turn_pending_live.resolve_unified_live_pending_reply
                           (kernel continuation, not a new-request shortcut)
 12. Phrase-bank exit      agent_intelligence should_offer_conversational_path
 13. Correction recall    conversational_turn_gate.correction_recall_pushback_reply

Not shortcuts (do not answer without kernel): tool narrowing, sentiment,
speculative read-warm, retrieve_plan_gate, pack-common orch, connector mapper.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from app.services.operator_task_intent import is_operator_task_shaped

# One threshold. Candidates do not get a private bar.
INTENT_GATEWAY_THRESHOLD = 0.92

# Exact matcher hits are high-confidence by construction (binary, narrow regex).
_MATCH_CONFIDENCE = 0.95
_CACHE_CONFIDENCE = 0.92
_PHRASE_BANK_CONFIDENCE = 0.93

_RESPONSE_CACHE_TTL = 300.0
_RESPONSE_CACHE: dict[str, tuple[float, str, list[str]]] = {}

_GREETING_BANK = {
    "greeting": "Hey — I'm here. What do you want to get done?",
    "thanks": "Glad that helped. What should we do next?",
    "banter": "I'm with you. What do you need?",
}
_VENTING_REPLY = (
    "That sounds frustrating. When you're ready, tell me the specific thing you want done."
)


@dataclass(frozen=True)
class CandidateVerdict:
    candidate_id: str
    confidence: float
    answer: str
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayContext:
    message: str
    spoken_mode: bool = False
    conversation_history: list[dict[str, Any]] | None = None
    task_state: dict[str, Any] | None = None
    org_id: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    connected_integrations: list[str] | None = None
    client: Any = None
    settings: Any = None


@dataclass(frozen=True)
class GatewayDecision:
    action: Literal["shortcut", "fallthrough"]
    reason: str
    candidate_id: str | None = None
    confidence: float | None = None
    answer: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def _cache_key(org_id: str, conversation_id: str | None, question: str) -> str:
    digest = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()[:16]
    conv = (conversation_id or "").strip() or "none"
    return f"{org_id}:{conv}:{digest}"


def response_cache_eligible(question: str) -> bool:
    from app.services.conversational_execution_service import CONFIRM_PATTERN, DECLINE_PATTERN

    text = (question or "").strip()
    if not text:
        return False
    if CONFIRM_PATTERN.match(text) or DECLINE_PATTERN.match(text):
        return False
    if is_operator_task_shaped(text):
        return False
    return True


def response_cache_put(
    org_id: str,
    conversation_id: str | None,
    question: str,
    answer: str,
    suggestions: list[str] | None = None,
) -> None:
    if not response_cache_eligible(question):
        return
    _RESPONSE_CACHE[_cache_key(org_id, conversation_id, question)] = (
        time.time(),
        answer,
        list(suggestions or []),
    )


def response_cache_get(
    org_id: str,
    conversation_id: str | None,
    question: str,
) -> tuple[str, list[str]] | None:
    if not response_cache_eligible(question):
        return None
    hit = _RESPONSE_CACHE.get(_cache_key(org_id, conversation_id, question))
    if not hit:
        return None
    ts, content, suggestions = hit
    if time.time() - ts >= _RESPONSE_CACHE_TTL:
        return None
    return content, suggestions


def response_cache_clear() -> None:
    _RESPONSE_CACHE.clear()


def _propose_nav_faq(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.frontend_ia_nav_faq import match_frontend_ia_nav_faq

    hit = match_frontend_ia_nav_faq(ctx.message)
    if not hit or not str(hit.get("answer") or "").strip():
        return None
    return CandidateVerdict(
        candidate_id="ia_nav_faq",
        confidence=_MATCH_CONFIDENCE,
        answer=str(hit["answer"]),
        extras={"hub": hit.get("hub")},
    )


def _propose_response_cache(ctx: GatewayContext) -> CandidateVerdict | None:
    if not ctx.org_id:
        return None
    hit = response_cache_get(ctx.org_id, ctx.conversation_id, ctx.message)
    if not hit:
        return None
    content, suggestions = hit
    if not content.strip():
        return None
    return CandidateVerdict(
        candidate_id="response_cache",
        confidence=_CACHE_CONFIDENCE,
        answer=content,
        extras={"suggestions": suggestions},
    )


def _propose_ambiguous_open(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.conversational_turn_gate import ambiguous_open_clarify_reply

    reply = ambiguous_open_clarify_reply(ctx.message)
    if not reply:
        return None
    return CandidateVerdict(
        candidate_id="ambiguous_open_clarify",
        confidence=_MATCH_CONFIDENCE,
        answer=reply,
    )


def _propose_definition_brief(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.conversational_turn_gate import definition_brief_reply

    reply = definition_brief_reply(ctx.message)
    if not reply:
        return None
    return CandidateVerdict(
        candidate_id="definition_brief",
        confidence=_MATCH_CONFIDENCE,
        answer=reply,
    )


def _propose_venting(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.conversational_turn_gate import is_human_moment_venting_no_ask

    if not is_human_moment_venting_no_ask(ctx.message):
        return None
    return CandidateVerdict(
        candidate_id="venting_no_ask",
        confidence=_MATCH_CONFIDENCE,
        answer=_VENTING_REPLY,
    )


def _propose_correction_recall(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.conversational_turn_gate import correction_recall_pushback_reply

    reply = correction_recall_pushback_reply(ctx.message, ctx.conversation_history)
    if not reply:
        return None
    return CandidateVerdict(
        candidate_id="correction_recall",
        confidence=_MATCH_CONFIDENCE,
        answer=reply,
    )


def _propose_phrase_bank(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.conversational_turn_gate import heuristic_turn_shape
    from app.services.pending_reply_classifier import has_pending_family

    if has_pending_family(ctx.task_state):
        return None
    decision = heuristic_turn_shape(ctx.message)
    if decision is None or decision.shape != "conversational":
        return None
    category = str(decision.category or "")
    reply = _GREETING_BANK.get(category)
    if not reply:
        return None
    if len((ctx.message or "").strip()) > 120:
        return None
    return CandidateVerdict(
        candidate_id="phrase_bank",
        confidence=_PHRASE_BANK_CONFIDENCE,
        answer=reply,
        extras={"category": category},
    )


async def _propose_channel_override(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.pending_reply_classifier import has_pending_family
    from app.services.unified_turn_pending_live import resolve_unified_live_channel_override_reply

    if has_pending_family(ctx.task_state):
        return None
    if not ctx.org_id:
        return None
    result = await resolve_unified_live_channel_override_reply(
        message=ctx.message,
        task_state=ctx.task_state,
        org_id=ctx.org_id,
        client=ctx.client,
        conversation_id=ctx.conversation_id,
        settings=ctx.settings,
    )
    text = str((result or {}).user_message or "").strip() if result is not None else ""
    if not text:
        return None
    return CandidateVerdict(
        candidate_id="channel_override",
        confidence=_MATCH_CONFIDENCE,
        answer=text,
    )


async def _propose_meta_capability(ctx: GatewayContext) -> CandidateVerdict | None:
    from app.services.pending_reply_classifier import has_pending_family
    from app.services.unified_turn_pending_live import resolve_unified_live_meta_capability_reply

    if has_pending_family(ctx.task_state):
        return None
    if not ctx.org_id:
        return None
    result = await resolve_unified_live_meta_capability_reply(
        message=ctx.message,
        task_state=ctx.task_state,
        org_id=ctx.org_id,
        connected_integrations=ctx.connected_integrations,
        client=ctx.client,
        settings=ctx.settings,
    )
    text = str((result or {}).user_message or "").strip() if result is not None else ""
    if not text:
        return None
    return CandidateVerdict(
        candidate_id="meta_capability",
        confidence=_MATCH_CONFIDENCE,
        answer=text,
    )


_SYNC_CANDIDATES: tuple[Callable[[GatewayContext], CandidateVerdict | None], ...] = (
    _propose_nav_faq,
    _propose_response_cache,
    _propose_ambiguous_open,
    _propose_definition_brief,
    _propose_venting,
    _propose_correction_recall,
    _propose_phrase_bank,
)


async def evaluate_intent_gateway(ctx: GatewayContext) -> GatewayDecision:
    """Sole decision: accept a candidate or fall through to CognitiveTurnKernel."""
    text = (ctx.message or "").strip()
    if not text:
        return GatewayDecision(action="fallthrough", reason="empty")
    if is_operator_task_shaped(text):
        return GatewayDecision(action="fallthrough", reason="operator_task_shaped")

    proposals: list[CandidateVerdict] = []
    for propose in _SYNC_CANDIDATES:
        try:
            verdict = propose(ctx)
        except Exception:  # noqa: BLE001
            continue
        if verdict is not None:
            proposals.append(verdict)

    for propose_async in (_propose_channel_override, _propose_meta_capability):
        try:
            verdict = await propose_async(ctx)
        except Exception:  # noqa: BLE001
            continue
        if verdict is not None:
            proposals.append(verdict)

    eligible = [p for p in proposals if p.confidence >= INTENT_GATEWAY_THRESHOLD]
    if not eligible:
        return GatewayDecision(action="fallthrough", reason="below_threshold")
    best = max(eligible, key=lambda p: p.confidence)
    return GatewayDecision(
        action="shortcut",
        reason="candidate_accepted",
        candidate_id=best.candidate_id,
        confidence=best.confidence,
        answer=best.answer,
        extras=best.extras,
    )
