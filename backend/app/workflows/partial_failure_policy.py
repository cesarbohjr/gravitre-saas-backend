"""Partial-failure policy resolver (STA-287)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from app.workflows.constants import (
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PARTIAL_SUCCESS,
)

POLICY_FAIL_FAST = "fail_fast"
POLICY_COMPENSATE = "compensate"
POLICY_PARTIAL_SUCCESS = "partial_success"


class FailureContext(str, Enum):
    WORKFLOW_GRAPH = "workflow_graph"
    WORKFLOW_GRAPH_PARALLEL = "workflow_graph_parallel"
    AUTONOMOUS_CONNECTOR_CHAIN = "autonomous_connector_chain"
    DEPARTMENT_PACK_INSTALL = "department_pack_install"
    MARKETPLACE_BULK_INSTALL = "marketplace_bulk_install"
    DIGITAL_TWIN = "digital_twin"
    HRIS_FINANCIAL_WRITE = "hris_financial_write"


_CONTEXT_POLICY: dict[FailureContext, str] = {
    FailureContext.WORKFLOW_GRAPH: POLICY_FAIL_FAST,
    FailureContext.WORKFLOW_GRAPH_PARALLEL: POLICY_FAIL_FAST,
    FailureContext.AUTONOMOUS_CONNECTOR_CHAIN: POLICY_COMPENSATE,
    FailureContext.DEPARTMENT_PACK_INSTALL: POLICY_PARTIAL_SUCCESS,
    FailureContext.MARKETPLACE_BULK_INSTALL: POLICY_PARTIAL_SUCCESS,
    FailureContext.DIGITAL_TWIN: POLICY_FAIL_FAST,
    FailureContext.HRIS_FINANCIAL_WRITE: POLICY_FAIL_FAST,
}


def resolve_failure_policy(context: FailureContext | str) -> str:
    """Return fail_fast, compensate, or partial_success for a execution context."""
    if isinstance(context, str):
        context = FailureContext(context)
    return _CONTEXT_POLICY[context]


def resolve_run_status(
    context: FailureContext | str,
    *,
    completed_count: int = 0,
    failed_count: int = 0,
    total_count: int | None = None,
) -> str:
    """Map counts to a workflow/run status under the context policy."""
    policy = resolve_failure_policy(context)
    total = total_count if total_count is not None else completed_count + failed_count

    if failed_count == 0:
        return RUN_STATUS_COMPLETED

    if policy == POLICY_PARTIAL_SUCCESS and completed_count > 0:
        return RUN_STATUS_PARTIAL_SUCCESS

    if policy == POLICY_COMPENSATE and completed_count > 0:
        # Side effects may exist — run failed but compensation queue populated separately
        return RUN_STATUS_FAILED

    if failed_count >= total and completed_count == 0:
        return RUN_STATUS_FAILED

    return RUN_STATUS_FAILED


def summarize_partial_result(
    *,
    completed: list[Any],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Standard shape for partial-success API responses."""
    status = resolve_run_status(
        FailureContext.DEPARTMENT_PACK_INSTALL,
        completed_count=len(completed),
        failed_count=len(failures),
        total_count=len(completed) + len(failures),
    )
    return {
        "status": status,
        "completedCount": len(completed),
        "failedCount": len(failures),
        "failures": failures,
        "partialSuccess": status == RUN_STATUS_PARTIAL_SUCCESS,
    }
