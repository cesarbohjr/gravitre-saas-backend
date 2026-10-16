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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

from app.core.logging import get_logger

logger = get_logger(__name__)

_org_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("model_call_org_id", default=None)
_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("cost_run_id", default=None)
_turn_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("cost_turn_id", default=None)
ATTRIBUTION_KEYS = ("run_id", "turn_id")


@dataclass(frozen=True)
class MeasuredModelCall:
    id: str
    org_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    created_at: datetime | None = None


@dataclass
class ModelCallCapture:
    """Request-local evidence for billing, shared across streaming child tasks."""

    org_id: str
    calls: list[MeasuredModelCall] = field(default_factory=list)
    _seen: set[str] = field(default_factory=set)

    def add(self, call: MeasuredModelCall) -> None:
        if call.org_id != self.org_id or call.id in self._seen:
            return
        self._seen.add(call.id)
        self.calls.append(call)


_model_call_capture: contextvars.ContextVar[ModelCallCapture | None] = contextvars.ContextVar(
    "model_call_capture", default=None,
)


@dataclass(frozen=True)
class AssistantBillingContract:
    org_id: str
    included: int
    environment: str = "production"


_assistant_billing_contract: contextvars.ContextVar[AssistantBillingContract | None] = contextvars.ContextVar(
    "assistant_billing_contract", default=None,
)


@contextmanager
def assistant_billing_contract(contract: AssistantBillingContract | None) -> Iterator[None]:
    token = _assistant_billing_contract.set(contract)
    try:
        yield
    finally:
        _assistant_billing_contract.reset(token)


@contextmanager
def capture_model_calls(capture: ModelCallCapture) -> Iterator[None]:
    token = _model_call_capture.set(capture)
    try:
        yield
    finally:
        _model_call_capture.reset(token)


def record_measured_model_call(call: MeasuredModelCall) -> None:
    capture = _model_call_capture.get()
    if capture is not None:
        capture.add(call)


@contextmanager
def attribution(*, run_id: str | None = None, turn_id: str | None = None, org_id: str | None = None) -> Iterator[None]:
    tokens = []
    if org_id:
        tokens.append((_org_id, _org_id.set(str(org_id))))
    if run_id:
        tokens.append((_run_id, _run_id.set(str(run_id))))
    if turn_id:
        tokens.append((_turn_id, _turn_id.set(str(turn_id))))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def current_model_org_id() -> str | None:
    return _org_id.get()


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


def insert_model_call(client: Any, row: dict[str, Any], *, billable: bool = True) -> Any:
    """Insert a model_calls row with attribution; fall back to the bare row."""
    full = {**row, **{k: v for k, v in attribution_fields().items() if k not in row}}
    contract = _assistant_billing_contract.get()
    recoverable = contract is not None and billable and row.get("task_type") != "embedding"
    if recoverable:
        if str(row.get("org_id")) != contract.org_id:
            raise ValueError("Assistant billing contract org mismatch")
        if not str(full.get("turn_id") or "").startswith("assistant:"):
            raise ValueError("Assistant billing contract turn mismatch")
        from app.billing.service import compute_ai_credits

        full.update({
            "billing_credits": compute_ai_credits(
                int(row.get("input_tokens") or 0), int(row.get("output_tokens") or 0),
                row.get("model_name"),
            ),
            "billing_included": contract.included,
            "billing_environment": contract.environment,
        })
    try:
        return client.table("model_calls").insert(full).execute()
    except Exception as exc:  # noqa: BLE001
        # A missing recovery column is a deployment error. Never strip the
        # billing contract and turn a recoverable call into an untracked one.
        if recoverable:
            raise
        if full == row or not _missing_column(exc):
            raise
        logger.info("model_calls_attribution_columns_missing; writing row without run/turn id")
        bare = {k: v for k, v in full.items() if k not in ATTRIBUTION_KEYS}
        return client.table("model_calls").insert(bare).execute()
