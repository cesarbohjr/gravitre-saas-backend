"""Follow-ups on a website-traffic answer, resolved against the analytics frame.

After a traffic answer the conversation has a subject: a period, the sources
that were read, and the offer that closed the answer ("want me to dig into
where the visits came from, or which pages did best?"). A person's next turn
is usually a small edit to that subject, not a new request:

* "no, last month"                  -> same read, new period
* "actually make it Search Console" -> same period, different source
* "and the week before?"            -> same read, the period before
* "which pages did best?"           -> page breakdown for the same period
* "yes do that" / "sure"            -> run what was offered
* "no thanks"                       -> run nothing
* "ok back to the traffic"          -> same read, the period we were on

This module decides which of those a turn is, from the stored frame. It does
not read data; the traffic handler executes the decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from app.services.canonical_time_resolver import (
    TimeWindow,
    previous_comparable_window,
    resolve_time_window,
    time_window_from_mapping,
)

ANALYTICS_FRAME_KEY = "analytics_frame"

GA = "google_analytics"
GSC = "google_search_console"
ANALYTICS_SOURCES = (GA, GSC)

FollowupKind = Literal["refine", "breakdown", "accept_offer", "decline_offer"]
Breakdown = Literal["pages", "sources"]

# Offer that closes a traffic answer; accepting it runs both breakdowns.
OFFERED_BREAKDOWNS: tuple[Breakdown, ...] = ("sources", "pages")

_GSC_RE = re.compile(r"(?i)\b(search\s*console|gsc|organic\s+search|google\s+search)\b")
_GA_RE = re.compile(r"(?i)\b(google\s+analytics|ga4?)\b")
_ANALYTICS_WORDS_RE = re.compile(
    r"(?i)\b(traffic|visits?|visitors?|sessions?|page\s*views?|pages?|analytics|website|site|"
    r"search\s*console|clicks?|impressions?|numbers)\b"
)
_PAGES_RE = re.compile(r"(?i)\b(pages?|urls?|landing\s+pages?|posts?|articles?)\b")
_SOURCES_RE = re.compile(
    r"(?i)\b(where\b.{0,30}\b(?:came|come|coming)\s+from|sources?|channels?|referr\w*|"
    r"which\s+sites?\s+sent)\b"
)
_RELATIVE_PREVIOUS_RE = re.compile(
    r"(?i)\b(?:the\s+)?(?:(?:week|month|period|quarter)\s+before(?:\s+that)?|"
    r"before\s+that|previous\s+(?:week|period)|prior\s+(?:week|month|period)|"
    r"(?:week|month)\s+prior)\b"
)
_RETURN_RE = re.compile(
    r"(?i)\b(?:back\s+to|return\s+to|about)\s+(?:the\s+|my\s+|our\s+)?"
    r"(traffic|analytics|website|site|numbers|visits)\b"
)
_SWITCH_CUE_RE = re.compile(
    r"(?i)\b(actually|instead|make\s+it|switch\s+to|use|just|only|what\s+about|how\s+about|from|in)\b"
)
# Other subjects. A turn about these is not an edit of the traffic answer.
_OTHER_SUBJECT_RE = re.compile(
    r"(?i)\b(deals?|pipeline|contacts?|compan(?:y|ies)|accounts?|owners?|owns|tickets?|invoices?|"
    r"tasks?|emails?|campaigns?|meetings?|calendar|crm|hubspot|asana|salesforce|slack)\b"
)
_APPRAISAL_ONLY_RE = re.compile(
    r"(?i)^\s*(great|cool|nice|perfect|awesome|excellent|interesting|wow)[\s!.]*$"
)
_MAX_EDIT_WORDS = 10


@dataclass(frozen=True)
class AnalyticsFollowup:
    kind: FollowupKind
    window: TimeWindow | None = None
    sources: tuple[str, ...] = ()
    breakdowns: tuple[Breakdown, ...] = field(default_factory=tuple)
    reason: str = ""


def analytics_frame(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    raw = (task_state or {}).get(ANALYTICS_FRAME_KEY) if isinstance(task_state, dict) else None
    return raw if isinstance(raw, dict) and raw else None


def analytics_frame_patch(
    *,
    message: str,
    window: TimeWindow | dict[str, Any] | None,
    sources: list[str] | tuple[str, ...],
    offer: tuple[Breakdown, ...] | list[str] | None = OFFERED_BREAKDOWNS,
) -> dict[str, Any]:
    """State to persist after a traffic answer so the next turn can edit it."""
    if isinstance(window, TimeWindow):
        window_payload: dict[str, Any] | None = window.as_dict()
    elif isinstance(window, dict):
        window_payload = dict(window)
    else:
        window_payload = None
    return {
        ANALYTICS_FRAME_KEY: {
            "window": window_payload,
            "sources": [s for s in sources if s in ANALYTICS_SOURCES],
            "offer": list(offer or []),
            "answered_message": (message or "").strip(),
        }
    }


def frame_window(task_state: dict[str, Any] | None) -> TimeWindow | None:
    frame = analytics_frame(task_state)
    return time_window_from_mapping(frame.get("window")) if frame else None


def _frame_is_latest_turn(message: str, task_state: dict[str, Any]) -> bool:
    """True when the traffic answer was the turn right before this one.

    ``cognitive_resolution_message`` is the last message canonical ingress
    resolved. Before this turn is resolved it is the previous user message;
    after, it is this message and ``previous_resolution_message`` holds the
    previous one.
    """
    frame = analytics_frame(task_state) or {}
    answered = str(frame.get("answered_message") or "").strip()
    if not answered:
        return False
    current = (message or "").strip()
    last = str(task_state.get("cognitive_resolution_message") or "").strip()
    if last == current and last != answered:
        last = str(task_state.get("previous_resolution_message") or "").strip()
    return last == answered


def _named_sources(text: str) -> tuple[str, ...]:
    named: list[str] = []
    if _GA_RE.search(text):
        named.append(GA)
    if _GSC_RE.search(text):
        named.append(GSC)
    return tuple(named)


def _relative_previous(text: str, base: TimeWindow | None) -> TimeWindow | None:
    if base is None or not _RELATIVE_PREVIOUS_RE.search(text):
        return None
    prior = previous_comparable_window(base)
    if base.interpretation in {"previous_calendar_month", "named_calendar_month"}:
        # Keep month wording ("August 2026") for the period before a month.
        prior = replace(prior, interpretation="named_calendar_month")
    return prior


def _breakdowns(text: str) -> tuple[Breakdown, ...]:
    found: list[Breakdown] = []
    if _SOURCES_RE.search(text):
        found.append("sources")
    if _PAGES_RE.search(text):
        found.append("pages")
    return tuple(found)


def resolve_analytics_followup(
    message: str,
    task_state: dict[str, Any] | None,
    *,
    connected_integrations: list[str] | None = None,
) -> AnalyticsFollowup | None:
    """Decide whether ``message`` edits the traffic answer, and how."""
    state = task_state if isinstance(task_state, dict) else {}
    frame = analytics_frame(state)
    text = (message or "").strip()
    if frame is None or not text:
        return None
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    if str(pending.get("status") or "").startswith("awaiting"):
        # An open approval owns yes/no and short replies.
        return None

    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    available = [s for s in ANALYTICS_SOURCES if not connected or s in connected]
    frame_sources = tuple(s for s in (frame.get("sources") or []) if s in available) or tuple(available)
    base_window = time_window_from_mapping(frame.get("window"))
    latest = _frame_is_latest_turn(text, state)
    words = len(text.split())
    on_topic = bool(_ANALYTICS_WORDS_RE.search(text))
    other_subject = bool(_OTHER_SUBJECT_RE.search(text))

    from app.services.offered_action_continuation import (
        is_confirm_utterance,
        is_decline_utterance,
    )

    offer = tuple(b for b in (frame.get("offer") or []) if b in OFFERED_BREAKDOWNS)
    if latest and offer and words <= 8 and not other_subject:
        if is_decline_utterance(text):
            return AnalyticsFollowup(kind="decline_offer", reason="declined_breakdown_offer")
        if is_confirm_utterance(text) and not _APPRAISAL_ONLY_RE.match(text):
            return AnalyticsFollowup(
                kind="accept_offer",
                window=base_window,
                sources=frame_sources,
                breakdowns=offer,  # type: ignore[arg-type]
                reason="accepted_breakdown_offer",
            )

    if other_subject:
        return None
    if not latest and not on_topic:
        # The traffic answer is no longer what we are talking about.
        return None

    explicit = resolve_time_window(text)
    relative = _relative_previous(text, base_window)
    window = explicit or relative
    named = tuple(s for s in _named_sources(text) if s in available)
    breakdowns = _breakdowns(text)

    if breakdowns and (latest or on_topic) and words <= 14:
        return AnalyticsFollowup(
            kind="breakdown",
            window=window or base_window,
            sources=named or frame_sources,
            breakdowns=breakdowns,
            reason="breakdown_followup",
        )
    if named and len(named) == 1 and words <= _MAX_EDIT_WORDS and (
        latest or _SWITCH_CUE_RE.search(text)
    ):
        return AnalyticsFollowup(
            kind="refine",
            window=window or base_window,
            sources=named,
            reason="source_switch",
        )
    if window is not None and words <= _MAX_EDIT_WORDS and (latest or on_topic):
        return AnalyticsFollowup(
            kind="refine",
            window=window,
            sources=named or frame_sources,
            reason="period_correction" if explicit else "previous_period",
        )
    if _RETURN_RE.search(text):
        return AnalyticsFollowup(
            kind="refine",
            window=base_window,
            sources=named or frame_sources,
            reason="returned_to_traffic",
        )
    return None
