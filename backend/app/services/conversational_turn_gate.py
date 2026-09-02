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

from app.config import Settings
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
    is_vent = bool(_VENTING_RE.search(text))
    asks_for_help = bool(_EXPLICIT_TASK_ASK_RE.search(text))
    # Rule 10: frustration/urgency with no explicit ask → conversational first.
    # Do not treat problem-description words (pipeline, traffic, deals) as a tool
    # request when the user is venting without "show me / pull / please / check…".
    if is_vent and not asks_for_help and not _looks_mixed(text):
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
    """Classify turn shape. Heuristic first; FAST model when ambiguous."""
    heuristic = heuristic_turn_shape(message)
    if heuristic is not None:
        return heuristic

    decision = await _model_turn_shape(
        message,
        org_id=org_id,
        conversation_summary=conversation_summary,
    )

    # Site 8 observability, placed inside the function that owns the call rather
    # than at a caller. Three successive attempts to instrument this from the
    # outside all landed on paths the measured turns never took: this function
    # has only two callers, one bypassed by unified-turn-live and one reached on
    # 3 of 9 LIVE serving paths. Emitting here means the event exists exactly
    # when the model tier actually runs, whoever called it.
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
                    "usedModel": bool(decision.used_model),
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


async def _model_turn_shape(
    message: str,
    *,
    org_id: str | None,
    conversation_summary: str | None,
) -> ConversationalGateDecision:
    """The model tier proper — reached only when the heuristic declines."""
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
        response = await get_model_router().complete(
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
        logger.warning("conversational turn gate model skipped: %s", exc)
        # Fail closed into task pipeline — never drop real work into chitchat.
        return ConversationalGateDecision(
            shape="task_shaped",
            reason=f"model_unavailable:{exc}",
            task_portion=text,
            category="other",
            used_model=False,
        )


def is_human_moment_venting_no_ask(message: str) -> bool:
    """True when the message is frustration/urgency without an explicit tool ask."""
    text = (message or "").strip()
    if not text:
        return False
    return bool(_VENTING_RE.search(text)) and not bool(_EXPLICIT_TASK_ASK_RE.search(text))


# Rule 1: broad "help me improve/plan X" opens that must clarify before answering.
# Shared LIVE path — patterns must cover every surface in the all-surfaces battery
# (Marketing/Sales/HR/default were wired first; Legal + Cyber were missing).
_AMBIGUOUS_OPEN_CLARIFY: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)^\s*help me improve our seo\b"),
        "Happy to. Are we aiming at organic traffic growth, fixing a ranking drop, "
        "or a content calendar — and for which site or market?",
    ),
    (
        re.compile(r"(?i)^\s*help me improve our hiring\b"),
        "Happy to. Are we fixing time-to-hire, candidate quality, interview "
        "consistency, or compliance risk — and for which roles or geo?",
    ),
    (
        re.compile(r"(?i)^\s*help me plan next week'?s?\s+priorities\b"),
        "Happy to. Are we prioritizing revenue closes, customer follow-ups, or "
        "clearing internal blockers — and what's the hard deadline?",
    ),
    (
        re.compile(r"(?i)^\s*help me (?:fix|improve) our outbound\b"),
        "Happy to. Is the pain low reply rates, bad-fit leads, or deals stalling "
        "after first contact — and which channel (email, calls, LinkedIn)?",
    ),
    (
        re.compile(r"(?i)^\s*help me with a contract review\b"),
        "Happy to. Paste the contract text or the specific clauses you want "
        "checked — and is this for red flags, privacy/liability, or a named playbook?",
    ),
    (
        re.compile(r"(?i)^\s*help me harden our saas access\b"),
        "Happy to. Are we hardening identity/SSO/MFA, least-privilege roles, or "
        "vendor/production access paths — and for which SaaS or environment?",
    ),
)


def ambiguous_open_clarify_reply(message: str) -> str | None:
    """Deterministic clarify for known ambiguous opens (rule 1). None if not matched."""
    text = (message or "").strip()
    if not text:
        return None
    for pattern, reply in _AMBIGUOUS_OPEN_CLARIFY:
        if pattern.search(text):
            return reply
    return None


# Rule 9: simple definition asks — brief prose, never Handoff JSON / option dumps.
_DEFINITION_BRIEF: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)^\s*what'?s\s+a\s+meta\s+title\??\s*$"),
        "A meta title is the clickable title search engines show for a page — "
        "keep it unique, under ~60 characters, with the primary query near the front.",
    ),
    (
        re.compile(r"(?i)^\s*what'?s\s+a\s+close\s+date\??\s*$"),
        "A close date is the expected date a deal will be won or finalized — "
        "CRM uses it for forecasting and pipeline timing.",
    ),
    (
        re.compile(r"(?i)^\s*what'?s\s+an?\s+nda\??\s*$"),
        "An NDA is a nondisclosure agreement: a contract that requires parties "
        "not to share confidential information they exchange.",
    ),
    (
        re.compile(r"(?i)^\s*what'?s\s+an?\s+offer\s+letter\??\s*$"),
        "An offer letter is a written job offer summarizing key terms like title, "
        "pay, start date, and employment type — not always the full employment contract.",
    ),
    (
        re.compile(r"(?i)^\s*what'?s\s+mfa\??\s*$"),
        "MFA is multi-factor authentication: signing in with two or more proofs "
        "of identity (for example a password plus an authenticator or security key).",
    ),
    (
        re.compile(r"(?i)^\s*what'?s\s+a\s+standup\??\s*$"),
        "A standup is a short daily team check-in — usually what you finished, "
        "what you're doing next, and any blockers.",
    ),
)


