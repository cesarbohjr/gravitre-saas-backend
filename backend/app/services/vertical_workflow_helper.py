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


def _is_msp_enrichment_workflow(workflow_row: dict[str, Any]) -> bool:
    config = workflow_row.get("config") if isinstance(workflow_row.get("config"), dict) else {}
    slug = str(
        config.get("workflow_slug")
        or config.get("marketplaceSlug")
        or config.get("marketplace_slug")
        or ""
    ).strip()
    if slug == "msp-prospects-clay-hubspot-enrichment":
        return True
    name = str(workflow_row.get("name") or "").lower()
    return "clay" in name and "hubspot" in name and ("enrich" in name or "msp" in name)


def _merge_install_var_keys(out: dict[str, Any], source: dict[str, Any] | None) -> None:
    if not isinstance(source, dict):
        return
    for key in ("HUBSPOT_LIST_ID", "HUBSPOT_LIST_NAME", "APOLLO_LIST_NAME"):
        if not out.get(key) and source.get(key):
            out[key] = source[key]


def enrich_msp_enrichment_parameters(
    parameters: dict[str, Any],
    workflow_row: dict[str, Any],
    *,
    client: Any | None = None,
    org_id: str | None = None,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Inject HubSpot connector id + install vars for Clay→HubSpot enrichment runs."""
    out = dict(parameters or {})
    config = workflow_row.get("config") if isinstance(workflow_row.get("config"), dict) else {}
    _merge_install_var_keys(out, config.get("install_variables") if isinstance(config.get("install_variables"), dict) else None)
    _merge_install_var_keys(out, config.get("installVariables") if isinstance(config.get("installVariables"), dict) else None)

    if client is not None and org_id and not out.get("HUBSPOT_LIST_ID"):
        try:
            workflow_id = str(workflow_row.get("id") or "").strip()
            query = (
                client.table("marketplace_installs")
                .select("install_variables, installed_entity_id")
                .eq("org_id", org_id)
                .eq("status", "active")
                .limit(20)
            )
            rows = query.execute()
            for row in rows.data or []:
                if workflow_id and str(row.get("installed_entity_id") or "") != workflow_id:
                    continue
                _merge_install_var_keys(out, row.get("install_variables") if isinstance(row.get("install_variables"), dict) else None)
                if out.get("HUBSPOT_LIST_ID"):
                    break
            if not out.get("HUBSPOT_LIST_ID"):
                # Fallback: any active install that declared the list id.
                for row in rows.data or []:
                    _merge_install_var_keys(
                        out,
                        row.get("install_variables") if isinstance(row.get("install_variables"), dict) else None,
                    )
                    if out.get("HUBSPOT_LIST_ID"):
                        break
        except Exception:  # noqa: BLE001
            pass

    if out.get("hubspot_connector_id") or out.get("hubspotConnectorId"):
        out.setdefault("hubspot_connector_id", out.get("hubspot_connector_id") or out.get("hubspotConnectorId"))
    elif client is not None and org_id:
        try:
            from app.connectors.repository import get_connector_by_type

            row = get_connector_by_type(client, org_id, "hubspot", environment_name=environment_name)
            if row and row.get("id"):
                out["hubspot_connector_id"] = str(row["id"])
        except Exception:  # noqa: BLE001
            pass
    return out


def enrich_vertical_workflow_parameters(
    org_id: str,
    workflow_id: str,
    parameters: dict[str, Any],
    workflow_row: dict[str, Any],
    *,
    client: Any | None = None,
    environment_name: str = "production",
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
    if _is_msp_enrichment_workflow(workflow_row):
        return enrich_msp_enrichment_parameters(
            parameters,
            workflow_row,
            client=client,
            org_id=org_id,
            environment_name=environment_name,
        )
    return parameters
