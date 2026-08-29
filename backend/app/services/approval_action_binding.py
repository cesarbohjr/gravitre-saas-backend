"""Bind approved connector actions to a stable identity from proposal through execution.

Approval cards and execute paths must share one frozen action identity
(vendor + invoke_action + tool_name + args digest). Execution must never
re-resolve a different catalog action than the one the user approved.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.services.chat_connector_models import ConnectorActionPlan

APPROVAL_ACTION_MISMATCH = "APPROVAL_ACTION_MISMATCH"

#: audit_events.action emitted whenever the fail-closed net actually refuses an
#: execution. Without this a real production occurrence leaves no trace, and the
#: net is only ever observable in the deliberate test that provokes it.
APPROVAL_MISMATCH_AUDIT_ACTION = "connector.approval.action_mismatch"


class ApprovalActionMismatchError(Exception):
    """Raised when execution would diverge from the approved action identity."""

    code = APPROVAL_ACTION_MISMATCH

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


@dataclass(frozen=True)
class MismatchAuditContext:
    """Who/where to record a refusal against. Optional so pure callers still work."""

    client: Any
    org_id: str
    actor_id: str
    conversation_id: str | None = None


def record_approval_mismatch(
    audit: MismatchAuditContext | None,
    *,
    reason: str,
    details: dict[str, Any],
) -> None:
    """Emit the standing audit trace for a refusal. Never raises."""
    if audit is None or audit.client is None:
        return
    try:
        from app.workflows.audit import write_audit_event

        write_audit_event(
            audit.client,
            audit.org_id,
            audit.actor_id,
            APPROVAL_MISMATCH_AUDIT_ACTION,
            "connector_action",
            audit.conversation_id or str(uuid.uuid4()),
            {
                "code": APPROVAL_ACTION_MISMATCH,
                "reason": reason,
                "refused": True,
                **details,
            },
        )
    except Exception:  # noqa: BLE001
        # Observability must never convert a safe refusal into a crash.
        pass


@dataclass(frozen=True)
class ApprovalActionBinding:
    approval_action_id: str
    bound_tool_name: str
    bound_invoke_action: str
    bound_integration: str
    bound_args_digest: str


def _normalize_args_for_digest(args: dict[str, Any] | None) -> dict[str, Any]:
    from app.core.safe_dict import safe_normalize_stored_dict

    raw = safe_normalize_stored_dict({"args": args or {}}, key="args")
    return raw if isinstance(raw, dict) else {}


def digest_plan_args(args: dict[str, Any] | None) -> str:
    normalized = _normalize_args_for_digest(args)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_binding_from_plan(plan: ConnectorActionPlan) -> ApprovalActionBinding:
    tool_name = str(plan.tool_name or "").strip()
    invoke_action = str(plan.invoke_action or "").strip()
    integration = str(plan.integration or "").strip()
    if not tool_name or not invoke_action:
        raise ApprovalActionMismatchError(
            "Cannot bind an approval action without tool_name and invoke_action.",
            details={
                "tool_name": tool_name,
                "invoke_action": invoke_action,
            },
        )
    return ApprovalActionBinding(
        approval_action_id=str(uuid.uuid4()),
        bound_tool_name=tool_name,
        bound_invoke_action=invoke_action,
        bound_integration=integration,
        bound_args_digest=digest_plan_args(plan.args),
    )


def binding_fields(binding: ApprovalActionBinding) -> dict[str, str]:
    return {
        "approval_action_id": binding.approval_action_id,
        "bound_tool_name": binding.bound_tool_name,
        "bound_invoke_action": binding.bound_invoke_action,
        "bound_integration": binding.bound_integration,
        "bound_args_digest": binding.bound_args_digest,
    }


def bind_plan_dict(plan_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach stable approval identity fields to a pending-task params dict."""
    from app.core.safe_dict import safe_normalize_stored_dict

    plan = ConnectorActionPlan(
        tool_name=str(plan_dict.get("tool_name") or ""),
        invoke_action=str(plan_dict.get("invoke_action") or ""),
        integration=str(plan_dict.get("integration") or ""),
        kind=str(plan_dict.get("kind") or "write"),
        label=str(plan_dict.get("label") or ""),
        args=_normalize_args_for_digest(plan_dict.get("args") if isinstance(plan_dict.get("args"), dict) else {}),
        requires_approval=bool(plan_dict.get("requires_approval")),
        approval_reason=plan_dict.get("approval_reason"),
        destructive=bool(plan_dict.get("destructive")),
        inferred_fields=tuple(str(item) for item in (plan_dict.get("inferred_fields") or [])),
        inference_sources=safe_normalize_stored_dict(plan_dict, key="inference_sources"),
    )
    binding = build_binding_from_plan(plan)
    return {**plan_dict, **binding_fields(binding)}


