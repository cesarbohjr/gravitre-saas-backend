"""Regression guard: POST /api/voice/turn-taking/event must stay `async def`.

Perf fix (2026-09-07). Root cause of the live "1-6s per call" report on the
legacy HTTP duplex path: this endpoint was a *sync* `def`, so every call was
dispatched through Starlette's `run_in_threadpool` (anyio's worker-thread
pool) even though its body does zero I/O (pure in-memory
`TurnTakingState` manipulation). Deepgram fires interim STT events every
~100-300ms and the frontend does not serialize `postTurnTakingEvent` calls
(see `apps/web/hooks/use-voice-duplex-session.ts`), so a real voice session
produces bursts of same-user concurrent calls to this endpoint. Under such a
burst, N concurrent sync dispatches contend for OS worker threads + the GIL
at the same time, adding a near-uniform, multi-hundred-ms-to-1s+ tax to
*every* call in the burst -- confirmed live: 15 concurrent calls each
measured ~1.3s even though `get_org_context` itself resolved in 0-125ms for
every one of those same calls (Railway logs), while 15 *sequential* calls to
the same endpoint measured p50 143.7ms / p95 185.4ms.

Fix: mark the handler `async def`. There is nothing to await inside besides
the dependencies FastAPI already resolves on the event loop directly
(`get_current_user`, `get_org_context` are both already `async def`); the
body itself is pure computation and now runs inline on the event loop with
zero thread-pool round-trip.

Mutation-proof: this test fails if a future edit reverts the handler to a
sync `def` (which would silently reintroduce the thread-pool tax under
concurrent load without changing any single-call, non-concurrent test
outcome -- the exact way this regression class hid before).
"""
from __future__ import annotations

import inspect

from app.routers import voice as voice_router


def test_post_turn_taking_event_is_async_def():
    assert inspect.iscoroutinefunction(voice_router.post_turn_taking_event), (
        "post_turn_taking_event must be `async def`, not a sync `def` -- a sync "
        "def here gets dispatched through Starlette's run_in_threadpool on every "
        "call, which is the confirmed live root cause of ~1.3s latency under "
        "same-user concurrent VAD-event bursts (vs ~150ms sequential p50). See "
        "module docstring for the full live-evidence trail."
    )


def test_post_turn_taking_event_body_has_no_blocking_calls():
    """Structural guard: since this handler now runs directly on the event
    loop (no thread-pool isolation), its body must never gain a genuinely
    blocking call (sync network/DB/file I/O) -- that would stall the whole
    event loop for every concurrent voice session, not just the caller.
    """
    src = inspect.getsource(voice_router.post_turn_taking_event)
    forbidden_markers = (
        "requests.",
        "httpx.Client(",
        "supabase.create_client(",
        "time.sleep(",
        ".execute()",  # common supabase-py sync call-site shape
    )
    for marker in forbidden_markers:
        assert marker not in src, (
            f"post_turn_taking_event body contains a likely-blocking call "
            f"({marker!r}); this handler runs directly on the event loop as "
            f"an async def with no thread-pool isolation, so blocking I/O here "
            f"would stall every other concurrent request on this worker."
        )
