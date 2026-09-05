"""Genuine, cancelable speculative LLM generation on probable-EOT.

Voice-SLO follow-up (2026-09-05) — the highest-value item flagged as "not
built" in docs/delivery/voice-slo-parallelism-standard-2026-09-05.md: Phase 1
previously only did READ-ONLY cache warming (speculative_prefetch.py) on
partial transcripts. This module adds the other half — a real, cancelable
CognitiveTurnKernel reasoning call started on Deepgram Flux's own
ProposedUserStoppedSpeakingFrame ("probably done") signal, whose output is
either:

  - adopted at confirmed end-of-turn, when the final transcript matches the
    text the speculative run was launched with (exact, normalized match —
    a deliberate, conservative scoping choice: a close-but-not-exact match
    falls back to a fresh call rather than risk answering a slightly
    different question to save time), or
  - discarded (cancelled), when the user kept talking and the probable-EOT
    was wrong, or the final transcript doesn't match.

Ownership split, so this module never needs to know about AgentIntelligence,
Pipecat frame types, or write-governance policy:

  - speculative_prefetch.py (SpeculativePrefetchProcessor) decides WHEN to
    start a run (on ProposedUserStoppedSpeakingFrame) and WHETHER it is safe
    to do so at all (never for write-shaped text — same conservative gate
    already used for read-only prefetch), and supplies the `runner` closure
    (a zero-arg callable returning intelligence.execute_task_streaming(...)
    with the current partial as `query`).
  - cognitive_llm.py (GravitreCognitiveLLMService) calls `adopt()` at
    confirmed end-of-turn and, on a hit, drains the run's buffered/live
    events instead of calling execute_task_streaming() again — the actual
    latency win: any tokens the speculative run already produced before
    confirmation arrive instantly instead of waiting for a fresh call.

Task creation is handled by the caller via a `create_task` callable (Pipecat
FrameProcessor.create_task) so speculative work shares the exact same task
lifecycle/cleanup already used by SpeculativePrefetchProcessor's read-only
prefetch — no second task-management system.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Sentinel enqueued once a run's producer coroutine finishes (success or
# error already reported via a preceding BaseException item) so events()
# knows to stop iterating rather than blocking forever on an empty queue.
_DONE = object()


def _normalize_for_match(text: str) -> str:
    """Whitespace/case-insensitive comparison — Deepgram framing/capitalization
    can differ trivially between an interim partial and the final transcript
    without the underlying words actually differing.
    """
    return " ".join((text or "").strip().split()).casefold()


@dataclass
class SpeculativeGenerationRun:
    """One in-flight or completed speculative generation attempt.

    `text` is the (partial) transcript this run was launched with — the only
    thing `adopt()` ever compares against the final transcript.
    """

    text: str
    task: "asyncio.Task[None]"
    queue: "asyncio.Queue[Any]" = field(default_factory=asyncio.Queue)
    consumed: bool = False

    def matches(self, final_text: str) -> bool:
        return bool(final_text) and _normalize_for_match(self.text) == _normalize_for_match(final_text)

    def cancel(self) -> None:
        if not self.task.done():
            self.task.cancel()

    async def events(self) -> AsyncIterator[Any]:
        """Yield every event this run has produced (already-buffered ones
        first, then whatever the still-running producer adds) until the
        producer signals completion. Re-raises any exception the producer
        surfaced, matching the semantics of iterating the live generator
        directly (a fresh execute_task_streaming() call failing mid-stream
        looks identical to the caller either way).
        """
        while True:
            item = await self.queue.get()
            if item is _DONE:
                return
            if isinstance(item, BaseException):
                raise item
            yield item


async def _drive_into_queue(
    runner: Callable[[], AsyncIterator[Any]],
    queue: "asyncio.Queue[Any]",
) -> None:
    try:
        async for event in runner():
            await queue.put(event)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 — surfaced to the eventual consumer, not lost
        await queue.put(exc)
    finally:
        await queue.put(_DONE)


def start_speculative_run(
    *,
    text: str,
    runner: Callable[[], AsyncIterator[Any]],
    create_task: Callable[[Awaitable[None]], "asyncio.Task[None]"],
) -> SpeculativeGenerationRun:
    """Launch one speculative run. Caller is responsible for cancelling any
    prior run first (SpeculativeGenerationCoordinator.set_run does this).
    """
    queue: "asyncio.Queue[Any]" = asyncio.Queue()
    task = create_task(_drive_into_queue(runner, queue))
    return SpeculativeGenerationRun(text=text, task=task, queue=queue)


class SpeculativeGenerationCoordinator:
    """Owns at most one in-flight/pending speculative run per voice session.

    Shared (one instance) between SpeculativePrefetchProcessor and
    GravitreCognitiveLLMService via pipeline.py, so the run started by the
    former can be adopted by the latter.
    """

    def __init__(self) -> None:
        self._run: SpeculativeGenerationRun | None = None

    @property
    def has_pending_run(self) -> bool:
        return self._run is not None

    def cancel(self) -> None:
        """Cancel and discard any pending run — the probable-EOT was wrong
        (user kept talking) or a new turn boundary made it moot.
        """
        if self._run is not None:
            self._run.cancel()
            self._run = None

    def set_run(self, run: SpeculativeGenerationRun) -> None:
        """Replace the pending run, cancelling whatever was running before.

        Reuses the same cancel-then-restart pattern speculative_prefetch.py
        already applies to its own read-only prefetch task — no second,
        separate cancellation mechanism introduced for generation.
        """
        self.cancel()
        self._run = run

    def adopt(self, final_text: str) -> SpeculativeGenerationRun | None:
        """Return the pending run if its text matches `final_text`, else None
        (cancelling a non-matching pending run along the way — it will never
        be consumed now that the turn has been confirmed with different
        text). Idempotent: a run already consumed is never returned twice.
        """
        run = self._run
        self._run = None
        if run is None or run.consumed:
            return None
        if not run.matches(final_text):
            run.cancel()
            return None
        run.consumed = True
        return run
