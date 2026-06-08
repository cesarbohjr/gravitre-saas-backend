"""Shared helpers for vertical-pack workflows — active versions + execute params."""
from __future__ import annotations

import uuid
from typing import Any

from app.workflows.constants import SCHEMA_VERSION
from app.workflows.repository import (
    create_workflow_version,
    get_next_workflow_version_number,
    set_active_workflow_version,
)


def _demo_approval_policy_id(org_id: str, workflow_id: str) -> str:
    try:
        namespace = uuid.UUID(org_id)
    except ValueError:
        namespace = uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")
    return str(uuid.uuid5(namespace, f"approval-policy:{workflow_id}"))


def ensure_demo_execute_policy(
    client: Any,
    org_id: str,
    workflow_id: str,
    *,
    actor_id: str | None = None,
) -> None:
    """Let vertical-pack demo workflows execute without the paid approvals feature."""
    client.table("approval_policies").upsert(
        {
            "id": _demo_approval_policy_id(org_id, workflow_id),
            "org_id": org_id,
            "workflow_id": workflow_id,
            "run_types": ["execute"],
            "required_approvals": 0,
            "approver_roles": ["admin"],
            "created_by": actor_id,
        },
        on_conflict="org_id,workflow_id",
    ).execute()


def ensure_active_workflow_version(
    client: Any,
    org_id: str,
    workflow_id: str,
    definition: dict[str, Any],
    *,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> str:
    """Create and activate a workflow version so /execute can run vertical-pack defs."""
    version_number = get_next_workflow_version_number(client, org_id, workflow_id, environment_name)
    version_row = create_workflow_version(
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        environment_name=environment_name,
        version=version_number,
        definition=definition,
        schema_version=definition.get("schema_version") or SCHEMA_VERSION,
        created_by=actor_id,
    )
    version_id = str(version_row["id"])
    set_active_workflow_version(
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        environment_name=environment_name,
        version_id=version_id,
        updated_by=actor_id,
    )
    ensure_demo_execute_policy(client, org_id, workflow_id, actor_id=actor_id)
    return version_id


def enrich_vertical_workflow_parameters(
    org_id: str,
    workflow_id: str,
    parameters: dict[str, Any],
    workflow_row: dict[str, Any],
) -> dict[str, Any]:
    """Apply vertical-pack default parameters before workflow execute."""
    from app.services.devops_workflow_service import devops_workflow_id, enrich_devops_incident_parameters
    from app.services.healthcare_vertical_service import (
        enrich_prior_auth_parameters,
        prior_auth_workflow_id,
    )
    from app.services.legal_vertical_service import enrich_intake_parameters, intake_workflow_id
    from app.services.marketing_workflow_service import (
        enrich_marketing_attribution_parameters,
        marketing_workflow_id,
    )
    from app.services.real_estate_vertical_service import enrich_listing_parameters, listing_workflow_id

    if workflow_id == prior_auth_workflow_id(org_id):
        return enrich_prior_auth_parameters(parameters, workflow_row)
    if workflow_id == intake_workflow_id(org_id):
        return enrich_intake_parameters(parameters, workflow_row)
    if workflow_id == listing_workflow_id(org_id):
        return enrich_listing_parameters(parameters, workflow_row)
    if workflow_id == devops_workflow_id(org_id):
        return enrich_devops_incident_parameters(parameters, workflow_row)
    if workflow_id == marketing_workflow_id(org_id):
        return enrich_marketing_attribution_parameters(parameters, workflow_row)
    return parameters
