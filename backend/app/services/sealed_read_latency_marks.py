"""P2 — sealed READ waterfall marks (investigation contract)."""
from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any

P2_MARKS = (
    "understanding",
    "memory.recalled",
    "preflight",
    "provider",
    "compose_canned",
    "first_sse",
)

_t0: ContextVar[float | None] = ContextVar("sealed_read_p2_t0", default=None)
_marks: ContextVar[dict[str, int] | None] = ContextVar("sealed_read_p2_marks", default=None)


def begin_p2_marks(t0: float | None = None) -> dict[str, int]:
    bag: dict[str, int] = {}
    _marks.set(bag)
    _t0.set(float(t0 if t0 is not None else time.perf_counter()))
    return bag


def record_p2_mark(name: str, ms: int | None = None) -> None:
    bag = _marks.get()
    if bag is None:
        bag = {}
        _marks.set(bag)
    if ms is None:
        start = _t0.get()
        if start is None:
            return
        ms = int((time.perf_counter() - start) * 1000)
    bag[str(name)] = int(ms)


def snapshot_p2_marks() -> dict[str, int]:
    bag = _marks.get()
    return dict(bag) if isinstance(bag, dict) else {}


def merge_p2_into(checkpoints: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(checkpoints or {})
    out.update(snapshot_p2_marks())
    return out
