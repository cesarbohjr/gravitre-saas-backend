"""Install marketplace intelligence packs as agent knowledge assignments."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.intelligence_packs.catalog import (
    get_intelligence_pack_spec,
    intelligence_pack_to_marketplace_asset,
    list_intelligence_pack_specs,
)
from app.services.agent_knowledge_assignment_service import get_agent_knowledge_assignment_service
from app.services.agent_knowledge_provenance_service import get_agent_knowledge_provenance_service
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

AUDIT_INTELLIGENCE_PACK_INSTALLED = "marketplace.intelligence_pack.installed"


def list_pack_catalog() -> list[dict[str, Any]]:
    return [intelligence_pack_to_marketplace_asset(spec) for spec in list_intelligence_pack_specs()]


def install_intelligence_pack(
    client: Any,
    org_id: str,
    agent_id: str,
    pack_id: str,
    *,
    actor_id: str | None = None,
    asset_id: str | None = None,
) -> dict[str, Any]:
    spec = get_intelligence_pack_spec(pack_id)
    if not spec:
        raise ValueError(f"Unknown intelligence pack: {pack_id}")

    assignment_svc = get_agent_knowledge_assignment_service()
    provenance_svc = get_agent_knowledge_provenance_service()
    created: list[dict[str, Any]] = []

    for row in spec.assignments:
        assignment = assignment_svc.create_assignment(
            client,
            org_id,
            agent_id,
            {
                "source_type": row.source_type,
                "source_id": row.source_id,
                "label": row.label,
                "department": row.department,
                "subdomain": row.subdomain or spec.default_subdomain,
                "confidence_weight": row.confidence_weight,
                "owning_department": row.department,
                "metadata": {"intelligence_pack_id": spec.pack_id, "tier": spec.tier},
            },
        )
        created.append(assignment)
        if row.reference_summary:
            try:
                provenance_svc.upsert_reference(
                    client,
                    org_id,
                    agent_id,
                    {
                        "assignment_id": assignment.get("id"),
                        "source_system": row.source_type,
                        "external_object_id": row.source_id,
                        "source_title": row.label,
                        "source_type": row.source_type,
                        "memory_summary": row.reference_summary,
                        "external_url": row.external_url,
                        "metadata": {"intelligence_pack_id": spec.pack_id},
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("intelligence_pack_reference_skipped pack=%s error=%s", pack_id, exc)

    # audit_events.resource_id is uuid — prefer marketplace asset id, else agent id.
    resource_id = (asset_id or "").strip() or agent_id
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_INTELLIGENCE_PACK_INSTALLED,
        resource_type="intelligence_pack",
        resource_id=resource_id,
        metadata={
            "agent_id": agent_id,
            "pack_id": pack_id,
            "assignment_count": len(created),
            "asset_id": asset_id,
        },
    )
    return {"pack_id": pack_id, "assignments": created, "count": len(created)}