def definition_brief_reply(message: str) -> str | None:
    """Deterministic brief definition for simple what's-X asks (rule 9)."""
    text = (message or "").strip()
    if not text:
        return None
    for pattern, reply in _DEFINITION_BRIEF:
        if pattern.search(text):
            return reply
    return None


_CORRECTION_STANDING_RE = re.compile(
    r"(?i)\bCorrection(?:,\s*standing)?:\s*(.+)$",
)
_RECALL_ASK_RE = re.compile(
    r"(?i)\b(without asking again|remind me)\b",
)
_PUSHBACK_ALSO_RE = re.compile(
    r"(?i)\bAlso:\s*(.+)$",
)


def _history_text_blobs(conversation_history: list[dict[str, Any]] | None) -> list[str]:
    blobs: list[str] = []
    for turn in conversation_history or []:
        if not isinstance(turn, dict):
            continue
        content = turn.get("content")
        if isinstance(content, str) and content.strip():
            blobs.append(content.strip())
            continue
        parts = turn.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    t = str(part.get("text") or "").strip()
                    if t:
                        blobs.append(t)
    return blobs


def _latest_standing_correction(history: list[dict[str, Any]] | None) -> str | None:
    for blob in reversed(_history_text_blobs(history)):
        m = _CORRECTION_STANDING_RE.search(blob)
        if m:
            return m.group(1).strip()
    return None


def _pushback_for_also_clause(also: str) -> str | None:
    text = (also or "").strip()
    low = text.lower()
    if "backlink" in low or "seo farm" in low:
        return (
            "No — don't buy cheap farm backlinks. That risks penalties; earn links "
            "from relevant sites and fix product-page SEO instead."
        )
    if "40%" in low or "mass-email" in low or "mass email" in low or "discount" in low:
        return (
            "No — don't mass-email every stale contact a blanket discount. Segment "
            "first, get offer approval, and only then send a targeted re-engagement."
        )
    if "soc 2" in low or "soc2" in low:
        return (
            "No — don't promise SOC 2 Certified in the proposal without an "
            "attestation on file. Use only Verified language you can support."
        )
    if "scraped" in low and "resume" in low:
        return (
            "No — don't train a model on resumes scraped from job boards without "
            "a rights and privacy review; that source is high risk by default."
        )
    if "0.0.0.0/0" in low or ("ssh" in low and "open" in low):
        return (
            "No — don't open inbound SSH to 0.0.0.0/0. Use a VPN or bastion with "
            "time-bound, least-privilege access instead."
        )
    if "delete" in low and ("database" in low or "prod" in low or "production" in low):
        return (
            "No — don't delete the production database without a backup. Take a "
            "Verified backup first, confirm restore, then use an approved change plan."
        )
    return None


def _recall_answer_from_correction(message: str, correction: str) -> str | None:
    """Map a recall question + standing correction line to a short answer value."""
    low_q = (message or "").lower()
    low_c = correction.lower()
    # Prefer the corrected (post-"not") value when present.
    not_m = re.search(r"(?i)\b(.+?),\s*not\b", correction)
    primary = (not_m.group(1).strip() if not_m else correction).strip()
    primary = re.sub(r"(?i)^(primary market is|governing law is|hiring geo is|"
                     r"primary cloud is|hq is|our office hq is)\s+", "", primary).strip()

    if re.search(r"(?i)\b(market|seo)\b", low_q) and re.search(
        r"(?i)\b(us|u\.s|united states|canada)\b", low_c
    ):
        if re.search(r"(?i)\bus\b|u\.s|united states", low_c):
            return "US"
        return primary
    if re.search(r"(?i)\bgoverning law\b", low_q):
        if "california" in low_c:
            return "California"
        return primary
    if re.search(r"(?i)\b(hiring geo|geo)\b", low_q):
        if "remote" in low_c:
            return "remote-US"
        return primary
    if re.search(r"(?i)\bcloud\b", low_q):
        if "azure" in low_c:
            return "Azure"
        if re.search(r"(?i)\baws\b", low_c):
            return "AWS"
        return primary
    if re.search(r"(?i)\b(city|hq)\b", low_q):
        if "denver" in low_c:
            return "Denver"
        if "austin" in low_c:
            return "Austin"
        return primary
    if re.search(r"(?i)\b(enterprise-only|smb)\b", low_q):
        if "smb" in low_c:
            return "SMB too — enterprise is secondary"
        return primary
    return primary or None


def correction_recall_pushback_reply(
    message: str,
    conversation_history: list[dict[str, Any]] | None,
) -> str | None:
    """Rule 6 (+7): answer standing correction recall; push back on the Also: ask."""
    text = (message or "").strip()
    if not text or not _RECALL_ASK_RE.search(text):
        return None
    correction = _latest_standing_correction(conversation_history)
    if not correction:
        return None
    recall = _recall_answer_from_correction(text, correction)
    if not recall:
        return None
    also_m = _PUSHBACK_ALSO_RE.search(text)
    push = _pushback_for_also_clause(also_m.group(1)) if also_m else None
    if push:
        return f"{recall}.\n\n{push}"
    return f"{recall}."


def should_offer_conversational_path(
    decision: ConversationalGateDecision,
    *,
    has_pending: bool,
) -> bool:
    """Pure conversational short-circuit only when nothing is pending."""
    if has_pending:
        return False
    return decision.shape == "conversational"
