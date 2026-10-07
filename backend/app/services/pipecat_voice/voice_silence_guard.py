"""Dead-air guard for one slow tool call inside a spoken turn.

The kernel's event stream goes quiet while a tool runs: nothing arrives
between ``tool-input-available`` and ``tool-output-available``. Tool-start
narration covers the first moment, but a single slow call (a big CRM search,
a connector write) can leave the caller in silence for many seconds, which on
a phone line reads as a dropped call.

``with_silence_ticks`` wraps the event stream and yields ``SILENCE_TICK``
whenever no event has arrived for ``interval_s`` seconds, without cancelling
the pending read. The turn loop decides what a tick means; it only speaks
when a real tool call is still open (see ``narrate_tool_still_running``), so
the guard never invents progress.
"""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

DEFAULT_SLOW_TOOL_NOTICE_SECONDS = 4.0
# After the first notice, repeat at most this many times, spaced further apart.
MAX_SLOW_TOOL_NOTICES_PER_CALL = 3
REPEAT_NOTICE_MULTIPLIER = 3.0


class _SilenceTick:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "SILENCE_TICK"


SILENCE_TICK = _SilenceTick()


def slow_tool_notice_seconds(settings: Any) -> float:
    """Seconds of silence during an open tool call before a spoken notice (0 disables)."""
    raw = getattr(settings, "voice_slow_tool_notice_seconds", None)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return DEFAULT_SLOW_TOOL_NOTICE_SECONDS
    return max(0.0, float(raw))


async def with_silence_ticks(source: AsyncIterator[Any], *, interval_s: float) -> AsyncIterator[Any]:
    """Yield every event from ``source``, plus ``SILENCE_TICK`` after each quiet interval."""
    it = source.__aiter__()
    if interval_s <= 0:
        async for event in it:
            yield event
        return
    pending: asyncio.Future[Any] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(it.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=interval_s)
            if not done:
                yield SILENCE_TICK
                continue
            finished, pending = pending, None
            try:
                event = finished.result()
            except StopAsyncIteration:
                return
            yield event
    finally:
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(BaseException):
                await pending
        aclose = getattr(source, "aclose", None)
        if aclose is not None:
            with contextlib.suppress(Exception):
                await aclose()


class SlowToolNotices:
    """Decide, per tick, whether an open tool call has earned a spoken notice."""

    def __init__(self, interval_s: float) -> None:
        self._interval_s = interval_s
        self._said: dict[str, tuple[int, float]] = {}

    def due(
        self,
        open_calls: dict[str, float],
        tool_names: dict[str, str],
        *,
        now: float,
        skip: Any = None,
    ) -> tuple[str, bool] | None:
        """Return ``(tool_name, is_repeat)`` for the oldest call owed a notice, else ``None``."""
        if self._interval_s <= 0:
            return None
        for call_id, started_at in sorted(open_calls.items(), key=lambda item: item[1]):
            tool_name = tool_names.get(call_id, "")
            if not tool_name or (skip is not None and skip(tool_name)):
                continue
            count, last_at = self._said.get(call_id, (0, started_at))
            if count >= MAX_SLOW_TOOL_NOTICES_PER_CALL:
                continue
            gap = self._interval_s if count == 0 else self._interval_s * REPEAT_NOTICE_MULTIPLIER
            if now - last_at < gap:
                continue
            self._said[call_id] = (count + 1, now)
            return tool_name, count > 0
        return None
