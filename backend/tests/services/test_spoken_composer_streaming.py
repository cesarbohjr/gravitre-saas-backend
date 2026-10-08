"""Spoken Composer replies stream sentence by sentence, still fully checked.

The Composer LLM call (`_llm_compose`, a non-streamed `complete()`) was the
main call of spoken deep turns, so first audio waited for the whole reply.
`stream_compose_reply_events` streams it through the router's streaming path
and releases a sentence only after the whole-text checks leave it unchanged
and output moderation passes for it.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import response_composer as rc
from app.services.ai_guardrails import AIContentFlaggedError
from app.services.model_router import ModelStreamEvent


class _Router:
    """prepare_stream/stream double; ``gate`` holds generation after the first chunk."""

    def __init__(self, pieces: list[str], *, gate: asyncio.Event | None = None, prepare_error=None, end_error=None):
        self.pieces = pieces
        self.gate = gate
        self.prepare_error = prepare_error
        self.end_error = end_error
        self._openai = object()
        self.finished = False

    async def prepare_stream(self, *_a, **_k):
        if self.prepare_error is not None:
            raise self.prepare_error
        return SimpleNamespace()

    async def stream(self, _prepared):
        for i, piece in enumerate(self.pieces):
            if self.gate is not None and i == 1:
                await self.gate.wait()
            yield ModelStreamEvent(delta=piece)
        if self.end_error is not None:
            raise self.end_error
        self.finished = True
        yield ModelStreamEvent(response=SimpleNamespace(content="".join(self.pieces)))


async def _collect(router: _Router, *, kind: str = "clarify", envelope=None, draft="Who should get it?", on_event=None):
    reply = rc.StreamedComposerReply()
    events = []
    with patch("app.services.model_router.get_model_router", return_value=router), patch(
        "app.services.response_composer._emit_composer_audit"
    ):
        async for event in rc.stream_compose_reply_events(
            envelope
            if envelope is not None
            else {"success": False, "error_code": "validation_error", "data": {"text": draft}},
            result=reply,
            kind=kind,
            draft=draft,
            user_message="send an email to acme about the renewal",
            settings=SimpleNamespace(disable_ai=False, ai_moderation_enabled=False),
            org_id="org-1",
        ):
            events.append(event)
            if on_event is not None:
                on_event(event)
    return reply, events


def _deltas(events) -> list[str]:
    return [str((e.payload or {}).get("delta") or "") for e in events if e.sse_type == "text-delta"]


@pytest.mark.asyncio
async def test_first_sentence_is_released_before_the_model_finishes() -> None:
    gate = asyncio.Event()
    router = _Router(["Who should I send it to? ", "I can draft it ", "once I know."], gate=gate)
    before_finish: list[str] = []

    def on_event(event) -> None:
        if event.sse_type == "text-delta" and not router.finished:
            before_finish.append(str(event.payload.get("delta")))
            gate.set()

    reply, events = await asyncio.wait_for(_collect(router, on_event=on_event), timeout=5)
    assert before_finish == ["Who should I send it to? "]
    assert "".join(_deltas(events)) == "Who should I send it to? I can draft it once I know."
    assert reply.text == "Who should I send it to? I can draft it once I know."
    assert reply.streamed is True
    assert events[0].sse_type == "text-start"
    assert events[-1].sse_type == "text-end"


@pytest.mark.asyncio
async def test_flagged_sentence_and_everything_after_it_never_reach_speech() -> None:
    router = _Router(["Fine first sentence. ", "Unsafe second sentence. ", "Third sentence."])

    async def moderate(text, *_a, **_k):
        if "Unsafe" in text:
            raise AIContentFlaggedError("flagged")

    with patch("app.services.ai_guardrails.moderate_output", AsyncMock(side_effect=moderate)):
        reply, events = await _collect(router)
    spoken = "".join(_deltas(events))
    assert "Unsafe" not in spoken
    assert "Third" not in spoken
    assert spoken == "Fine first sentence. "
    assert reply.text == "Fine first sentence."


@pytest.mark.asyncio
async def test_full_reply_flagged_by_router_output_moderation_releases_no_tail() -> None:
    gate = asyncio.Event()
    router = _Router(
        ["First sentence. ", "second part without end"], gate=gate, end_error=AIContentFlaggedError("flagged")
    )

    def on_event(event) -> None:
        if event.sse_type == "text-delta":
            gate.set()

    reply, events = await asyncio.wait_for(_collect(router, on_event=on_event), timeout=5)
    spoken = "".join(_deltas(events))
    assert spoken == "First sentence. "
    assert "second part" not in spoken
    assert reply.text == "First sentence."


@pytest.mark.asyncio
async def test_sentence_a_whole_text_check_would_rewrite_is_not_released() -> None:
    # A raw backend leak in the second sentence: the whole-text pipeline would
    # replace the reply, so the stream stops before that sentence.
    router = _Router(["Let me check that. ", "Traceback (most recent call last): boom. ", "More."])
    reply, events = await _collect(router)
    spoken = "".join(_deltas(events))
    assert "Traceback" not in spoken
    assert spoken == "Let me check that. "
    assert "Traceback" not in reply.text


@pytest.mark.asyncio
async def test_unchecked_completion_claim_is_held_back_for_consequential_success() -> None:
    # Success of a staged write with no verified execution: a completion claim
    # is rewritten by the whole-text check, so it must never be spoken.
    envelope = {"success": True, "canonical_lifecycle": "AWAITING_APPROVAL", "data": {"text": "draft"}}
    router = _Router(["I sent the email to Acme. ", "Anything else?"])
    reply, events = await _collect(router, kind="success", envelope=envelope, draft="")
    spoken = "".join(_deltas(events))
    assert "I sent the email" not in spoken


@pytest.mark.asyncio
async def test_input_guardrail_refusal_falls_back_like_the_non_streamed_path() -> None:
    router = _Router(["unused"], prepare_error=AIContentFlaggedError("input flagged"))
    reply, events = await _collect(router)
    assert reply.streamed is False
    assert "".join(_deltas(events)) == rc._fallback_text("clarify")
    assert reply.text == rc._fallback_text("clarify")


@pytest.mark.asyncio
async def test_outcomes_that_need_no_model_call_take_the_existing_path() -> None:
    router = _Router(["should not be used"])
    reply, events = await _collect(
        router,
        kind="success",
        envelope={"success": True, "data": {"text": "Acme is the priority this quarter."}},
        draft="Acme is the priority this quarter.",
    )
    assert reply.text == "Acme is the priority this quarter."
    assert "".join(_deltas(events)) == "Acme is the priority this quarter."
    assert router.finished is False


@pytest.mark.asyncio
async def test_existing_text_id_is_reused_and_left_open_when_asked() -> None:
    router = _Router(["One. ", "Two."])
    reply = rc.StreamedComposerReply()
    events = []
    with patch("app.services.model_router.get_model_router", return_value=router), patch(
        "app.services.response_composer._emit_composer_audit"
    ):
        async for event in rc.stream_compose_reply_events(
            {"success": False, "error_code": "validation_error", "data": {"text": "q"}},
            result=reply,
            kind="clarify",
            draft="q",
            settings=SimpleNamespace(disable_ai=False, ai_moderation_enabled=False),
            org_id="org-1",
            existing_text_id="t-1",
            close=False,
        ):
            events.append(event)
    assert all(e.sse_type == "text-delta" for e in events)
    assert reply.text_id == "t-1"
