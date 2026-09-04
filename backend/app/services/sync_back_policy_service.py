"""Per-department CRM / SoR sync-back timing (Phase 4 — Alta-style defer).

Default: immediate verified write (current behavior).
Optional: defer early-tier actions until the pipeline sync milestone; F6 verification
unchanged when the write eventually fires.
"""
from __future__ import annotations

from typing import Any, Literal

from app.core.safe_dict import safe_normalize_stored_dict

from app.marketplace.department_pipelines.catalog import (
    DepartmentPipelineSpec,
    PipelineStageSpec,
    get_department_pipeline,
    pipeline_for_invoke_action,
)

SyncTimingMode = Literal["immediate", "defer_to_milestone"]

_SETTINGS_KEY = "department_pipelines"


def _default_policy() -> dict[str, Any]:
    return {"syncTiming": "immediate", "deferMilestoneStageId": None}


def load_department_pipeline_settings(org_settings: dict[str, Any] | None) -> dict[str, Any]:
    root = org_settings or {}
    block = root.get(_SETTINGS_KEY) if isinstance(root.get(_SETTINGS_KEY), dict) else {}
    sync_back = block.get("syncBack") if isinstance(block.get("syncBack"), dict) else {}
    return {"syncBack": sync_back}


def get_sync_back_policy(
    org_settings: dict[str, Any] | None,
    *,
    department: str,
) -> dict[str, Any]:
    dept = str(department or "").strip().lower()
    block = load_department_pipeline_settings(org_settings)
    row = block["syncBack"].get(dept) if isinstance(block["syncBack"].get(dept), dict) else {}
    mode = str(row.get("syncTiming") or row.get("sync_timing") or "immediate").strip().lower()
    if mode not in {"immediate", "defer_to_milestone"}:
        mode = "immediate"
    pipeline = get_department_pipeline(department=dept)
    default_milestone = pipeline.sync_milestone_stage_id if pipeline else None
    milestone = str(row.get("deferMilestoneStageId") or row.get("defer_milestone_stage_id") or default_milestone or "").strip() or None
    return {
        "department": dept,
        "syncTiming": mode,
        "deferMilestoneStageId": milestone,
        "defaultDeferMilestoneStageId": default_milestone,
    }


def save_sync_back_policy(
    org_settings: dict[str, Any] | None,
    *,
    department: str,
    sync_timing: SyncTimingMode,
    defer_milestone_stage_id: str | None = None,
) -> dict[str, Any]:
    root = dict(org_settings or {})
    block = safe_normalize_stored_dict(root, key=_SETTINGS_KEY)
    sync_back = safe_normalize_stored_dict(block, key="syncBack")
    dept = str(department or "").strip().lower()
    pipeline = get_department_pipeline(department=dept)
    milestone = defer_milestone_stage_id
    if sync_timing == "defer_to_milestone" and not milestone and pipeline:
        milestone = pipeline.sync_milestone_stage_id
    sync_back[dept] = {
        "syncTiming": sync_timing,
        "deferMilestoneStageId": milestone,
    }
    block["syncBack"] = sync_back
    root[_SETTINGS_KEY] = block
    return root


def evaluate_sync_back_gate(
    org_settings: dict[str, Any] | None,
    *,
    invoke_action: str,
    department: str | None = None,
    explicit_milestone_stage_id: str | None = None,
) -> dict[str, Any]:
    """Return whether a CRM/SoR write should run now or be deferred."""
    pipeline, stage = pipeline_for_invoke_action(invoke_action)
    dept = str(department or (pipeline.department if pipeline else "") or "").strip().lower()
    policy = get_sync_back_policy(org_settings, department=dept) if dept else _default_policy()
    mode = policy.get("syncTiming") or "immediate"

    if mode != "defer_to_milestone":
        return {
            "defer": False,
            "syncTiming": "immediate",
            "reason": "immediate_sync_default",
            "department": dept or None,
            "invokeAction": invoke_action,
        }

    if not pipeline or not stage:
        return {
            "defer": False,
            "syncTiming": mode,
            "reason": "unmapped_action_runs_immediate",
            "department": dept or None,
            "invokeAction": invoke_action,
        }

    milestone_id = str(
        explicit_milestone_stage_id
        or policy.get("deferMilestoneStageId")
        or pipeline.sync_milestone_stage_id
    ).strip()

    if explicit_milestone_stage_id and explicit_milestone_stage_id == milestone_id:
        return {
            "defer": False,
            "syncTiming": mode,
            "reason": "sync_milestone_reached",
            "department": pipeline.department,
            "milestoneStageId": milestone_id,
            "invokeAction": invoke_action,
        }

    # Defer all mapped CRM/SoR writes until the named milestone is explicitly reached.
    return {
        "defer": True,
        "syncTiming": mode,
        "reason": "deferred_until_sync_milestone",
        "department": pipeline.department,
        "stageId": stage.stage_id,
        "deferUntilStageId": milestone_id,
        "invokeAction": invoke_action,
        "message": (
            f"Sync to the system of record is deferred until the "
            f"「{milestone_id.replace('_', ' ')}」 milestone. "
            f"This action will not write to the destination yet."
        ),
    }


def is_crm_sync_invoke_action(invoke_action: str) -> bool:
    """True for mutating CRM/accounting writes that participate in sync-back policy."""
    key = str(invoke_action or "").strip().lower()
    if not key:
        return False
    prefixes = (
        "hubspot.",
        "salesforce.",
        "quickbooks.",
        "greenhouse.",
        "zendesk.",
        "clay.crm.",
        "marketo.",
        "pipedrive.",
        "connectwise.",
    )
    if any(key.startswith(p) for p in prefixes):
        return True
    pipeline, stage = pipeline_for_invoke_action(key)
    return bool(stage and stage.sync_milestone_tier in {"early", "sync"} and stage.capability_kind == "connector")
