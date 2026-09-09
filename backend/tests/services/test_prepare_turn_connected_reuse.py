"""prepare_assistant_turn must not re-resolve the connector list.

``list_connected_integrations`` defaults to ``force_live=True``, which skips the
connector snapshot cache and does one HTTP round trip per connected connector.
Called synchronously from a coroutine it blocked the event loop for 1,630ms on a
measured spoken voice turn, stalling audio for every concurrent session, while
``agent_intelligence`` had already resolved the same list off-thread earlier in
the same turn.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from app.services.intelligence_orchestrator import IntelligenceOrchestrator

_ORCHESTRATOR_SRC = Path(inspect.getfile(IntelligenceOrchestrator)).read_text(
    encoding="utf-8"
)


class TestCallerSuppliedConnectorsWin:
    def test_signature_accepts_connected_integrations(self) -> None:
        params = inspect.signature(
            IntelligenceOrchestrator.prepare_assistant_turn
        ).parameters
        assert "connected_integrations" in params
        assert params["connected_integrations"].default is None

    def test_supplied_list_short_circuits_the_live_call(self) -> None:
        src = _ORCHESTRATOR_SRC
        guard = src.index("if connected_integrations is not None:")
        live_call = src.index("self._registry.list_connected_integrations")
        # The live lookup must sit inside the else branch, after the guard.
        assert guard < live_call

    def test_fallback_runs_off_the_event_loop(self) -> None:
        src = _ORCHESTRATOR_SRC
        live_call = src.index("self._registry.list_connected_integrations")
        window = src[max(0, live_call - 200) : live_call]
        # run_io replaced to_thread here: the default executor is ~6 workers on a
        # small container and shared process-wide, so it queued these reads.
        assert "run_io" in window, (
            "a synchronous per-connector HTTP walk must not run on the event loop"
        )


class TestAgentIntelligencePassesItThrough:
    def test_caller_forwards_the_early_list(self) -> None:
        import app.operators.agent_intelligence as ai

        src = Path(inspect.getfile(ai)).read_text(encoding="utf-8")
        call = src.index("prepare_assistant_turn(")
        # The call spans to its closing paren; the forwarded kwarg must be inside.
        window = src[call : call + 1600]
        assert "connected_integrations=list(connected_early or [])" in window


class TestBreakdownStaysObservable:
    def test_connected_stage_is_still_timed(self) -> None:
        # The checkpoint that exposed the 1,630ms must survive the fix, so a
        # regression shows up in prepare_assistant_turn_breakdown_ms.
        assert '_mark("connected_integrations")' in _ORCHESTRATOR_SRC
