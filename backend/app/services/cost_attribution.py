"""Attribute model calls to the workflow run or chat turn that made them.

A context variable carries the ids; ``execute_workflow_steps`` sets the run id
for everything it runs (contextvars follow ``asyncio.to_thread``), and model call
writers merge ``attribution_fields()`` into their ``model_calls`` row.

``insert_model_call`` is expand-safe: if the database does not have the columns
yet (migration 20261013080000 not applied) the row is written without them, so
cost is never lost because of attribution.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Iterator

from app.core.logging import get_logger

logger = get_logger(__name__)

_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("cost_run_id", default=None)
_turn_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("cost_turn_id", default=None)
ATTRIBUTION_KEYS = ("run_id", "turn_id")


@contextmanager
def attribution(*, run_id: str | None = None, turn_id: str | None = None) -> Iterator[None]:
    tokens = []
    if run_id:
        tokens.append((_run_id, _run_id.set(str(run_id))))
    if turn_id:
        tokens.append((_turn_id, _turn_id.set(str(turn_id))))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def attribution_fields() -> dict[str, str]:
    out: dict[str, str] = {}
    if _run_id.get():
        out["run_id"] = str(_run_id.get())
    if _turn_id.get():
        out["turn_id"] = str(_turn_id.get())
    return out


def bind_turn_attribution(turn_id: str | None) -> contextvars.Token | None:
    """Set turn_id for model_calls attribution for the rest of this async task."""
    if not turn_id:
        return None
    return _turn_id.set(str(turn_id))


def reset_turn_attribution(token: contextvars.Token | None) -> None:
    if token is not None:
        _turn_id.reset(token)


def _missing_column(exc: Exception) -> bool:
    text = str(exc)
    return "PGRST204" in text or "42703" in text or ("column" in text and any(k in text for k in ATTRIBUTION_KEYS))


def insert_model_call(client: Any, row: dict[str, Any]) -> Any:
    """Insert a model_calls row with attribution; fall back to the bare row."""
    full = {**row, **{k: v for k, v in attribution_fields().items() if k not in row}}
    try:
        return client.table("model_calls").insert(full).execute()
    except Exception as exc:  # noqa: BLE001
        if full == row or not _missing_column(exc):
            raise
        logger.info("model_calls_attribution_columns_missing; writing row without run/turn id")
        bare = {k: v for k, v in full.items() if k not in ATTRIBUTION_KEYS}
        return client.table("model_calls").insert(bare).execute()
