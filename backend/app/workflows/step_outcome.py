"""Per-step outcome rollup shared by the graph runtime and the linear executor.

A run may only claim what its consequential steps proved: each write, send or
delegated step is judged on its own source-of-record evidence.
"""
from __future__ import annotations

import json
from typing import Any

from app.workflows.constants import (
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_SKIPPED,
)


def snapshot_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def step_outcome_rollup(step_rows: list[dict[str, Any]]):
    """Rollup over the consequential steps of a run, each judged on its own evidence."""
    from app.services.outcome_verification import rollup, step_action, step_is_consequential

    children: list[dict[str, Any]] = []
    for row in step_rows or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").lower()
        if status == STEP_STATUS_SKIPPED:
            continue
        output = snapshot_dict(row.get("output_snapshot"))
        step_type = str(row.get("step_type") or row.get("type") or "")
        action = step_action({**row, "output_snapshot": output})
        if not step_is_consequential(step_type, action):
            continue
        child: dict[str, Any] = {
            "consequential": True,
            "success": status == STEP_STATUS_COMPLETED,
            "step_id": row.get("step_id"),
            "action": action,
        }
        if isinstance(output.get("verification"), dict):
            child["verification"] = output["verification"]
        elif output.get("outcome_verified") is True or output.get("outcomeVerified") is True:
            child["verification"] = {"verified": True, "method": "delegated_outcome", "kind": step_type}
        if str(row.get("error_code") or "").lower() == "outcome_uncertain":
            child["outcome_uncertain"] = True
        children.append(child)
    return rollup(children)


def status_from_rollup(status: str, outcome: Any) -> str:
    """Never let a run claim more than its steps proved."""
    if not outcome.consequential:
        return status
    if status == RUN_STATUS_COMPLETED:
        return outcome.status
    if status == RUN_STATUS_FAILED and (outcome.verified or outcome.unverified):
        if not outcome.verified and not outcome.succeeded:
            # Only an ambiguous write may have landed: unknown, not failed.
            return "verification_inconclusive"
        # Some changes landed before the failure: the objective is partly done.
        return "partial_success"
    return status


def rollup_summary(outcome: Any, status: str) -> str:
    if not outcome.consequential:
        return ""
    if status == RUN_STATUS_COMPLETED:
        return f"All {outcome.consequential} changes confirmed in the source systems."
    if status == "verification_inconclusive":
        return (
            f"{outcome.verified} of {outcome.consequential} changes confirmed; "
            f"{outcome.unverified} could not be confirmed in the source system."
        )
    if status == "partial_success":
        return (
            f"{outcome.verified} of {outcome.consequential} changes confirmed; "
            f"{outcome.failed} failed and {outcome.unverified} are unconfirmed."
        )
    return ""
