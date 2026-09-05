"""Phase 2 + Phase 3 (conversational-realism): progressive spoken narration
during multi-step tool execution, and honest tool-state speech mapping.

Reuses the EXISTING plan/execution SSE event stream that already drives the
text plan-bar — ``tool-input-available`` / ``tool-output-available`` (see
``app/operators/stream_events.py`` and the AI SDK UI message stream
protocol already emitted by ``execute_task_streaming``) — rather than
building a second, separate progress-tracking mechanism for voice.

Every narrated sentence is derived from the REAL tool name and the REAL
tool-output payload for this turn. When there is nothing genuinely sayable
(``narrate_tool_completed`` returns ``None``), callers must stay silent —
never fabricate a "working on it" filler disconnected from actual state,
per Product Truth.

Phase 3 — honest tool-state speech mapping. What the agent is PERMITTED TO
SAY about a write is gated by the REAL tool-execution state, never by
free-form LLM generation:

  - EXECUTING (``narrate_tool_started`` on a write-shaped tool): "I'm
    updating that now." — spoken the moment the real tool call starts,
    never before (REQUESTED/AUTHORIZED — the pre-approval "Reply yes to
    confirm" ask — is Module D's existing write-approval speech; this
    module only covers what happens once execution genuinely begins).
  - CONFIRMED (``narrate_tool_completed`` when ``output["success"] is
    True``): a real, specific detail read straight from the tool's own
    output when present, otherwise a generic honest confirmation. Never
    fabricated field values.
  - FAILED (``narrate_tool_completed`` when the output reports failure):
    the tool's own real error/reason, never a generic "something went
    wrong" that hides what actually happened.

HARD, NON-NEGOTIABLE CONSTRAINT: the CONFIRMED/FAILED branches only ever
fire from a real ``tool-output-available`` event for *this* call (see the
call site in ``cognitive_llm.py``) — never speculatively, and never before
the tool call has actually returned. Reverting that call-site wiring (so a
success phrase could be spoken from ``tool-input-available`` or from the
model's own free-form text before the real observation arrives) is exactly
the regression ``test_cognitive_llm_tool_narration.py``'s mutation-proof
tests are written to catch.
"""
from __future__ import annotations

import re
from typing import Any

# Verb prefixes real enough to signal "this tool call mutates something" —
# used ONLY to choose the pre-call EXECUTING phrasing (never to gate whether
# a success claim is spoken; that gate is the output["success"] check below).
_WRITE_VERB_GERUNDS: dict[str, str] = {
    "update": "updating that",
    "create": "creating that",
    "add": "adding that",
    "send": "sending that",
    "delete": "deleting that",
    "remove": "removing that",
    "move": "moving that",
    "set": "setting that",
    "assign": "assigning that",
    "close": "closing that",
    "cancel": "cancelling that",
    "schedule": "scheduling that",
    "approve": "approving that",
    "reject": "rejecting that",
    "invite": "sending that invite",
    "share": "sharing that",
    "publish": "publishing that",
    "archive": "archiving that",
    "merge": "merging that",
    "convert": "converting that",
}

# Real, single-value output fields safe to read back verbatim in a CONFIRMED
# sentence — never a guess, only fields the tool's own response actually set.
_CONFIRMED_DETAIL_KEYS = ("stage", "newStage", "status", "newStatus")

# Small, explicit, hand-picked phrasing for the handful of tools common
# enough to deserve one. Everything else falls through to the generic
# camelCase/snake_case humanizer below — never a guessed/invented name.
_FRIENDLY_TOOL_NAMES: dict[str, str] = {
    "searchknowledgebase": "your knowledge base",
    "getpipelinehealth": "your pipeline",
    "listopportunities": "your opportunities",
    "getconnectorstatus": "your connections",
    "searchcrmrecords": "your CRM",
    "getcalendarevents": "your calendar",
}

# Result-list keys checked, in order, when narrating a real tool output.
_LIST_RESULT_KEYS = (
    "results",
    "records",
    "items",
    "contacts",
    "companies",
    "deals",
    "opportunities",
    "rows",
)
_COUNT_KEYS = ("total", "totalResults", "totalCount", "count")


def _humanize_tool_name(tool_name: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", (tool_name or "").lower())
    friendly = _FRIENDLY_TOOL_NAMES.get(key)
    if friendly:
        return friendly
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", tool_name or "").replace("_", " ").replace("-", " ")
    words = [w for w in spaced.split() if w]
    return " ".join(w.lower() for w in words) or "that"


def is_write_shaped_tool_name(tool_name: str) -> bool:
    """Best-effort, name-only signal that a tool call mutates something.

    Selects EXECUTING vs. read-shaped pre-call phrasing only. Never used to
    decide whether a success/failure claim may be spoken — that decision is
    always gated on the real ``tool-output-available`` observation.
    """
    key = re.sub(r"[^a-z]", "", (tool_name or "").lower())
    return any(key.startswith(verb) for verb in _WRITE_VERB_GERUNDS)


def _gerund_phrase(tool_name: str) -> str:
    key = re.sub(r"[^a-z]", "", (tool_name or "").lower())
    for verb, phrase in _WRITE_VERB_GERUNDS.items():
        if key.startswith(verb):
            return phrase
    return "that"


def narrate_tool_started(tool_name: str) -> str:
    """Short, honest, spoken sentence for a real tool call that just started.

    Always sayable — a tool call genuinely starting is real state, not a
    fabrication, unlike an invented "I'm working on it" filler.

    Phase 3: a write-shaped tool gets EXECUTING phrasing ("I'm updating
    that now.") instead of the read-shaped "Let me check X." — the tool
    call is already authorized and running by the time this fires (see
    module docstring), so this is honestly describing real, in-progress
    execution, not a pre-approval ask.
    """
    if is_write_shaped_tool_name(tool_name):
        return f"I'm {_gerund_phrase(tool_name)} now."
    return f"Let me check {_humanize_tool_name(tool_name)}."


def narrate_tool_completed(tool_name: str, output: Any) -> str | None:
    """Short, honest, spoken sentence derived from the REAL tool output.

    Returns ``None`` when there's nothing worth narrating out loud (an
    opaque, empty, or non-dict payload) — silence is always safer than a
    fabricated finding.
    """
    if not isinstance(output, dict):
        return None
    if output.get("success") is False or output.get("error"):
        err = str(output.get("error") or output.get("message") or "").strip()
        if not err:
            return f"That didn't go through when checking {_humanize_tool_name(tool_name)}."
        return f"That didn't go through — {err[:140]}."
    if is_write_shaped_tool_name(tool_name) and output.get("success") is True:
        # CONFIRMED — Phase 3. Only ever reached from a real, returned
        # tool-output-available observation reporting success=True; never
        # spoken speculatively (see module docstring's HARD CONSTRAINT).
        for key in _CONFIRMED_DETAIL_KEYS:
            val = output.get(key)
            if isinstance(val, str) and val.strip():
                return f"Done — I moved it to {val.strip()}."
        return "Done, that went through."
    for key in _LIST_RESULT_KEYS:
        rows = output.get(key)
        if isinstance(rows, list):
            n = len(rows)
            return f"Found {n}." if n else None
    for key in _COUNT_KEYS:
        val = output.get(key)
        if isinstance(val, int):
            return f"Found {val}." if val else None
    return None
