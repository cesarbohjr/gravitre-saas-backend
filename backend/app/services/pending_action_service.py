"""Phase E5 — PendingAction: governance/continuation state, not executable plan SoT."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

PendingActionKind = Literal[
    "confirmation",
    "clarification",
    "approval",
    "selection",
    "plan_confirm",
    "step_confirm",
]

PendingActionStatus = Literal[
    "awaiting_user",
    "confirmed",
    "declined",
    "cancelled",
    "expired",
]


@dataclass
class PendingAction:
    """Conversation state waiting for user confirmation, clarification, approval, or selection."""

    pending_action_id: str
    kind: PendingActionKind
    status: PendingActionStatus = "awaiting_user"
    plan_id: str | None = None
    step_id: str | None = None
    revision: int | None = None
    message: str | None = None
    source: str = "offered_action"
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "pending_action_id": self.pending_action_id,
            "kind": self.kind,
            "status": self.status,
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "message": self.message,
            "source": self.source,
            "meta": dict(self.meta),
        }
        if self.revision is not None:
            payload["revision"] = self.revision
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PendingAction | None:
        if not isinstance(raw, dict):
            return None
        return cls(
            pending_action_id=str(raw.get("pending_action_id") or raw.get("id") or uuid4()),
            kind=raw.get("kind") or "confirmation",  # type: ignore[arg-type]
            status=raw.get("status") or "awaiting_user",  # type: ignore[arg-type]
            plan_id=raw.get("plan_id"),
            step_id=raw.get("step_id"),
            revision=int(raw["revision"]) if raw.get("revision") is not None else None,
            message=raw.get("message"),
            source=str(raw.get("source") or "task_state"),
            meta=dict(raw.get("meta") or {}),
        )


def pending_action_patch(action: PendingAction | None) -> dict[str, Any]:
    return {"pending_action": action.as_dict() if action else None}


def pending_action_from_offered(
    *,
    offered_id: str,
    plan_id: str,
    scope: list[str] | None = None,
    tools: list[str] | None = None,
) -> PendingAction:
    return PendingAction(
        pending_action_id=str(uuid4()),
        kind="confirmation",
        status="awaiting_user",
        plan_id=plan_id,
        message="Awaiting user confirmation for offered READ inspection",
        source="offered_action",
        meta={
            "offered_action_id": offered_id,
            "scope": list(scope or []),
            "tools": list(tools or []),
        },
    )


def pending_action_from_pending_task(pending: dict[str, Any], *, plan_id: str) -> PendingAction:
    status_raw = str(pending.get("status") or "").strip().lower()
    kind: PendingActionKind = "confirmation"
    if status_raw in {"awaiting_params"}:
        kind = "clarification"
    elif status_raw in {"awaiting_admin_approval"}:
        kind = "approval"
    elif status_raw in {"awaiting_plan_confirm"}:
        kind = "plan_confirm"
    elif status_raw in {"awaiting_step_confirm"}:
        kind = "step_confirm"
    elif status_raw in {"awaiting_confirm"}:
        kind = "approval" if pending.get("requires_approval") else "confirmation"

    pa_status: PendingActionStatus = "awaiting_user"
    if status_raw in {"completed", "confirmed"}:
        pa_status = "confirmed"
    elif status_raw in {"cancelled", "declined"}:
        pa_status = "declined"

    return PendingAction(
        pending_action_id=str(pending.get("pending_action_id") or uuid4()),
        kind=kind,
        status=pa_status,
        plan_id=plan_id,
        step_id=str(pending.get("step_id") or "") or None,
        message=str(pending.get("label") or pending.get("action") or "") or None,
        source="pending_task_bridge",
        meta={"legacy_pending_status": status_raw},
    )
