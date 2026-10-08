"""One conversational tier per turn: light, medium or deep.

Text chat and voice share one brain. The tier only decides how much of the
pre-kernel pipeline a turn needs and which execution mode voice picks; it
never grants tools or bypasses guardrails. Every rule fails closed toward a
deeper tier:

- deep:   operator tasks, connector reads/writes, named apps or business data,
          imperative operational verbs, research, and short continuations of a
          deep exchange or of a pending approval / offered action.
- light:  social and phatic chat with no business noun and no task verb.
- medium: everything else (explanations, comparisons, brainstorming, opinions).

The classifier is deterministic and pure so a speculative voice run and the
confirmed turn compute the same tier for the same text and history.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

ConversationTierName = Literal["light", "medium", "deep"]
_ORDER = {"light": 0, "medium": 1, "deep": 2}


@dataclass(frozen=True)
class ConversationTier:
    tier: ConversationTierName
    reason: str

    def as_trace(self) -> dict[str, str]:
        return {"conversationTier": self.tier, "conversationTierReason": self.reason}


# Named apps / connectors. Mentioning one makes a turn deep unless it is a
# plain definitional question ("what is HubSpot?").
_NAMED_APP_RE = re.compile(
    r"(?i)\b("
    r"hub\s?spot|salesforce|apollo|gmail|google\s*(?:ads|analytics|drive|calendar|sheets|docs)|"
    r"ga4|adwords|slack|zendesk|quickbooks|stripe|shopify|notion|jira|linear|asana|"
    r"clickup|intercom|pipedrive|zoho|outlook|mailchimp|klaviyo|airtable|monday\.com|"
    r"github|gitlab|vercel|datadog|pagerduty|gong|calendly|xero|netsuite"
    r")\b"
)

# Business data nouns. With a possessive or a data verb they are deep; on their
# own they still disqualify light.
_BUSINESS_NOUN_RE = re.compile(
    r"(?i)\b("
    r"pipeline|leads?|deals?|prospects?|contacts?|companies|accounts?|customers?|clients?|"
    r"campaigns?|ad\s*groups?|keywords?|revenue|sales|mrr|arr|churn|bookings|quota|forecast|"
    r"invoices?|payments?|expenses?|budget|spend|roi|kpis?|metrics|analytics|dashboards?|"
    r"reports?|tickets?|workflows?|automations?|agents?|connectors?|integrations?|"
    r"crm|inbox|emails?|calendar|meetings?|orders?|inventory|subscribers?|signups?|"
    r"conversions?|traffic|tasks?|projects?|records?|database|logs?|production|deployments?"
    r")\b"
)
_POSSESSIVE_RE = re.compile(r"(?i)\b(my|our|we|us|the team'?s|the company'?s|this month'?s|last month'?s)\b")
_DATA_QUESTION_RE = re.compile(
    r"(?i)\b(how\s+many|how\s+much|number\s+of|count\s+of|total|list|show(?:\s+me)?|"
    r"which\s+of|top\s+\d+|latest|recent|this\s+(?:week|month|quarter)|last\s+(?:week|month|quarter)|"
    r"yesterday|today'?s|status\s+of)\b"
)

# Operational verbs that ask the system to do something. They count when they
# open the request (optionally after a greeting / politeness lead-in).
_IMPERATIVE_VERBS = (
    r"deploy|merge|run|execute|send|email|create|set\s+up|setup|update|delete|remove|archive|"
    r"schedule|book|draft|post|publish|pull(?:\s+up)?|fetch|sync|export|import|investigate|audit|"
    r"analy[sz]e|check|look\s+up|research|connect|add|assign|approve|launch|pause|enroll|enrich|"
    r"upload|forward|reply\s+to|remind|refund|migrate|log"
)
# Broader verb set: anywhere in the utterance it only disqualifies light.
_TASK_VERBS = (
    _IMPERATIVE_VERBS
    + r"|build|review|find|search|summari[sz]e|compare|track|monitor|generate|prepare|compile|"
    r"download|cancel|qualify|write|call|text|message"
)
_LEAD_IN = (
    r"(?:(?:hey|hi|hello|ok(?:ay)?|so|alright|um+|uh+|yo)[,!.\s]+)*"
    r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|please\s+|i\s+(?:need|want|would\s+like)\s+(?:you\s+)?to\s+|"
    r"go\s+ahead\s+and\s+|let'?s\s+|help\s+me\s+|i'?d\s+like\s+(?:you\s+)?to\s+)?"
)
_IMPERATIVE_OP_RE = re.compile(rf"(?i)^\s*{_LEAD_IN}(?:{_IMPERATIVE_VERBS})\b")
# "create an agent", "analyze my ...": operational regardless of position.
_EMBEDDED_OP_RE = re.compile(
    r"(?i)\b("
    r"create\s+(?:an?\s+|the\s+)?(?:new\s+)?(?:agent|workflow|automation|campaign|list|report|dashboard)|"
    r"(?:analy[sz]e|investigate|audit|debug)\s+(?:my|our|the)\b|"
    r"(?:review|check|pull|look\s+at|dig\s+into|summari[sz]e|find|show\s+me|go\s+through)\s+(?:my|our)\b|"
    r"send\s+(?:an?\s+|the\s+)?(?:email|message|invite|follow[-\s]?up)|"
    r"run\s+(?:a|the|my|our)\s+(?:workflow|report|agent|job|query|audit)|"
    r"across\s+(?:my|our)\s+(?:apps|systems|tools)"
    r")"
)
_RESEARCH_RE = re.compile(
    r"(?i)\b(research|deep\s+dive|look\s+(?:it\s+)?up|search\s+(?:the\s+web|online|for)|"
    r"find\s+out|latest\s+news|competitive\s+analysis|market\s+analysis|sources?\s+for)\b"
)

# "What does merge mean in git?" — asking what a word means is not a task.
_DEFINITIONAL_RE = re.compile(
    r"(?i)^\s*(?:(?:hey|hi|so|ok(?:ay)?)[,!.\s]+)*(?:"
    r"what\s+(?:does|do)\s+.{1,60}\s+(?:mean|stand\s+for|do)\b|"
    r"what(?:'s|\s+is|\s+are)\s+(?:an?\s+|the\s+)?(?:meaning\s+of\s+)?[\w\s.\-']{1,50}\??\s*$|"
    r"define\s+|definition\s+of\s+|meaning\s+of\s+|"
    r"explain\s+(?:what\s+)?(?:an?\s+|the\s+)?[\w\s.\-']{1,40}\s+(?:is|means)\b"
    r")"
)

# Any of these anywhere disqualifies light (task verbs not at sentence start).
_TASK_VERB_ANYWHERE_RE = re.compile(rf"(?i)\b(?:{_TASK_VERBS})\b")

# Social / phatic. Matched with search() and a word cap, not exact match.
_LIGHT_RE = re.compile(
    r"(?i)("
    r"^\s*(?:hi|hey|hello|hiya|howdy|yo|sup|good\s+(?:morning|afternoon|evening|night))\b|"
    r"\bhow\s+(?:are|r)\s+(?:you|u|things)\b|\bhow'?s\s+(?:it\s+going|your\s+day|life|everything|things)\b|"
    r"\bwhat'?s\s+up\b|\bhow\s+(?:was|is)\s+your\s+(?:day|weekend|morning|night|week|trip|vacation|holiday)\b|"
    r"\b(?:my|the|this|your)\s+(?:weekend|vacation|holiday|trip|birthday)\b|"
    r"\b(?:weather|sunny|raining|rainy|snow(?:ing|y)?|cold\s+out|hot\s+out)\b|"
    r"\b(?:lunch|dinner|breakfast|coffee|pizza|tacos?|food|cooking|recipe\s+ideas?)\b|"
    r"\b(?:football|soccer|basketball|baseball|hockey|tennis|the\s+game|the\s+match|playoffs|world\s+cup)\b|"
    r"\b(?:movie|film|tv\s+show|series|music|song|concert|book\s+club|netflix)\b|"
    r"\b(?:my\s+(?:dog|cat|kids?|son|daughter|wife|husband|partner|family|mom|dad))\b|"
    r"^\s*(?:ha(?:ha)+|he(?:he)+|lol|lmao|rofl|nice|cool|awesome|wow|whoa|oh\s+wow|no\s+way|"
    r"interesting|fair\s+enough|makes\s+sense|gotcha|got\s+it|i\s+see|oh\s+really|really|true|"
    r"amazing|great|perfect|love\s+it|love\s+that|same|totally|exactly|right)\b|"
    r"\bthat'?s\s+(?:so\s+|really\s+|pretty\s+)?(?:wild|funny|hilarious|crazy|awesome|great|cool|nice|"
    r"amazing|interesting|wonderful|sad|rough|fair|true|cute|lovely)\b|"
    r"\b(?:tell\s+me\s+a\s+joke|another\s+joke|a\s+joke|make\s+me\s+laugh|say\s+something\s+funny|"
    r"fun\s+fact|a\s+pun|riddle|knock\s+knock|you'?re\s+(?:funny|hilarious|great|the\s+best|awesome|sweet))\b|"
    r"\b(?:thanks|thank\s+you|thx|ty|cheers|appreciate\s+it|much\s+appreciated)\b|"
    r"\b(?:bye|goodbye|see\s+you|see\s+ya|talk\s+(?:to\s+you\s+)?later|good\s+night|take\s+care|have\s+a\s+good)\b|"
    r"\bi'?m\s+(?:so\s+|really\s+|pretty\s+|a\s+bit\s+|kind\s+of\s+)?(?:tired|exhausted|stressed|happy|excited|bored|"
    r"sad|good|great|fine|okay|ok|well|hungry|sleepy|nervous|anxious)\b|"
    r"\bi\s+feel\s+(?:so\s+|really\s+)?(?:tired|great|good|bad|down|happy|stressed)\b|"
    r"\b(?:can\s+you\s+hear\s+me|are\s+you\s+(?:there|still\s+there)|you\s+there)\b|"
    r"\b(?:what'?s\s+your\s+name|who\s+are\s+you|nice\s+to\s+meet\s+you|you'?re\s+welcome|no\s+worries)\b"
    r")"
)
_LIGHT_MAX_WORDS = 16

# Short continuations / answers to whatever the assistant said last.
_CONTINUATION_RE = re.compile(
    r"(?i)^\s*(?:(?:yes|yeah|yep|yup|sure|ok(?:ay)?|alright|right|great|perfect|cool|fine|no|nope|"
    r"actually|please|wait|hmm+|um+|uh+)[,.!\s]*)*"
    r"(?:"
    r"(?:yes|yeah|yep|yup|sure|ok(?:ay)?|alright|absolutely|definitely|of\s+course|please|correct|exactly|"
    r"no|nope|not\s+yet|not\s+now|wait|hold\s+on|hang\s+on|stop)|"
    r"(?:please\s+)?(?:do|send|run|execute|approve|create|go\s+for|proceed\s+with|cancel|undo|drop|"
    r"skip|use|pick|take|choose|try)\s+(?:it|that|this|those|them|both|all|the\s+\w+(?:\s+one)?)|"
    r"go\s+(?:ahead|for\s+it)|do\s+it|let'?s\s+(?:do\s+it|go|go\s+with\s+.{1,30})|sounds\s+good|"
    r"that\s+(?:one|works|sounds\s+good)|(?:the\s+)?(?:first|second|third|fourth|last|other)\s+one|"
    r"(?:option|number)\s+(?:\d+|one|two|three|four)|both|all\s+of\s+(?:them|those)|neither|"
    r"never\s*mind|scratch\s+that|cancel\s+(?:it|that)|no\s+wait|not\s+that\s+one|"
    r"same\s+as\s+(?:before|last\s+time)|just\s+(?:the\s+)?\w+(?:\s+one)?|more|tell\s+me\s+more|"
    r"keep\s+going|continue|and\s+(?:then|the\s+rest)"
    r")"
    r"(?:[,.!\s]+(?:please|now|then|thanks|thank\s+you))*\s*[.!?]*\s*$"
)
_CONTINUATION_MAX_WORDS = 8

_ASSISTANT_OFFER_RE = re.compile(
    r"(?i)(want\s+me\s+to|would\s+you\s+like\s+me\s+to|shall\s+i|should\s+i|do\s+you\s+want\s+me\s+to|"
    r"i\s+can\s+(?:check|pull|send|create|run|draft|set\s+up|look)|happy\s+to\s+(?:check|pull|send|run|draft)|"
    r"ready\s+to\s+(?:send|run|create|execute)|approve|confirm|which\s+(?:one|option)|"
    r"here\s+are\s+(?:a\s+few|some|the|\d+|two|three)\s+options?)"
)


def _words(text: str) -> int:
    return len((text or "").split())


def _max_tier(*tiers: str) -> ConversationTierName:
    return max(tiers, key=lambda t: _ORDER.get(t, 2))  # type: ignore[return-value]


def _last(history: list[dict[str, Any]] | None, role: str, *, skip_text: str | None = None) -> str:
    rows = [r for r in (history or []) if isinstance(r, dict)]
    # Callers differ on whether history already holds the current utterance.
    if skip_text is not None and rows:
        tail = rows[-1]
        if str(tail.get("role") or "").lower() == "user" and str(
            tail.get("content") or tail.get("text") or ""
        ).strip() == skip_text.strip():
            rows = rows[:-1]
    for row in reversed(rows):
        if str(row.get("role") or "").strip().lower() == role:
            return str(row.get("content") or row.get("text") or "").strip()
    return ""


def _pending_reason(task_state: dict[str, Any] | None) -> str | None:
    """Structured state that means the user is mid-task (approval, offer, plan)."""
    state = task_state if isinstance(task_state, dict) else {}
    if not state:
        return None
    try:
        from app.services.reference_resolver import _pending_confirmation_target

        target = _pending_confirmation_target(state)
        if target:
            return f"pending_{target}"
    except Exception:  # noqa: BLE001
        return "pending_state_unreadable"
    try:
        from app.services.pending_reply_classifier import has_pending_family

        if has_pending_family(state):
            return "pending_task_family"
    except Exception:  # noqa: BLE001
        return "pending_state_unreadable"
    try:
        from app.services.offered_action_continuation import offered_from_state

        offered = offered_from_state(state)
        if offered is not None and offered.status in {"awaiting_user_confirmation", "awaiting_confirm"}:
            return "pending_offered_action"
    except Exception:  # noqa: BLE001
        return "pending_state_unreadable"
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    if str(plan.get("terminal_status") or "") in {"running", "waiting_for_approval"}:
        return "active_execution_plan"
    if state.get("pending_hold_prompt"):
        return "pending_hold_prompt"
    return None


def has_pending_task_state(task_state: dict[str, Any] | None) -> bool:
    return _pending_reason(task_state) is not None


def _is_continuation(text: str) -> bool:
    if _words(text) > _CONTINUATION_MAX_WORDS:
        return False
    if _CONTINUATION_RE.match(text):
        return True
    try:
        from app.services.conversational_execution_service import (
            CONFIRM_PATTERN,
            DECLINE_PATTERN,
        )
        from app.services.spoken_write_approval import classify_spoken_write_approval

        if CONFIRM_PATTERN.match(text) or DECLINE_PATTERN.match(text):
            return True
        if classify_spoken_write_approval(text).decision != "none":
            return True
    except Exception:
        logger.debug("conversation_tier_continuation_detector_failed", exc_info=True)
    return False


def is_continuation_utterance(message: str) -> bool:
    """Short answer / confirmation / selection bound to whatever came before."""
    text = (message or "").strip()
    return bool(text) and _is_continuation(text)


def _reference_matched(text: str, task_state: dict[str, Any] | None) -> str | None:
    """Ordinals, 'all of them', confirmations bound to structured task state."""
    if not isinstance(task_state, dict) or not task_state:
        return None
    try:
        from app.services.reference_resolver import resolve_reference

        ref = resolve_reference(text, task_state)
    except Exception:
        logger.debug("conversation_tier_reference_resolver_failed", exc_info=True)
        return None
    if not ref.matched:
        return None
    # A pronoun inside small talk ("haha that's funny") is not a task reference.
    if ref.reason == "demonstrative_pronoun" and _LIGHT_RE.search(text):
        return None
    return f"reference_{ref.kind}"


def _is_definitional(text: str) -> bool:
    if not _DEFINITIONAL_RE.search(text) or _LIGHT_RE.search(text):
        return False
    # "What is my pipeline?" / "what's our revenue" is a data read, not a definition.
    return not (_POSSESSIVE_RE.search(text) or _DATA_QUESTION_RE.search(text))


def _content_tier(text: str) -> ConversationTier:
    """Tier from the utterance alone (no history, no state)."""
    if not text:
        return ConversationTier("medium", "empty")
    from app.services.operator_task_intent import should_keep_full_reasoning_for_spoken

    if should_keep_full_reasoning_for_spoken(text):
        return ConversationTier("deep", "operator_task")
    if _is_definitional(text):
        return ConversationTier("medium", "definitional_question")
    if _IMPERATIVE_OP_RE.search(text):
        return ConversationTier("deep", "imperative_operational_verb")
    if _EMBEDDED_OP_RE.search(text):
        return ConversationTier("deep", "operational_request")
    if _NAMED_APP_RE.search(text):
        return ConversationTier("deep", "named_app")
    if _BUSINESS_NOUN_RE.search(text) and (_POSSESSIVE_RE.search(text) or _DATA_QUESTION_RE.search(text)):
        return ConversationTier("deep", "business_data")
    if _RESEARCH_RE.search(text):
        return ConversationTier("deep", "research_request")
    if (
        _words(text) <= _LIGHT_MAX_WORDS
        and _LIGHT_RE.search(text)
        and not _BUSINESS_NOUN_RE.search(text)
        and not _TASK_VERB_ANYWHERE_RE.search(text)
        and not re.search(r"https?://|\S+@\S+\.\w+|\d{3,}", text)
    ):
        return ConversationTier("light", "social")
    return ConversationTier("medium", "general")


def _assistant_signals_deep(assistant_text: str) -> bool:
    if not assistant_text:
        return False
    if _content_tier(assistant_text).tier == "deep":
        return True
    try:
        from app.services.offered_action_continuation import (
            _WRITE_OFFER_RE,
            claims_future_action,
        )

        if claims_future_action(assistant_text):
            return True
        if _ASSISTANT_OFFER_RE.search(assistant_text) and (
            _WRITE_OFFER_RE.search(assistant_text) or _BUSINESS_NOUN_RE.search(assistant_text)
        ):
            return True
    except Exception:  # noqa: BLE001
        return True
    return False


def classify_conversation_tier(
    message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    task_state: dict[str, Any] | None = None,
) -> ConversationTier:
    """Classify one turn. Pure and deterministic; fails closed toward deep."""
    text = (message or "").strip()
    if not text:
        return ConversationTier("medium", "empty")

    pending = _pending_reason(task_state)
    ref = _reference_matched(text, task_state)
    if ref:
        return ConversationTier("deep", ref)

    if _is_continuation(text):
        if pending:
            return ConversationTier("deep", f"continuation_{pending}")
        assistant_text = _last(history, "assistant")
        prior_user = _last(history, "user", skip_text=text)
        if _assistant_signals_deep(assistant_text):
            return ConversationTier("deep", "continuation_of_deep_assistant_turn")
        prior_tier = _content_tier(prior_user).tier if prior_user else None
        if prior_tier == "deep":
            return ConversationTier("deep", "continuation_of_deep_user_turn")
        asked = bool(assistant_text) and (
            assistant_text.rstrip().endswith("?") or bool(_ASSISTANT_OFFER_RE.search(assistant_text))
        )
        if asked and prior_tier is None:
            # An offer or question with nothing to anchor it: assume it mattered.
            return ConversationTier("deep", "continuation_of_unanchored_offer")
        if prior_tier is not None:
            # Inherit the exchange's depth ("want another joke?" -> "sure" stays light).
            return ConversationTier(prior_tier, f"continuation_inherits_{prior_tier}")
        return ConversationTier("medium", "continuation_without_context")

    result = _content_tier(text)
    if pending and result.tier == "light":
        # Mid-task small talk never takes the lite path.
        return ConversationTier("medium", f"light_demoted_{pending}")
    return result


def tier_to_execution_mode(tier: str) -> str:
    """Light/medium run in fast mode; deep uses the unified agent engine."""
    return "agent" if tier == "deep" else "fast"


def upgrade_spoken_mode_for_tier(mode: str | None, tier: str, *, spoken_mode: bool) -> str | None:
    """Raise a voice turn's pinned fast mode to agent when the brain's tier is deep.

    Voice entry points pick the mode from socket and durable history only. The
    brain also sees task state (a pending approval or offered action), so its
    tier can be deeper; a confirmation like "yes, do that" must then run with
    the tools the offer needs. Never lowers a mode, and leaves text alone.
    """
    if spoken_mode and tier == "deep" and (mode or "").strip().lower() == "fast":
        return "agent"
    return mode
