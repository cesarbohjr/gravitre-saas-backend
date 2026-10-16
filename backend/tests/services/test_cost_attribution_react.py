"""ReAct engine binds run/turn attribution without leaking across calls."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.operators.react_engine import ReActEngine
from app.services.cost_attribution import attribution_fields
from app.services.tool_types import ToolContext


@pytest.mark.asyncio
async def test_run_streaming_sets_turn_and_run_attribution():
    engine = ReActEngine(settings=Settings())
    ctx = ToolContext(
        settings=Settings(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        turn_id="turn-a",
        run_id="run-a",
    )
    seen: list[dict[str, str]] = []

    async def fake_loop(**_kwargs):
        seen.append(dict(attribution_fields()))
        from app.operators.stream_events import ReActStreamEvent
        from app.operators.react_engine import ReActResult, ReActStatus

        yield ReActStreamEvent(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="ok"),
        )

    with patch.object(engine, "_react_loop", fake_loop):
        async for _ in engine.run_streaming(ctx=ctx, task="hello"):
            pass

    assert seen == [{"run_id": "run-a", "turn_id": "turn-a"}]
    assert attribution_fields() == {}


@pytest.mark.asyncio
async def test_run_clears_turn_attribution_after_completion():
    engine = ReActEngine(settings=Settings())
    ctx = ToolContext(
        settings=Settings(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        turn_id="turn-b",
    )

    async def fake_loop(**_kwargs):
        from app.operators.stream_events import ReActStreamEvent
        from app.operators.react_engine import ReActResult, ReActStatus

        yield ReActStreamEvent(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer="ok"),
        )

    with patch.object(engine, "_react_loop", fake_loop):
        await engine.run(ctx=ctx, task="hello")

    assert attribution_fields() == {}
