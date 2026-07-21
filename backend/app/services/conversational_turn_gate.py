"""Early gate: task-shaped vs genuinely conversational (additive Module B routing).

Runs only when there is NO pending family. Pending-reply classifier remains the
owner whenever awaiting_* / sticky plan / collecting is active.

Does not weaken write-authority or connector mapping for task-shaped content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TurnShape = Literal["conversational", "task_shaped", "mixed"]

_GREETING_RE = re.compile(
    r"(?i)^\s*("
    r"(?:hi|hey|hello|howdy|yo|sup|hiya)(?:\s*,?\s*)?"
    r"(?:how'?s\s+it\s+going|how\s+are\s+you|how\s+are\s+things|what'?s\s+up)?"
    r"|"
    r"good\s+(morning|afternoon|evening)|"
    r"how'?s\s+it\s+going|how\s+are\s+you|how\s+are\s+things|"
    r"what'?s\s+up|whats\s+up|"
    r"thanks?(?:\s+you)?|thx|ty|"
    r"(?:lol|haha+|heh+|lmao|rofl)(?:\s+\w+){0,3}|"
    r"nice(?:\s+one)?|cool|awesome|great\s+job|well\s+done|"
    r"gm|gn"
    r")[\s!.?]*$"
)

_SOCIAL_HINT_RE = re.compile(
    r"(?i)\b("
    r"how'?s\s+it\s+going|how\s+are\s+you|what'?s\s+up|"
    r"thanks?(?:\s+you)?|thank\s+you|appreciate\s+it|"
    r"haha+|lol|lmao|funny|joke|"
    r"good\s+morning|good\s+afternoon|good\s+evening|"
    r"how(?:'s|\s+is)\s+your\s+day|weather|"
    r"what\s+can\s+you\s+do|are\s+you\s+(?:an\s+)?ai|"
    r"who\s+are\s+you|what\s+are\s+you|"
    r"ugh|annoying|frustrating|this\s+sucks"
    r")\b"
)

# Casual phrasing that still needs real data / connector work — must NOT be conversational.
_DATA_TASK_RE = re.compile(
    r"(?i)\b("
    r"deals?|pipeline|revenue|quota|forecast|contacts?|companies|"
    r"how\s+are\s+the\s+\w+|how(?:'s|\s+is)\s+(?:our|the|my)\s+\w+|"
    r"show\s+me|look\s+up|search|find|list|create|send|post|update|"
    r"hubspot|apollo|slack|gmail|salesforce|asana|notion|"
    r"workflow|run\s+history|connector|approve|execute|"
    r"how\s+many|status\s+of|pull\s+(?:the\s+)?|"
    r"check\s+on|draft|enrich"
    r")\b"
)

_CONNECTOR_HINT_RE = re.compile(
    r"(?i)\b("
    r"hubspot|apollo|slack|gmail|salesforce|asana|notion|jira|"
    r"connector|oauth|/connectors"
    r")\b"
)


class TurnShapeResult(BaseModel):
    shape: TurnShape = "task_shaped"
    reason: str = ""
    social_portion: str = ""
    task_portion: str = ""
    category: str = ""  # greeting|thanks|banter|small_talk|meta_capability|venting|other


@dataclass(frozen=True)
class ConversationalGateDecision:
    shape: TurnShape
    reason: str
    social_portion: str = ""
    task_portion: str = ""
    category: str = "other"
    used_model: bool = False


def heuristic_turn_shape(message: str) -> ConversationalGateDecision | None:
    """Fast deterministic gate. Returns None when the model should decide."""
    text = (message or "").strip()
    if not text:
        return ConversationalGateDecision(
            shape="conversational",
            reason="empty",
            category="greeting",
        )
    if _GREETING_RE.match(text):
        cat = "thanks" if re.search(r"(?i)\bthanks?\b|\bthx\b|\bty\b", text) else "greeting"
        if re.search(r"(?i)\bhaha|lol|lmao|heh", text):
            cat = "banter"
        return ConversationalGateDecision(
            shape="conversational",
            reason="whole_message_social",
            social_portion=text,
            category=cat,
        )
    has_social = bool(_SOCIAL_HINT_RE.search(text))
    has_data = bool(_DATA_TASK_RE.search(text))
    has_connector = bool(_CONNECTOR_HINT_RE.search(text))
    is_vent = bool(re.search(r"(?i)\bugh|annoying|frustrating|sucks\b", text))
    asks_for_help = bool(
        re.search(
            r"(?i)\b(can you|could you|please|fix|reconnect|help me|check|debug)\b",
            text,
        )
    )
    # Mild venting about a connector with no ask → conversational empathy, not task mode.
    if is_vent and has_connector and not asks_for_help and not _looks_mixed(text):
        return ConversationalGateDecision(
            shape="conversational",
            reason="venting_no_ask",
            social_portion=text,
            category="venting",
        )
    if has_data or has_connector:
        if has_social and _looks_mixed(text):
            social, task = _split_mixed(text)
            return ConversationalGateDecision(
                shape="mixed",
                reason="social_plus_task_heuristic",
                social_portion=social,
                task_portion=task or text,
                category="other",
            )
        return ConversationalGateDecision(
            shape="task_shaped",
            reason="data_or_connector_signal",
            task_portion=text,
            category="other",
        )
    is_meta = bool(re.search(r"(?i)what can you do|are you (an )?ai|who are you|what are you", text))
    if is_meta and not has_data and not (has_connector and asks_for_help):
        return ConversationalGateDecision(
            shape="conversational",
            reason="meta_capability",
            social_portion=text,
            category="meta_capability",
        )
    if has_social and len(text) < 160 and (
        is_meta or not re.search(r"(?i)\b(can you|could you|please)\b", text)
    ):
        cat = "small_talk"
        if re.search(r"(?i)\bhaha|lol|lmao|heh|funny|joke", text):
            cat = "banter"
        if re.search(r"(?i)\bugh|annoying|frustrating|sucks\b", text):
            cat = "venting"
        if is_meta:
            cat = "meta_capability"
        return ConversationalGateDecision(
            shape="conversational",
            reason="social_no_task_signal",
            social_portion=text,
            category=cat,
        )
    return None


def _looks_mixed(text: str) -> bool:
    # Comma / "also" / "but" often joins banter to a task.
    return bool(re.search(r"(?i)\b(also|but|anyway|btw)\b|,", text))


def _split_mixed(text: str) -> tuple[str, str]:
    for sep in (r"(?i)\balso\b", r"(?i)\bbut\b", r"(?i)\banyway\b", r"(?i)\bbtw\b", r","):
        parts = re.split(sep, text, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0].strip(" ,."), parts[1].strip(" ,.")
            if left and right:
                # Prefer task on the side with data/connector signals.
                if _DATA_TASK_RE.search(right) or _CONNECTOR_HINT_RE.search(right):
                    return left, right
                if _DATA_TASK_RE.search(left) or _CONNECTOR_HINT_RE.search(left):
                    return right, left
                return left, right
    return "", text


async def classify_turn_shape(
    message: str,
    *,
    settings: Settings | None = None,
    org_id: str | None = None,
    conversation_summary: str | None = None,
) -> ConversationalGateDecision:
    """Classify turn shape. Heuristic first; FAST model when ambiguous."""
    heuristic = heuristic_turn_shape(message)
    if heuristic is not None:
        return heuristic

    text = (message or "").strip()
    try:
        from app.services.model_router import TaskType, get_model_router

        prompt = (
            "Classify whether the user message is genuinely conversational "
            "(greeting, thanks, banter, small talk, meta question about the assistant, "
            "mild venting with no ask) versus task-shaped (wants data, a connector action, "
            "platform work, or a business status check — even if phrased casually).\n"
            "If BOTH appear, use mixed and split social_portion vs task_portion.\n"
            "Casually phrased data asks like 'how are the deals looking' are task_shaped.\n\n"
            f"Recent context: {(conversation_summary or '')[:400]}\n"
            f"User message: {text}\n"
        )
        response = await get_model_router(settings or get_settings()).complete(
            task_type=TaskType.CLASSIFICATION,
            prompt=prompt,
            system_prompt=(
                'Respond as JSON: {"shape":"conversational|task_shaped|mixed",'
                '"reason":"...","social_portion":"...","task_portion":"...",'
                '"category":"greeting|thanks|banter|small_talk|meta_capability|venting|other"}'
            ),
            temperature=0.0,
            max_tokens=160,
            response_format=TurnShapeResult,
            org_id=org_id,
        )
        parsed = response.parsed if isinstance(response.parsed, dict) else None
        if not parsed:
            import json

            try:
                parsed = json.loads(response.content or "{}")
            except Exception:  # noqa: BLE001
                parsed = {}
        shape = str((parsed or {}).get("shape") or "task_shaped").lower().strip()
        if shape not in {"conversational", "task_shaped", "mixed"}:
            shape = "task_shaped"
        return ConversationalGateDecision(
            shape=shape,  # type: ignore[arg-type]
            reason=str((parsed or {}).get("reason") or "model")[:240],
            social_portion=str((parsed or {}).get("social_portion") or "").strip(),
            task_portion=str((parsed or {}).get("task_portion") or "").strip() or text,
            category=str((parsed or {}).get("category") or "other").strip() or "other",
            used_model=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("conversational turn gate model skipped: %s", exc)
        # Fail closed into task pipeline — never drop real work into chitchat.
        return ConversationalGateDecision(
            shape="task_shaped",
            reason=f"model_unavailable:{exc}",
            task_portion=text,
            category="other",
            used_model=False,
        )


def should_offer_conversational_path(
    decision: ConversationalGateDecision,
    *,
    has_pending: bool,
) -> bool:
    """Pure conversational short-circuit only when nothing is pending."""
    if has_pending:
        return False
    return decision.shape == "conversational"
