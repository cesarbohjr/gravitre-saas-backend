"""Typed LIVE replies stream as checked sentences.

Typed chat used to wait for the whole LIVE answer and send it as one block,
because LIVE can still drop or rewrite a reply after the model has written it
(a promise to check instead of answering, a false "disconnected" claim, a tool
round). Sending raw tokens would show text the turn later disowns.

This module streams only what those checks would keep:

- ``typed_should_stream_live_deltas`` decides before the model call. Turns
  whose fallthrough is already decided by the message (operator tasks, a reply
  to a task in progress, orchestration, evidence-plan reads, pack intents, classical
  tool SSE) keep the whole-reply path.
- ``TypedLiveRelease`` holds model text until a sentence or line is complete
  and releases it only when everything released so far, plus that unit,
  passes the same text checks LIVE applies afterwards. The first unit that
  fails, or the first tool-call delta, stops the release for the turn.
- ``remainder_after`` lets the caller send the rest of LIVE's final message
  when it still begins with what was released.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# A complete unit: terminal punctuation (optionally closed by a quote or
# bracket) followed by whitespace, or a line break (markdown lists and tables).
_UNIT_BOUNDARY = re.compile(r"[.!?][\"')\]]*[ \t]+|\n+")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def typed_should_stream_live_deltas(
    *,
    spoken_mode: bool,
    message: str,
    task_state: dict[str, Any] | None = None,
    classification: dict[str, Any] | None = None,
    connected_integrations: list[str] | None = None,
) -> bool:
    """True when a typed LIVE turn may release text before the model finishes."""
    if spoken_mode:
        return False
    text = (message or "").strip()
    if not text:
        return False
    from app.services.conversation_tier import has_pending_task_state
    from app.services.offered_action_continuation import is_unrelated_read_question
    from app.services.operator_task_intent import should_force_live_connector_pipeline

    if should_force_live_connector_pipeline(text):
        return False
    # A draft or offer waiting for a yes keeps the whole-reply path, except
    # for a workspace question that is not about it ("What changed in my
    # workspace since yesterday?"), which LIVE answers on its own.
    if has_pending_task_state(task_state) and not is_unrelated_read_question(text):
        return False
    state = task_state if isinstance(task_state, dict) else {}
    plan = state.get("capability_evidence_plan")
    if state.get("live_classical_handoff_queue") or (
        isinstance(plan, dict) and (plan.get("required") or [])
    ):
        return False
    connected = list(connected_integrations or [])
    try:
        from app.services.capability_evidence_plan import looks_like_ceo_ops_question
        from app.services.chat_orchestration_service import ChatOrchestrationService
        from app.services.pack_common_intent_defaults import (
            try_pack_common_list_create_plan,
            try_pack_common_msp_enrich_workflow_plan,
        )
        from app.services.unified_turn_classical_fallback import (
            message_requires_classical_tool_sse,
        )

        if looks_like_ceo_ops_question(text):
            return False
        if ChatOrchestrationService.is_orchestration_intent(text, state, connected):
            return False
        if try_pack_common_list_create_plan(text, connected_integrations=connected) is not None:
            return False
        if (
            try_pack_common_msp_enrich_workflow_plan(text, connected_integrations=connected)
            is not None
        ):
            return False
        if message_requires_classical_tool_sse(text):
            return False
    except Exception as exc:  # noqa: BLE001 - unknown means keep the whole-reply path
        logger.debug("typed_live_stream_gate_failed: %s", exc)
        return False
    return True


def reply_unit_ok(candidate: str, *, connected_integrations: list[str] | None = None) -> bool:
    """True when ``candidate`` (everything to be shown so far) survives LIVE's text checks."""
    text = candidate or ""
    if not text.strip():
        return True
    from app.services.action_availability_honesty import answer_claims_action_missing
    from app.services.offered_action_continuation import claims_future_action
    from app.services.response_composer import looks_like_raw_backend
    from app.services.unified_turn_connector_grounding import (
        unified_live_message_claims_false_disconnect,
    )
    from app.services.user_facing_copy_guard import finalize_user_facing_message

    if looks_like_raw_backend(text):
        return False
    try:
        if _squash(finalize_user_facing_message(text, context="typed_live_stream")) != _squash(
            text
        ):
            return False
    except Exception:  # noqa: BLE001 - finalize refusing the text is a failed check
        return False
    if claims_future_action(text):
        return False
    if unified_live_message_claims_false_disconnect(text, connected_integrations):
        return False
    if answer_claims_action_missing(text):
        return False
    return True


class TypedLiveRelease:
    """Turns model deltas into checked units; nothing unchecked is released."""

    def __init__(self, *, connected_integrations: list[str] | None = None) -> None:
        self._connected = list(connected_integrations or [])
        self._buffer = ""
        self.released = ""
        self.stopped = False
        self.tool_round = False

    def feed(self, delta: str) -> str:
        """Add model text; return the newly releasable text ("" when none)."""
        if not delta:
            return ""
        self._buffer += delta
        if self.stopped:
            return ""
        cut = 0
        for match in _UNIT_BOUNDARY.finditer(self._buffer):
            cut = match.end()
        if not cut:
            return ""
        ready, self._buffer = self._buffer[:cut], self._buffer[cut:]
        out = ""
        for match in re.finditer(r".*?(?:[.!?][\"')\]]*[ \t]+|\n+)", ready, flags=re.S):
            unit = match.group(0)
            if not self.released and not out:
                unit = unit.lstrip()
            if not unit:
                continue
            if not reply_unit_ok(self.released + out + unit, connected_integrations=self._connected):
                self.stopped = True
                break
            out += unit
        self.released += out
        return out

    def on_tool_call(self) -> None:
        """The model turned to a tool: what was released is a preamble at most."""
        self.tool_round = True
        self.stopped = True


def remainder_after(final: str, released: str) -> str | None:
    """The part of ``final`` after ``released``, ignoring whitespace differences.

    None when ``final`` does not begin with what was released.
    """
    i = 0
    for ch in released or "":
        if ch.isspace():
            continue
        while i < len(final) and final[i].isspace():
            i += 1
        if i >= len(final) or final[i] != ch:
            return None
        i += 1
    rest = final[i:]
    already = len(released) - len(released.rstrip())
    lead = len(rest) - len(rest.lstrip())
    return rest[min(lead, already) :]


def reconcile_final(released: str, final: str) -> tuple[str, str]:
    """What to send after ``released`` and the turn's full text, given LIVE's final message.

    When the final message still begins with what was shown, only the rest is
    sent and the full text is the final message. When LIVE rewrote it (an
    offer to check, an honesty rewrite), what was shown stays and the final
    message follows as a new paragraph unless it repeats what was shown.
    """
    shown = (released or "").rstrip()
    final_text = (final or "").strip()
    if not final_text:
        return "", shown
    rest = remainder_after(final_text, released or "")
    if rest is not None:
        return rest, final_text
    if _squash(final_text) in _squash(shown):
        return "", shown
    return f"\n\n{final_text}", f"{shown}\n\n{final_text}"
