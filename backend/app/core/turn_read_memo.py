"""Per-turn memo for org configuration reads that one chat turn repeats.

A single assistant turn read the same org rows several times before the model
was called: the enabled MCP tool list four to five times, the intelligence
engine settings row three times. Each was a Supabase round trip on the critical
path. Within the preparation phase of one turn those rows do not change (the
turn itself writes none of them), so the first read is reused.

Scope is deliberately narrow:

* ``begin_turn_memo()`` starts a fresh memo at the start of a turn
  (``AgentIntelligence.execute_task_streaming``); ``end_turn_memo()`` drops it
  when the turn reaches the model/tool loop, so nothing after a tool could have
  run is ever served from it. A memo older than ``MAX_AGE_S`` is ignored as a
  backstop.
* It lives in a ``ContextVar``: tasks the turn starts share it, other requests
  never see it, and a worker thread without the turn's context reads live.
* Only the process-wide production client is memoized
  (``app.core.db.is_shared_service_client``); tests that pass mock clients
  always read live, so their call counts are unchanged.
* Callers get a deep copy, so mutating a result cannot change what the next
  reader sees.
"""
from __future__ import annotations

import asyncio
import copy
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, TypeVar

_T = TypeVar("_T")

MAX_AGE_S = 30.0


class _TurnMemo:
    __slots__ = ("started", "values")

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.values: dict[tuple[Any, ...], Any] = {}


_CURRENT: ContextVar[_TurnMemo | None] = ContextVar("gravitre_turn_read_memo", default=None)


def begin_turn_memo() -> None:
    _CURRENT.set(_TurnMemo())


def end_turn_memo() -> None:
    _CURRENT.set(None)


def _active_memo(client: Any) -> _TurnMemo | None:
    memo = _CURRENT.get()
    if memo is None or time.monotonic() - memo.started > MAX_AGE_S:
        return None
    from app.core.db import is_shared_service_client

    try:
        if not is_shared_service_client(client):
            return None
    except Exception:  # noqa: BLE001
        return None
    return memo


async def memo_read_async(
    key: tuple[Any, ...],
    client: Any,
    load: Callable[[], Awaitable[_T]],
) -> _T:
    """``await load()`` once per turn for ``key``; concurrent readers share one read."""
    memo = _active_memo(client)
    if memo is None:
        return await load()
    entry = memo.values.get(key)
    if entry is None:
        entry = asyncio.ensure_future(load())
        memo.values[key] = entry
        entry.add_done_callback(lambda f: f.cancelled() or f.exception())
    try:
        value = await asyncio.shield(entry)
    except BaseException:
        # A failed read is not remembered: the next reader tries again.
        if memo.values.get(key) is entry:
            memo.values.pop(key, None)
        raise
    return copy.deepcopy(value)
