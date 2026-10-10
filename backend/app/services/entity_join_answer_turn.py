"""3.0-H natural-language answer from accepted BusinessEntity store.

Does not invent joins. Does not live-read a disconnected provider.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from uuid import uuid4

from app.services.business_entity_fabric import load_accepted_entities
from app.services.clarification_policy import format_not_connected_message
from app.services.connector_semantic_registry import connector_display_name
from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    execution_plan_patch,
    mark_plan_terminal,
    observations_patch,
)

_CROSS = re.compile(
    r"(?is)\b("
    r"same (?:company|customer|account|entity)"
    r"|across (?:systems|hubspot|quickbooks|zendesk)"
    r"|hubspot and (?:quickbooks|zendesk|qbo)"
    r"|(?:quickbooks|zendesk) and hubspot"
    r"|cross[- ]system"
    r")\b"
)


def match_cross_system_entity_intent(message: str) -> bool:
    return bool(_CROSS.search(message or ""))


@dataclass(frozen=True)
class EntityJoinIntent:
    display_name: str | None


def entity_join_intent(message: str) -> EntityJoinIntent | None:
    if not match_cross_system_entity_intent(message or ""):
        return None
    named = re.search(
        r"(?is)\babout\s+([A-Za-z][\w&'. -]{0,40}?)\s+across\b",
        message or "",
    )
    display_name = named.group(1).strip() if named else None
    return EntityJoinIntent(display_name=display_name)


def try_cross_system_entity_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not match_cross_system_entity_intent(message or ""):
        return None
    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    entities = load_accepted_entities(client, org_id)
    companies = [row for row in entities if row.kind == "company" and len(row.bindings) >= 2]
    wanted = (entity_join_intent(message) or EntityJoinIntent(None)).display_name
    if wanted:
        named = [
            row
            for row in companies
            if row.display_name.strip().lower() == wanted.strip().lower()
        ]
        if named:
            companies = named
        elif companies:
            return _entity_join_finished(
                body=(
                    f"I have accepted joins in this organization, but none named “{wanted}”. "
                    "I will not treat a similar display name as the same company."
                ),
                task_state=task_state,
                join=False,
            )
    if not companies:
        return _entity_join_finished(
            body=(
                "I haven't matched this company across HubSpot, QuickBooks, and Zendesk yet. "
                "A matching name isn't enough, so I'm keeping them separate until I see the "
                "same website or email in each."
            ),
            task_state=task_state,
            join=False,
        )
    entity = companies[0]
    systems = sorted({b.system for b in entity.bindings if b.system})
    hosts = sorted(
        {e.value for e in entity.evidence if e.kind == "host"}
        | {e.value for b in entity.bindings for e in b.evidence if e.kind == "host"}
    )
    missing = [
        format_not_connected_message(vendor, display_name=connector_display_name(vendor))
        for vendor in systems
        if vendor not in connected
    ]
    fact = (
        f"I've matched “{entity.display_name}” across "
        f"{', '.join(connector_display_name(s) for s in systems)} based on what Gravitre has saved"
        + (f" (website {', '.join(hosts)})" if hosts else "")
        + "."
    )
    inference = (
        "That match comes from what Gravitre has saved, not a fresh look at each tool, "
        "so I won't mix their numbers together as if they were one set."
    )
    if missing:
        limitation = " ".join(missing)
    else:
        limitation = "If you want the latest numbers, I can check each tool separately."
    body = f"{fact}\n\n{inference}\n\n{limitation}"
    return _entity_join_finished(
        body=body,
        task_state={
            **(task_state or {}),
            "business_entity": entity.as_dict(),
            "capability_id": "entity.join.store",
        },
        join=True,
        extra={
            "entity_id": entity.id,
            "systems": systems,
            "missing_live_sources": missing,
        },
        rows=[
            {
                "system": system,
                "entity": entity.display_name,
                "join": "accepted store join",
            }
            for system in systems
        ],
    )


def _entity_join_finished(
    *,
    body: str,
    task_state: dict[str, Any] | None,
    join: bool,
    extra: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from app.services.durable_work_session import bind_finished_work, execution_result_from_finished_work

    plan = mark_plan_terminal(
        ExecutionPlan(
            plan_id=str(uuid4()),
            summary="Accepted store join answer",
            objective="entity_join_store",
            steps=[
                ExecutionStep(
                    step_id="entity_join_primary",
                    title="store join",
                    kind="read",
                    meta={"entity_id": (extra or {}).get("entity_id")},
                )
            ],
            source="entity_join_store",
            execution_strategy="api_native",
            entity_id=str((extra or {}).get("entity_id") or "") or None,
        ),
        "completed",
    )
    obs = ExecutionObservation(
        step_id="entity_join_primary",
        connector_id="gravitre",
        success=True,
        summary=body.split("\n", 1)[0][:500],
        structured={
            "rows": list(rows or []),
            "execution_path": "entity_join_store",
            "provider_invoked": False,
            "join": join,
        },
        observation_id=str(uuid4()),
        plan_id=plan.plan_id,
        source="entity_join_store",
    )
    merged = {
        **(task_state or {}),
        **execution_plan_patch(plan),
        **observations_patch([obs]),
    }
    merged = bind_finished_work(merged, body=body, title="Cross-system entity")
    for art in merged.get("work_artifacts") or []:
        if isinstance(art, dict):
            meta = art.get("metadata") if isinstance(art.get("metadata"), dict) else {}
            meta["execution_path"] = "entity_join_store"
            art["metadata"] = meta
    payload = {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": body,
        "task_state": merged,
        "workflow_status": "completed",
        "execution_path": "entity_join_store",
        "execution_result": execution_result_from_finished_work(merged, body=body, success=True),
        "join": join,
        "writes_started": False,
        "provider_reinvoked": False,
        "plan_id": plan.plan_id,
    }
    if extra:
        payload.update(extra)
    return payload
