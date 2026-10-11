"""Which approval a "yes" answers: an explicit contract, not the shape of the last sentence.

A staged write carries an approval identity (``approval_action_id``, minted by
``approval_action_binding.bind_plan_dict``). Every revision of the draft (a new
subject, message or recipient) mints a new one. A spoken or typed "yes" is an
answer to the version the user was shown or read, so the turn that carries it
binds that version here, and both the spoken-approval classifier and the write
claim refuse a pending write whose identity differs:

* the draft was revised after it was read back (another device, an older
  connection, a correction that landed first);
* the draft was cancelled and a new one staged since;
* no version was read back on this connection at all (reconnect during the
  readback): ``ExpectedApproval("")`` matches nothing, so the voice layer re-reads
  the current version first.

Unbound (no voice turn, text chat's Approve button) keeps the existing
behavior: the staged binding (``assert_plan_matches_binding``) still protects
the arguments.
"""
from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

#: Error code when a confirmation is for a different version than the staged one.
APPROVAL_REVISION_STALE = "APPROVAL_REVISION_STALE"

_AWAITING = frozenset({"awaiting_confirm", "awaiting_admin_approval", "awaiting_user"})


@dataclass(frozen=True)
class ExpectedApproval:
    """The approval version this turn's confirmation answers ("" = none was read back)."""

    approval_action_id: str


@dataclass(frozen=True)
class PendingApproval:
    """The staged write waiting on the user's go-ahead, as stored in task_state."""

    approval_action_id: str
    args_digest: str
    status: str
    label: str
    invoke_action: str


_expected: contextvars.ContextVar[ExpectedApproval | None] = contextvars.ContextVar(
    "gravitre_expected_approval", default=None
)


def approval_revision_id(pending: dict[str, Any] | None) -> str:
    """The approval identity of a pending_task (its params carry the binding)."""
    row = pending if isinstance(pending, dict) else {}
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    return str(params.get("approval_action_id") or row.get("approval_action_id") or "").strip()


def pending_approval_from_state(task_state: dict[str, Any] | None) -> PendingApproval | None:
    """The staged write awaiting approval, or None (nothing staged, or still collecting details)."""
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else None
    if not pending:
        return None
    status = str(pending.get("status") or "").strip().lower()
    if status not in _AWAITING:
        return None
    approval_id = approval_revision_id(pending)
    if not approval_id:
        return None
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    return PendingApproval(
        approval_action_id=approval_id,
        args_digest=str(params.get("bound_args_digest") or ""),
        status=status,
        label=str(params.get("label") or pending.get("label") or ""),
        invoke_action=str(params.get("invoke_action") or pending.get("invoke_action") or ""),
    )


@contextmanager
def bind_expected_approval(approval_action_id: str | None) -> Iterator[None]:
    """Bind the approval version a confirmation answers, for the work it starts.

    ``None`` binds nothing (legacy behavior); ``""`` binds "no version read back".
    Follows the turn into tasks, ``asyncio.to_thread`` and ``run_io`` (they copy
    the context).
    """
    if approval_action_id is None:
        yield
        return
    token = _expected.set(ExpectedApproval(str(approval_action_id)))
    try:
        yield
    finally:
        _expected.reset(token)


def expected_approval() -> ExpectedApproval | None:
    return _expected.get()


def approval_mismatch_reason(pending: dict[str, Any] | None) -> str | None:
    """Why a bound confirmation may not approve ``pending`` (None when it may)."""
    expected = _expected.get()
    if expected is None:
        return None
    current = approval_revision_id(pending)
    if not expected.approval_action_id:
        return "approval_not_read_back"
    if not current or current != expected.approval_action_id:
        return "approval_revised"
    return None


def set_expected_approval(approval_action_id: str) -> contextvars.Token[ExpectedApproval | None]:
    """Bind for the rest of the current task; pair with :func:`reset_expected_approval`."""
    return _expected.set(ExpectedApproval(str(approval_action_id)))


def reset_expected_approval(token: contextvars.Token[ExpectedApproval | None]) -> None:
    _expected.reset(token)
