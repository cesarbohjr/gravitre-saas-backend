"""3.0-E deterministic catalog search — eligible ActionSpecs, not an LLM dump."""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    execution_plan_patch,
    mark_plan_terminal,
    observations_patch,
)
from app.services.jit_tool_discovery import (
    HARD_CAP_ELIGIBLE,
    MAX_ELIGIBLE_TOOLS,
    search_eligible_action_specs,
)

_CATALOG_INTENT = re.compile(
    r"(?is)\b("
    r"search(?:ing)? (?:the )?(?:tool )?catalog"
    r"|tool catalog"
    r"|action schema"
    r"|which (?:connected )?(?:tools|actions)"
    r"|what (?:tools|actions) (?:can|do) i"
    r")\b"
)


def _vendor_name(slug: str | None) -> str:
    """Product name for a vendor slug (``google_analytics`` -> Google Analytics)."""
    raw = str(slug or "").strip()
    if not raw:
        return ""
    try:
        from app.services.connector_semantic_registry import connector_display_name

        return connector_display_name(raw) or raw
    except Exception:  # noqa: BLE001 — copy only; never fail the turn over a label
        return raw.replace("_", " ").title()


def match_catalog_search_intent(message: str) -> bool:
    return bool(_CATALOG_INTENT.search(message or ""))


_READ_ONLY = re.compile(r"(?is)\bread[- ]only\b|do not create")
_CAPABILITIES = re.compile(r"(?is)\b(which (?:connected )?(?:tools|actions)|what (?:tools|actions) (?:can|do) i)\b")


def try_catalog_search_turn(
    *,
    message: str,
    connected_integrations: list[str] | None,
    capability_id: str | None = None,
    task_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not match_catalog_search_intent(message or ""):
        return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    include_writes = bool(_CAPABILITIES.search(message or "")) and not bool(_READ_ONLY.search(message or ""))
    found = search_eligible_action_specs(
        query=message or "",
        capability_id=capability_id,
        connected=connected,
        include_writes=include_writes,
        max_results=MAX_ELIGIBLE_TOOLS,
    )
    if len(found) > HARD_CAP_ELIGIBLE:
        found = found[:HARD_CAP_ELIGIBLE]
    names = [row.action_id for row in found]
    mentioned_github = bool(re.search(r"\bgithub\b", message or "", re.I))
    github_excluded = mentioned_github and "github" not in set(connected)
    lines = []
    table_rows: list[dict[str, Any]] = []
    writes = 0
    for row in found[:16]:
        label = str(row.name or "").strip() or row.action_id
        if row.governed_write:
            writes += 1
            gate = "makes changes, needs your okay first"
        elif row.f1_read:
            gate = "looks things up"
        else:
            gate = "looks things up"
        lines.append(f"- {label} ({_vendor_name(row.vendor)}; {gate})")
        table_rows.append(
            {
                "action": label,
                "vendor": str(row.vendor or ""),
                "gate": gate,
            }
        )
    intro = (
        "Here's what I can do with your connected tools that matches that search. I haven't run any of it."
        if include_writes
        else "Here's what I can look up with your connected tools that matches that search. I haven't run any of it."
    )
    if writes:
        intro += " Anything that makes changes needs your okay before I run it, and I haven't started any of those."
    body_bits = [
        intro,
        "\n".join(lines) if lines else "Nothing I can do with your connected tools matched that.",
        f"That's {len(found)} match{'es' if len(found) != 1 else ''} (I show up to {HARD_CAP_ELIGIBLE}).",
    ]
    if github_excluded:
        body_bits.append("GitHub isn't connected yet, so I can't work with GitHub issues.")
    body = "\n\n".join(body_bits)
    plan = mark_plan_terminal(
        ExecutionPlan(
            plan_id=str(uuid4()),
            summary="Catalog search of eligible ActionSpecs",
            objective=str(message or "")[:240],
            steps=[
                ExecutionStep(
                    step_id="catalog_primary",
                    title="search catalog",
                    kind="read",
                )
            ],
            source="catalog_search",
            execution_strategy="api_native",
        ),
        "completed",
    )
    obs = ExecutionObservation(
        step_id="catalog_primary",
        connector_id="gravitre",
        success=True,
        summary=body.split("\n", 1)[0][:500],
        structured={
            "rows": table_rows,
            "eligible_count": len(found),
            "writes_listed": writes,
            "writes_started": False,
            "execution_path": "catalog_search_eligible",
            "provider_invoked": False,
        },
        observation_id=str(uuid4()),
        plan_id=plan.plan_id,
        source="catalog_search",
    )
    from app.services.durable_work_session import bind_finished_work, execution_result_from_finished_work

    merged = {
        **(task_state or {}),
        **execution_plan_patch(plan),
        **observations_patch([obs]),
    }
    merged = bind_finished_work(merged, body=body, title="Eligible connected actions")
    for art in merged.get("work_artifacts") or []:
        if isinstance(art, dict):
            meta = art.get("metadata") if isinstance(art.get("metadata"), dict) else {}
            meta["execution_path"] = "catalog_search_eligible"
            art["metadata"] = meta
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": body,
        "task_state": merged,
        "workflow_status": "completed",
        "execution_path": "catalog_search_eligible",
        "execution_result": execution_result_from_finished_work(merged, body=body, success=True),
        "eligible_action_ids": names,
        "eligible_count": len(found),
        "hard_cap": HARD_CAP_ELIGIBLE,
        "github_excluded": github_excluded,
        "writes_started": False,
        "writes_listed": writes,
        "include_writes": include_writes,
        "provider_reinvoked": False,
        "plan_id": plan.plan_id,
    }
