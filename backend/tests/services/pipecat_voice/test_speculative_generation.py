"""Voice-SLO follow-up (2026-09-05): SpeculativeGenerationCoordinator.

Pure-asyncio unit tests, no Pipecat/FrameProcessor dependency — `create_task`
is just `asyncio.ensure_future` here, matching how a real FrameProcessor's
`self.create_task` behaves for scheduling purposes.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    start_speculative_run,
)


def _create_task(coro):
    return asyncio.ensure_future(coro)


async def _events(*items):
    for item in items:
        yield item


class TestStartAndAdoptExactMatch:
    @pytest.mark.asyncio
    async def test_adopt_returns_the_run_and_replays_all_buffered_events(self):
        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="what is two plus two",
            runner=lambda: _events("a", "b", "c"),
            create_task=_create_task,
        )
        coordinator.set_run(run)
        await run.task  # let the producer finish buffering into the queue

        adopted = coordinator.adopt("what is two plus two")
        assert adopted is not None
        collected = [item async for item in adopted.events()]
        assert collected == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_adopt_is_case_and_whitespace_insensitive(self):
        """MUTATION PROOF: trivial STT capitalization/spacing differences
        between the interim partial and the final transcript must not block
        an otherwise-identical adoption — revert to a raw `==` and this
        fails.
        """
        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="  What Is Two Plus Two  ",
            runner=lambda: _events("ok"),
            create_task=_create_task,
        )
        coordinator.set_run(run)
        await run.task

        adopted = coordinator.adopt("what is two plus two")
        assert adopted is not None

    @pytest.mark.asyncio
    async def test_adopt_drains_a_still_running_producer_not_just_a_snapshot(self):
        """A run adopted before its producer finishes must still see every
        subsequently-produced event, not just whatever had already landed in
        the queue at adopt() time.
        """
        coordinator = SpeculativeGenerationCoordinator()
        release = asyncio.Event()

        async def _slow_runner():
            yield "first"
            await release.wait()
            yield "second"

        run = start_speculative_run(text="hi there", runner=_slow_runner, create_task=_create_task)
        coordinator.set_run(run)
        await asyncio.sleep(0.01)  # let "first" land in the queue

        adopted = coordinator.adopt("hi there")
        assert adopted is not None

        collected: list[str] = []

        async def _drain():
            async for item in adopted.events():
                collected.append(item)

        drain_task = asyncio.ensure_future(_drain())
        await asyncio.sleep(0.01)
        assert collected == ["first"]
        release.set()
        await drain_task
        assert collected == ["first", "second"]


class TestAdoptMismatchFallsBackSafely:
    @pytest.mark.asyncio
    async def test_mismatched_final_text_returns_none_and_cancels_the_run(self):
        """MUTATION PROOF: the coordinator must never hand back a run whose
        speculative text differs from what the user actually, confirmedly
        said — a caller that ignores the None and uses the run anyway would
        answer the wrong question. Also verifies the stale, wrong-guess run
        is cancelled rather than left running to waste compute/cost.
        """
        coordinator = SpeculativeGenerationCoordinator()
        started = asyncio.Event()

        async def _runner():
            started.set()
            await asyncio.sleep(10)
            yield "never"

        run = start_speculative_run(text="email sarah", runner=_runner, create_task=_create_task)
        coordinator.set_run(run)
        await started.wait()

        adopted = coordinator.adopt("email mike")
        assert adopted is None
        await asyncio.sleep(0.01)
        assert run.task.cancelled() or run.task.done()

    @pytest.mark.asyncio
    async def test_no_pending_run_returns_none(self):
        coordinator = SpeculativeGenerationCoordinator()
        assert coordinator.adopt("anything") is None

    @pytest.mark.asyncio
    async def test_a_run_already_adopted_once_is_never_returned_again(self):
        """MUTATION PROOF: without the `consumed` guard, two confirmed turns
        in a row with the same accidental text collision could double-drain
        (or double-adopt) the same run."""
        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(text="ok", runner=lambda: _events("x"), create_task=_create_task)
        coordinator.set_run(run)
        await run.task

        first = coordinator.adopt("ok")
        assert first is not None
        second = coordinator.adopt("ok")
        assert second is None


class TestCancelAndRestart:
    @pytest.mark.asyncio
    async def test_set_run_cancels_the_previous_pending_run(self):
        """MUTATION PROOF: starting a second speculative run (a new,
        materially-different probable-EOT) must cancel the first — two
        concurrent speculative turns running the full governed pipeline at
        once is exactly the risk this coordinator exists to prevent.
        """
        coordinator = SpeculativeGenerationCoordinator()
        started = asyncio.Event()

        async def _slow_runner():
            started.set()
            await asyncio.sleep(10)
            yield "never"

        first_run = start_speculative_run(text="email sarah", runner=_slow_runner, create_task=_create_task)
        coordinator.set_run(first_run)
        await started.wait()

        second_run = start_speculative_run(text="email mike", runner=lambda: _events("ok"), create_task=_create_task)
        coordinator.set_run(second_run)

        await asyncio.sleep(0.01)
        assert first_run.task.cancelled()

    @pytest.mark.asyncio
    async def test_explicit_cancel_clears_pending_run(self):
        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="hi", runner=lambda: _events("x"), create_task=_create_task
        )
        coordinator.set_run(run)
        assert coordinator.has_pending_run is True

        coordinator.cancel()

        assert coordinator.has_pending_run is False
        assert coordinator.adopt("hi") is None


class TestProducerErrorSurfacesThroughEvents:
    @pytest.mark.asyncio
    async def test_a_failing_runner_raises_when_drained_not_silently_swallowed(self):
        coordinator = SpeculativeGenerationCoordinator()

        async def _failing_runner():
            yield "partial"
            raise RuntimeError("upstream boom")

        run = start_speculative_run(text="hi", runner=_failing_runner, create_task=_create_task)
        coordinator.set_run(run)
        await run.task

        adopted = coordinator.adopt("hi")
        assert adopted is not None
        collected = []
        with pytest.raises(RuntimeError, match="upstream boom"):
            async for item in adopted.events():
                collected.append(item)
        assert collected == ["partial"]
