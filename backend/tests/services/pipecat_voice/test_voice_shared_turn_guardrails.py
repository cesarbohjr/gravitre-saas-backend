"""Voice runs the same turn preparation as text chat.

Single-engine parity (2026-10-07): Pipecat voice used to skip the canonical
assistant system prompt, the prompt-injection note and the model guardrails
(kill switch, rate limit, budget, moderation, model policy) that text chat
runs. These tests pin that voice now passes text's prompt into the shared
brain, speaks a guardrail refusal instead of answering, and shows nothing
before the guard has passed even though the guard runs concurrently.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.ai_guardrails import AIBudgetExceededError, AIContentFlaggedError, AIRateLimitError
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.shared_turn_preparation import (
    SPOKEN_GUARDRAIL_MESSAGES,
    TurnGuardrailBlocked,
    classify_guardrail_error,
)

ORG = "00000000-0000-4000-8000-000000000001"
USER = "00000000-0000-4000-8000-000000000002"


class _Context:
    def get_messages(self) -> list[dict[str, Any]]:
        return [{"role": "user", "content": "Help me generate 150 qualified leads per month."}]


def _drive(guard: Any) -> dict[str, Any]:
    seen: dict[str, Any] = {"kwargs": None, "display": [], "spoken": [], "narration": [], "closed": False}

    async def _fake_stream(**kwargs: Any):
        seen["kwargs"] = kwargs
        try:
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Here is the plan. "})
            yield AssistantStreamComplete(full_content="Here is the plan.", tool_results=[], react_result=None, model="t")
        except GeneratorExit:
            seen["closed"] = True
            raise

    fake_intelligence = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)})()
    service = GravitreCognitiveLLMService(app_settings=object(), org_id=ORG, user_id=USER)

    async def _push_frame(frame: Any, *_a: Any, **_kw: Any) -> None:
        message = getattr(frame, "message", None)
        if isinstance(message, dict) and message.get("type") == "assistant_text":
            seen["display"].append(str(message.get("delta") or ""))

    async def _push_llm_text(text: str) -> None:
        seen["spoken"].append(text)

    async def _narrate(text: str, kind: str = "progress") -> None:
        seen["narration"].append(text)

    service.push_frame = AsyncMock(side_effect=_push_frame)
    service._push_llm_text = AsyncMock(side_effect=_push_llm_text)
    service._speak_narration = AsyncMock(side_effect=_narrate)
    with (
        patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=fake_intelligence),
        patch("app.services.shared_turn_preparation.build_turn_system_prompt", return_value="CANONICAL PROMPT"),
        patch("app.services.shared_turn_preparation.guard_spoken_turn", new=guard),
    ):
        asyncio.run(service._run_gravitre_turn(_Context()))
    return seen


def test_voice_passes_text_chats_canonical_prompt_to_the_shared_brain() -> None:
    seen = _drive(AsyncMock(return_value=None))
    # Text chat's prompt, plus the one voice note that keeps context background.
    from app.services.pipecat_voice.cognitive_llm import VOICE_NO_VOLUNTEERED_DATA_NOTE

    assert seen["kwargs"]["assistant_base_prompt"] == f"CANONICAL PROMPT\n\n{VOICE_NO_VOLUNTEERED_DATA_NOTE}"
    assert seen["kwargs"]["spoken_mode"] is True
    assert "Here is the plan" in "".join(seen["display"])


def test_guardrail_refusal_is_spoken_and_nothing_else_reaches_the_user() -> None:
    seen = _drive(AsyncMock(side_effect=TurnGuardrailBlocked("budget_exceeded")))
    assert seen["narration"] == [SPOKEN_GUARDRAIL_MESSAGES["budget_exceeded"]]
    assert seen["display"] == [] and seen["spoken"] == []
    assert seen["closed"] is True


def test_guard_runs_concurrently_but_gates_the_first_output() -> None:
    order: list[str] = []

    async def _slow_guard(*_a: Any, **_kw: Any) -> None:
        order.append("guard-start")
        await asyncio.sleep(0.05)
        order.append("guard-pass")

    seen = _drive(_slow_guard)
    assert order == ["guard-start", "guard-pass"]
    assert seen["kwargs"] is not None
    assert "Here is the plan" in "".join(seen["display"])


def test_guardrail_errors_map_to_the_same_kinds_text_chat_reports() -> None:
    assert classify_guardrail_error(AIRateLimitError()) == "rate_limited"
    assert classify_guardrail_error(AIBudgetExceededError()) == "budget_exceeded"
    assert classify_guardrail_error(AIContentFlaggedError("x")) == "content_flagged"
    assert classify_guardrail_error(RuntimeError("db down")) is None