def binding_from_params(params: dict[str, Any]) -> ApprovalActionBinding | None:
    approval_action_id = str(params.get("approval_action_id") or "").strip()
    tool_name = str(params.get("bound_tool_name") or "").strip()
    invoke_action = str(params.get("bound_invoke_action") or "").strip()
    integration = str(params.get("bound_integration") or "").strip()
    args_digest = str(params.get("bound_args_digest") or "").strip()
    if not approval_action_id or not tool_name or not invoke_action or not args_digest:
        return None
    return ApprovalActionBinding(
        approval_action_id=approval_action_id,
        bound_tool_name=tool_name,
        bound_invoke_action=invoke_action,
        bound_integration=integration,
        bound_args_digest=args_digest,
    )


def resolve_invoke_action_for_tool(
    registry: Any,
    *,
    tool_name: str,
    args: dict[str, Any] | None,
) -> str | None:
    spec = registry.get_spec(str(tool_name or "").strip()) if registry is not None else None
    if spec is None:
        return None
    try:
        return str(registry.resolve_invoke_action(spec, dict(args or {})) or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def assert_plan_matches_binding(
    plan: ConnectorActionPlan,
    params: dict[str, Any],
    *,
    registry: Any | None = None,
    audit: MismatchAuditContext | None = None,
) -> None:
    """Fail closed when live plan fields diverge from the approved binding."""
    binding = binding_from_params(params)
    current_tool = str(plan.tool_name or "").strip()
    current_invoke = str(plan.invoke_action or "").strip()
    current_integration = str(plan.integration or "").strip()
    current_digest = digest_plan_args(plan.args)

    if binding is not None:
        mismatches: dict[str, str] = {}
        if current_tool != binding.bound_tool_name:
            mismatches["tool_name"] = f"{binding.bound_tool_name} != {current_tool}"
        if current_invoke != binding.bound_invoke_action:
            mismatches["invoke_action"] = f"{binding.bound_invoke_action} != {current_invoke}"
        if binding.bound_integration and current_integration != binding.bound_integration:
            mismatches["integration"] = f"{binding.bound_integration} != {current_integration}"
        if current_digest != binding.bound_args_digest:
            mismatches["args_digest"] = "approved args no longer match staged args"
        if mismatches:
            details = {
                "approval_action_id": binding.approval_action_id,
                "mismatches": mismatches,
                "approved": {
                    "tool_name": binding.bound_tool_name,
                    "invoke_action": binding.bound_invoke_action,
                    "integration": binding.bound_integration,
                },
                "current": {
                    "tool_name": current_tool,
                    "invoke_action": current_invoke,
                    "integration": current_integration,
                },
            }
            record_approval_mismatch(audit, reason="binding_divergence", details=details)
            raise ApprovalActionMismatchError(
                "The approved action no longer matches what is about to execute. Please try again.",
                details=details,
            )

    # Legacy pending_task rows without binding fields trust staged invoke_action as-is.
    if binding is None:
        return

    if registry is None:
        return

    resolved = resolve_invoke_action_for_tool(
        registry,
        tool_name=current_tool,
        args=plan.args,
    )
    if resolved and current_invoke and resolved != current_invoke:
        details = {
            "tool_name": current_tool,
            "invoke_action": current_invoke,
            "resolved_invoke_action": resolved,
        }
        record_approval_mismatch(audit, reason="live_resolution_divergence", details=details)
        raise ApprovalActionMismatchError(
            "The approved action no longer matches what is about to execute. Please try again.",
            details=details,
        )


def plan_from_approved_params(
    params: dict[str, Any],
    *,
    registry: Any | None = None,
    audit: MismatchAuditContext | None = None,
) -> ConnectorActionPlan | None:
    """Restore the exact approved plan from pending_task.params."""
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    if not isinstance(params, dict) or not params.get("invoke_action"):
        return None
    plan = ChatConnectorExecutionService.plan_from_dict(params)
    assert_plan_matches_binding(plan, params, registry=registry, audit=audit)
    return plan


def format_approval_mismatch_message(exc: ApprovalActionMismatchError) -> str:
    return (
        str(exc)
        or "The approved action no longer matches what is about to execute. Please try again."
    )
