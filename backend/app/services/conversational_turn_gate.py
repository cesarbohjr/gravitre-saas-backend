"""Early gate: task-shaped vs genuinely conversational (additive Module B routing).

Runs only when there is NO pending family. Pending-reply classifier remains the
owner whenever awaiting_* / sticky plan / collecting is active.

Does not weaken write-authority or connector mapping for task-shaped content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TurnShape = Literal["conversational", "task_shaped", "mixed"]

_GREETING_RE = re.compile(
    r"(?i)^\s*("
    r"(?:hi|hey|hello|howdy|yo|sup|hiya)(?:\s+there)?"
    r"(?:\s*,?\s*)?"
    r"(?:how'?s\s+it\s+going|how\s+are\s+you|how\s+are\s+things|what'?s\s+up)?"
    r"|"
    r"good\s+(morning|afternoon|evening)|"
    r"how'?s\s+it\s+going|how\s+are\s+you|how\s+are\s+things|"
    r"what'?s\s+up|whats\s+up|"
    r"thanks?(?:\s+you)?|thx|ty|"
    r"(?:lol|haha+|heh+|lmao|rofl)(?:\s+[\w']+){0,4}|"
    r"nice(?:\s+one)?|cool|awesome|great\s+job|well\s+done|"
    r"gm|gn"
    r")[\s!.?]*$"
)

_SOCIAL_HINT_RE = re.compile(
    r"(?i)\b("
    r"hey|hi|hello|howdy|yo|"
    r"how'?s\s+it\s+going|how\s+are\s+you|what'?s\s+up|"
    r"thanks?(?:\s+you)?|thank\s+you|appreciate\s+it|"
    r"haha+|lol|lmao|funny|joke|cool|"
    r"good\s+morning|good\s+afternoon|good\s+evening|"
    r"how(?:'s|\s+is)\s+your\s+day|weather|"
    r"what\s+can\s+you\s+do|are\s+you\s+(?:an\s+)?ai|"
    r"who\s+are\s+you|what\s+are\s+you|"
    r"ugh|annoying|frustrating|frustrated|frustration|"
    r"stressed|stressful|under\s+pressure|this\s+sucks|"
    r"killing\s+me|rough\s+spot|bad\s+spot|tight\s+clock"
    r")\b"
)

# Canned LIVE replies are high-confidence only. Longer operator tasks must fall
# through to real reasoning (same class as pending-cancel / meta-query / IA FAQ).
_MAX_CANNED_REPLY_CHARS = 280

# Human-moment / venting lexicon (rule 10) — includes "frustrated" not only "frustrating".
_VENTING_RE = re.compile(
    r"(?i)\b("
    r"ugh|annoying|frustrating|frustrated|frustration|"
    r"stressed|stressful|under\s+pressure|this\s+sucks|"
    r"killing\s+me|cratered|meltdown|panicking|panic"
    r")\b"
)

# Explicit asks that keep a vent in task/mixed mode (still needs tools).
# Avoid bare nouns like "draft" / past-tense problem description ("sent").
_EXPLICIT_TASK_ASK_RE = re.compile(
    r"(?i)\b("
    r"can you|could you|please|help me|"
    r"fix(?:\s+it|\s+this|\s+the)?|reconnect|"
    r"check (?:on|my|our|the|if|whether)|debug|"
    r"show me|look up|search|find|list|pull|"
    r"create|send (?:me|an?|the)|post|update|"
    r"draft (?:me|an?|the|us)|enrich|run (?:the|a|an|my|our)"
    r")\b"
)

# Casual phrasing that still needs real data / connector work — must NOT be conversational.
_DATA_TASK_RE = re.compile(
    r"(?i)\b("
    r"deals?|pipeline|revenue|quota|forecast|contacts?|companies|"
    r"how\s+are\s+the\s+\w+|how(?:'s|\s+is)\s+(?:our|the|my)\s+\w+|"
    r"show\s+me|look\s+up|search|find|list|create|send|post|update|"
    r"hubspot|apollo|slack|gmail|salesforce|asana|notion|"
    r"google\s*ads|adwords|campaigns?|"
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
    is_vent = bool(_VENTING_RE.search(text))
    asks_for_help = bool(_EXPLICIT_TASK_ASK_RE.search(text))
    # Rule 10: frustration/urgency with no explicit ask → conversational first.
    # Do not treat problem-description words (pipeline, traffic, deals) as a tool
    # request when the user is venting without "show me / pull / please / check…".
    from app.services.operator_task_intent import looks_like_operator_task

    if (
        is_vent
        and not asks_for_help
        and not _looks_mixed(text)
        and len(text) <= _MAX_CANNED_REPLY_CHARS
        and not looks_like_operator_task(text)
    ):
        return ConversationalGateDecision(
            shape="conversational",
            reason="human_moment_venting_no_ask",
            social_portion=text,
            category="venting",
        )
    if has_data or has_connector:
        if (has_social or is_vent) and _looks_mixed(text):
            social, task = _split_mixed(text)
            return ConversationalGateDecision(
                shape="mixed",
                reason="social_plus_task_heuristic",
                social_portion=social,
                task_portion=task or text,
                category="venting" if is_vent else "other",
            )
        return ConversationalGateDecision(
            shape="task_shaped",
            reason="data_or_connector_signal",
            task_portion=text,
            category="other",
        )
    from app.services.conversational_reply_service import re_search_meta

    is_meta = re_search_meta(text)
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
        if _VENTING_RE.search(text):
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
    settings: Settings | None = None,  # unused; kept for caller compatibility
    org_id: str | None = None,
    conversation_summary: str | None = None,
    user_id: str | None = None,
    client: Any = None,
    call_site: str = "unspecified",
) -> ConversationalGateDecision:
    """Classify turn shape from the heuristic alone.

    The model tier was RETIRED on 2026-09-02 by product decision, after its
    value was measured rather than assumed
    (docs/delivery/turn-shape-gate-value.md). Three findings drove it:

    1. Conversational quality no longer depends on this gate. The unified-turn
       reasoning model decides it directly, demonstrably — the site 8 probe runs
       produced "Glad it clicked." and "That's a reasonable place to pause."
       while this gate's model tier was dormant and never ran.
    2. The gate's whole-turn consumer, `should_offer_conversational_path`, is
       switched off whenever unified-turn LIVE is enabled, and exists as the
       documented `UNIFIED_TURN_LIVE_ENABLED=false` rollback.
    3. LIVE's own shape hint (`is_task_shaped_for_retrieval`) calls
       `heuristic_turn_shape` DIRECTLY and is scoped to picking a retrieval
       strategy, explicitly never skipping the reasoning call. It would not have
       benefited from the model tier at all.

    So the heuristic is kept — it is free, it is what LIVE actually consumes,
    and every working consumer still works — while the per-turn model call is
    dropped. When the heuristic declines, this fails closed to task_shaped,
    which never routes real work into chitchat.
    """
    heuristic = heuristic_turn_shape(message)
    if heuristic is not None:
        return heuristic

    decision = _declined_to_task_shaped(message)

    # Kept as the only visibility into a component whose production reach was
    # measured at near zero. Volume note: this fires on the ~72% of gate calls
    # the heuristic cannot decide, so if routing ever puts real traffic through
    # this gate, sample it rather than writing a row per turn.
    if user_id:
        try:
            from app.workflows.audit import write_audit_event

            await write_audit_event(
                org_id=org_id or "",
                actor_id=user_id,
                action="turn.shape.classified",
                resource_type="assistant",
                metadata={
                    "shape": decision.shape,
                    "usedModel": False,
                    "modelTierRetired": True,
                    "category": decision.category,
                    "reason": (decision.reason or "")[:120],
                    "callSite": call_site,
                },
                client=client,
                settings=settings,
            )
        except Exception:  # noqa: BLE001
            logger.debug("turn.shape.classified audit skipped", exc_info=True)

    return decision


def _declined_to_task_shaped(message: str) -> ConversationalGateDecision:
    """Fail closed when the heuristic cannot decide: never drop real work into chitchat."""
    text = (message or "").strip()
    return ConversationalGateDecision(
        shape="task_shaped",
        reason="heuristic_declined_model_tier_retired",
        task_portion=text,
        category="other",
        used_model=False,
    )


def is_human_moment_venting_no_ask(message: str) -> bool:
    """True when the message is frustration/urgency without an explicit tool ask."""
    from app.services.operator_task_intent import looks_like_operator_task

    text = (message or "").strip()
    if not text or len(text) > _MAX_CANNED_REPLY_CHARS:
        return False
    if looks_like_operator_task(text):
        return False
    return bool(_VENTING_RE.search(text)) and not bool(_EXPLICIT_TASK_ASK_RE.search(text))


# Rule 1: broad "help me improve/plan X" opens that must clarify before answering.
# Shared LIVE path — patterns must cover every surface in the all-surfaces battery
# (Marketing/Sales/HR/default were wired first; Legal + Cyber were missing).
def ambiguous_open_clarify_reply(message: str) -> str | None:
    """Retired: clarification must generalize through the reasoning path.

    Production replies must not be keyed to benchmark/example wording.
    """
    return None


def definition_brief_reply(message: str) -> str | None:
    """Retired: definitions are generated by the normal conversational model."""
    return None


def correction_recall_pushback_reply(
    message: str,
    conversation_history: list[dict[str, Any]] | None,
) -> str | None:
    """Retired: recall of standing corrections and pushback on risky asks must
    come from the reasoning path with conversation history.

    The old implementation answered with hard-coded values and refusal lines
    keyed to live-battery prompts (scraped resumes, SSH to the world, farm
    backlinks, governing law "California", cloud "Azure"), so a passing battery
    proved the answer bank, not the model.
    """
    return None


def should_offer_conversational_path(
    decision: ConversationalGateDecision,
    *,
    has_pending: bool,
) -> bool:
    """Pure conversational short-circuit only when nothing is pending."""
    if has_pending:
        return False
    return decision.shape == "conversational"
