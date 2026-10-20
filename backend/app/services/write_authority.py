"""One write-authority check on the shared invoke spine.

Before this, ``invoke_tool`` trusted its caller: each surface (chat, canvas,
ReAct, extension, agent jobs, compensation) decided on its own whether a write
was approved, and a caller that skipped its gate reached the provider. Now every
catalog write must arrive with a declared authority:

* ``human``: a person approved this exact action (chat confirmation, approval
  queue, extension confirm token, an explicit user click);
* ``run``: the write is a step of a workflow run whose approval was granted;
* ``policy``: org policy allows it without a person (HITL says no approval
  needed, or an autonomous agent with an ``auto_run`` override). Never valid for
  actions that always require approval (sends, CRM creates, ticket state
  changes, destructive, financial ...);
* ``compensation``: undoing an earlier write of an approved run;
* ``internal``: operator smoke tests behind the internal secret.

Callers declare authority with ``with write_authority(kind, ref):`` around the
call (a context variable, so signatures do not change). ``WRITE_AUTHORITY_MODE``
is ``shadow`` by default: a missing or invalid authority is logged
(``write_authority_violation``) and allowed, so production paths that were
missed show up in logs before anything is refused. ``enforce`` refuses them.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from app.core.logging import get_logger

logger = get_logger(__name__)

KINDS = frozenset({"human", "run", "policy", "compensation", "internal"})


@dataclass(frozen=True)
class WriteAuthority:
    kind: str
    ref: str = ""


_current: contextvars.ContextVar[WriteAuthority | None] = contextvars.ContextVar("write_authority", default=None)


@contextmanager
def write_authority(kind: str, ref: str | None = "") -> Iterator[WriteAuthority]:
    if kind not in KINDS:
        raise ValueError(f"unknown write authority kind {kind!r}")
    token = _current.set(WriteAuthority(kind=kind, ref=str(ref or "")))
    try:
        yield _current.get()  # type: ignore[misc]
    finally:
        _current.reset(token)


def declare_write_authority(kind: str, ref: str | None = "") -> None:
    """Set authority for the rest of the current task (a request handler's own context).

    For route handlers where wrapping the call would re-indent a large block;
    FastAPI runs each request in its own context, so this does not leak.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown write authority kind {kind!r}")
    _current.set(WriteAuthority(kind=kind, ref=str(ref or "")))


def current_write_authority() -> WriteAuthority | None:
    return _current.get()


def authorized(kind: str, ref: str = ""):
    """Decorator: run a function (sync or async) under a declared write authority."""
    import functools
    import inspect

    def wrap(fn):
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def run_async(*args, **kwargs):
                with write_authority(kind, ref or fn.__name__):
                    return await fn(*args, **kwargs)

            return run_async

        @functools.wraps(fn)
        def run(*args, **kwargs):
            with write_authority(kind, ref or fn.__name__):
                return fn(*args, **kwargs)

        return run

    return wrap


class WriteAuthorityError(Exception):
    code = "WRITE_AUTHORITY_REQUIRED"


def _mode(settings: Any | None) -> str:
    value = str(getattr(settings, "write_authority_mode", "") or "shadow").strip().lower()
    return value if value in {"shadow", "enforce", "off"} else "shadow"


def check_write_authority(action: str, *, settings: Any | None = None, org_id: str | None = None,
                          actor_id: str | None = None) -> WriteAuthority | None:
    """Return the authority for a write, or raise in enforce mode when it has none.

    Reads are not checked (returns None without looking).
    """
    from app.services.outcome_verification import is_write_action

    if not is_write_action(action):
        return None
    mode = _mode(settings)
    if mode == "off":
        return current_write_authority()
    authority = current_write_authority()
    problem: str | None = None
    if authority is None:
        problem = "no_authority"
    elif authority.kind == "policy":
        from app.connectors.action_catalog.f1_write_slice import requires_write_approval_always
        from app.connectors.action_catalog.registry import get_action_spec

        try:
            spec = get_action_spec(action)
            risk_class = str(getattr(spec, "risk_class", "") or "") if spec is not None else ""
            always = bool(requires_write_approval_always(action, risk_class=risk_class))
        except Exception:  # noqa: BLE001
            always = False
        if always:
            problem = "policy_cannot_authorize_always_approve_action"
    if problem is None:
        return authority
    logger.warning(
        "write_authority_violation mode=%s action=%s problem=%s authority=%s org_id=%s actor_id=%s",
        mode,
        action,
        problem,
        f"{authority.kind}:{authority.ref}" if authority else None,
        org_id,
        actor_id,
    )
    if mode == "enforce":
        raise WriteAuthorityError(
            "This change needs an approval that was not provided"
            if problem == "no_authority"
            else "This kind of change always needs a person's approval"
        )
    return authority
