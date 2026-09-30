"""Canonical target validation for training/external dataset bindings.

Bindings are pointers into existing Gravitre entities. This module does not
create a new target registry. It validates the target against the canonical
source/read model already used by that product surface.
"""
from __future__ import annotations

from typing import Any

from app.operators.repository import get_operator
from app.plays.catalog import get_platform_play
from app.workflows.repository import get_workflow_def


SUPPORTED_DATASET_TARGET_TYPES = frozenset(
    {"agent", "model", "department", "evaluation", "play", "workflow"}
)


def dataset_target_exists(
    client: Any,
    org_id: str,
    *,
    target_type: str,
    target_id: str,
) -> bool:
    kind = str(target_type or "").strip().lower()
    target = str(target_id or "").strip()
    if kind not in SUPPORTED_DATASET_TARGET_TYPES or not target:
        return False

    if kind == "play":
        return get_platform_play(target) is not None

    if kind == "workflow":
        return get_workflow_def(client, org_id, target) is not None

    if kind == "agent":
        return get_operator(client, org_id, target) is not None

    if kind == "model":
        rows = (
            client.table("ml_models")
            .select("id")
            .eq("org_id", org_id)
            .eq("id", target)
            .limit(1)
            .execute()
            .data
            or []
        )
        return bool(rows)

    if kind == "department":
        # Agent roster is the existing customer-facing source for departments;
        # Model Studio derives its department choices from that same roster.
        rows = (
            client.table("agents")
            .select("id")
            .eq("org_id", org_id)
            .eq("department", target)
            .limit(1)
            .execute()
            .data
            or []
        )
        return bool(rows)

    # Evaluation has no parallel dataset-owned registry. An evaluation binding
    # must point at an existing tenant response evaluation.
    rows = (
        client.table("response_evaluations")
        .select("id")
        .eq("org_id", org_id)
        .eq("id", target)
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def require_dataset_target(
    client: Any,
    org_id: str,
    *,
    target_type: str,
    target_id: str,
) -> None:
    try:
        exists = dataset_target_exists(
            client,
            org_id,
            target_type=target_type,
            target_id=target_id,
        )
    except Exception as exc:  # canonical target lookup should fail closed
        raise RuntimeError(
            f"Could not verify canonical {target_type} target."
        ) from exc
    if not exists:
        raise LookupError(
            f"Dataset target not found in this organization: {target_type}:{target_id}"
        )
