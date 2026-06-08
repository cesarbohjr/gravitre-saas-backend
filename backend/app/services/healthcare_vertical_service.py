"""Healthcare vertical pack — FHIR sandbox, agents, prior-auth workflow (STA-113)."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.connectors.fhir import FHIR_SANDBOX_BASE_URL
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.vertical_workflow_helper import ensure_active_workflow_version
from app.workflows.audit import write_audit_event
from app.workflows.constants import SCHEMA_VERSION

logger = logging.getLogger(__name__)

HEALTHCARE_WORKFLOW_SEED_LABEL = "workflow:healthcare-prior-auth"
PRIOR_AUTH_WORKFLOW_NAME = "Referral → prior authorization checklist"
FHIR_SANDBOX_CONNECTOR_NAME = "FHIR Sandbox (HAPI R4)"

CLINICAL_ADMIN_TASK = (
    "Review the FHIR patient and appointment context for this referral. Summarize clinical "
    "documentation gaps and payer-specific requirements for prior authorization."
)

AUDIT_HEALTHCARE_INSTALLED = "vertical.healthcare.installed"


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def _seed_id(org_id: str, label: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{label}"))


def prior_auth_workflow_id(org_id: str) -> str:
    return _seed_id(org_id, HEALTHCARE_WORKFLOW_SEED_LABEL)


def clinical_admin_agent_id(org_id: str) -> str:
    return _seed_id(org_id, "agent:clinical-admin")


def patient_services_agent_id(org_id: str) -> str:
    return _seed_id(org_id, "agent:patient-services")


def fhir_sandbox_connector_id(org_id: str) -> str:
    return _seed_id(org_id, "connector:fhir-sandbox")


def _find_active_connector_id(
    client: Any,
    org_id: str,
    connector_type: str,
    *,
    environment_name: str = "production",
) -> str | None:
    result = (
        client.table("connectors")
        .select("id")
        .eq("org_id", org_id)
        .eq("type", connector_type)
        .eq("status", "active")
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not result.data:
        result = (
            client.table("connectors")
            .select("id")
            .eq("org_id", org_id)
            .eq("type", connector_type)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
    if not result.data:
        return None
    return str(result.data[0]["id"])


def build_prior_auth_workflow_definition(
    *,
    org_id: str,
    fhir_connector_id: str | None,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    if fhir_connector_id:
        steps.extend(
            [
                {
                    "id": "patient_search",
                    "name": "Find patient in FHIR",
                    "type": "invoke_tool",
                    "config": {
                        "action": "fhir.patients.search",
                        "connector_id": fhir_connector_id,
                        "param_sources": {
                            "name": "$patient_name",
                            "birthdate": "$patient_birthdate",
                            "count": 5,
                        },
                    },
                },
                {
                    "id": "appointment_search",
                    "name": "List patient appointments",
                    "type": "invoke_tool",
                    "config": {
                        "action": "fhir.appointments.search",
                        "connector_id": fhir_connector_id,
                        "param_sources": {
                            "patient_id": "$patient_id",
                            "count": 10,
                        },
                    },
                },
            ]
        )

    steps.append(
        {
            "id": "clinical_review",
            "name": "Clinical admin review",
            "type": "agent",
            "metadata": {
                "agent_id": clinical_admin_agent_id(org_id),
                "task": CLINICAL_ADMIN_TASK,
                "briefing_from_steps": True,
            },
        }
    )

    if fhir_connector_id:
        steps.append(
            {
                "id": "prior_auth_checklist",
                "name": "Generate prior auth checklist",
                "type": "invoke_tool",
                "config": {
                    "action": "fhir.prior_auth.checklist",
                    "connector_id": fhir_connector_id,
                    "param_sources": {
                        "patient_id": "$patient_id",
                        "referral_reason": "$referral_reason",
                        "payer": "$payer",
                    },
                },
            }
        )
    else:
        steps.append({"id": "await_fhir", "name": "Awaiting FHIR connector", "type": "noop"})

    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def enrich_prior_auth_parameters(base: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    cfg = (workflow.get("config") or {}).get("healthcare") or {}
    out.setdefault("patient_name", cfg.get("demo_patient_name") or "Smith")
    out.setdefault("patient_birthdate", cfg.get("demo_patient_birthdate") or "1970-01-01")
    out.setdefault("patient_id", base.get("patient_id") or cfg.get("demo_patient_id") or "example")
    out.setdefault("referral_reason", base.get("referral_reason") or "Specialist referral")
    out.setdefault("payer", base.get("payer") or cfg.get("payer") or "Medicare")
    return out


def ensure_fhir_sandbox_connector(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> str:
    connector_id = fhir_sandbox_connector_id(org_id)
    row = {
        "id": connector_id,
        "org_id": org_id,
        "name": FHIR_SANDBOX_CONNECTOR_NAME,
        "vendor": "fhir",
        "type": "fhir",
        "description": "Public HAPI FHIR R4 sandbox for healthcare vertical demos.",
        "status": "active",
        "environment": environment_name,
        "phi_capable": True,
        "config": {
            "base_url": FHIR_SANDBOX_BASE_URL,
            "sandbox": True,
        },
        "docs_url": "https://hapi.fhir.org/baseR4/metadata",
    }
    client.table("connectors").upsert(row, on_conflict="id").execute()
    logger.info("fhir_sandbox_connector_ensured org_id=%s connector_id=%s", org_id, connector_id)
    return connector_id


def ensure_healthcare_agents(client: Any, org_id: str, *, actor_id: str | None = None) -> dict[str, str]:
    clinical_id = clinical_admin_agent_id(org_id)
    cs_id = patient_services_agent_id(org_id)
    agents = [
        {
            "id": clinical_id,
            "org_id": org_id,
            "name": "Clinical Admin Agent",
            "purpose": "Supports prior authorization workflows with FHIR clinical context and documentation checklists.",
            "role": "Clinical Operations",
            "department": "Healthcare",
            "model": "claude-sonnet-4-6",
            "capabilities": ["prior-auth", "fhir-read", "clinical-documentation"],
            "systems": ["fhir"],
            "guardrails": ["hipaa-required", "human-approval-for-submission"],
            "config": {"demo": True, "vertical": "healthcare", "type": "clinical_admin"},
            "status": "active",
        },
        {
            "id": cs_id,
            "org_id": org_id,
            "name": "Patient Services Agent",
            "purpose": "Answers scheduling questions and routes referrals using read-only FHIR appointment data.",
            "role": "Patient Services",
            "department": "Healthcare",
            "model": "gpt-4.1",
            "capabilities": ["appointment-lookup", "referral-intake", "patient-communication"],
            "systems": ["fhir"],
            "guardrails": ["hipaa-required", "no-clinical-advice"],
            "config": {"demo": True, "vertical": "healthcare", "type": "patient_services"},
            "status": "active",
        },
    ]
    client.table("agents").upsert(agents, on_conflict="id").execute()
    for agent in agents:
        upsert_agent_tool_permission(
            client,
            org_id,
            str(agent["id"]),
            connector_id=None,
            connector_type="fhir",
            scopes=default_demo_scopes_for_system("fhir"),
            granted_by=actor_id,
        )
    return {"clinicalAdminAgentId": clinical_id, "patientServicesAgentId": cs_id}


def ensure_prior_auth_workflow(
    client: Any,
    org_id: str,
    *,
    fhir_connector_id: str | None,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> str:
    workflow_id = prior_auth_workflow_id(org_id)
    definition = build_prior_auth_workflow_definition(org_id=org_id, fhir_connector_id=fhir_connector_id)
    workflow_config = {
        "demo": True,
        "healthcare": {
            "demo_patient_name": "Smith",
            "demo_patient_birthdate": "1970-01-01",
            "demo_patient_id": "example",
            "payer": "Medicare",
        },
    }

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": PRIOR_AUTH_WORKFLOW_NAME,
            "description": "Lookup FHIR patient/appointments, clinical admin review, prior auth checklist.",
            "status": "active",
            "schema_version": SCHEMA_VERSION,
            "definition": definition,
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    client.table("workflows").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": PRIOR_AUTH_WORKFLOW_NAME,
            "description": "Referral intake through prior authorization checklist generation.",
            "status": "active",
            "environment": environment_name,
            "nodes": [
                {"id": "trigger", "type": "trigger", "name": "Referral received"},
                {"id": "fhir", "type": "tool", "name": "FHIR lookup"},
                {"id": "clinical", "type": "agent", "name": "Clinical admin"},
                {"id": "checklist", "type": "tool", "name": "Prior auth checklist"},
            ],
            "edges": [
                {"from": "trigger", "to": "fhir"},
                {"from": "fhir", "to": "clinical"},
                {"from": "clinical", "to": "checklist"},
            ],
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()
    ensure_active_workflow_version(
        client,
        org_id,
        workflow_id,
        definition,
        environment_name=environment_name,
        actor_id=actor_id,
    )
    return workflow_id


def get_healthcare_vertical_status(client: Any, org_id: str) -> dict[str, Any]:
    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = (org_row.data or [{}])[0].get("settings") or {}
    healthcare = settings.get("healthcare") if isinstance(settings.get("healthcare"), dict) else {}
    fhir_id = healthcare.get("fhirConnectorId") or _find_active_connector_id(client, org_id, "fhir")
    return {
        "installed": bool(healthcare.get("installed")),
        "installedAt": healthcare.get("installedAt"),
        "fhirConnectorId": fhir_id,
        "priorAuthWorkflowId": healthcare.get("priorAuthWorkflowId") or prior_auth_workflow_id(org_id),
        "clinicalAdminAgentId": healthcare.get("clinicalAdminAgentId") or clinical_admin_agent_id(org_id),
        "patientServicesAgentId": healthcare.get("patientServicesAgentId") or patient_services_agent_id(org_id),
        "hipaaRequired": True,
        "sandboxBaseUrl": FHIR_SANDBOX_BASE_URL,
    }


def install_healthcare_vertical_pack(
    client: Any,
    org_id: str,
    *,
    actor_id: str,
    environment_name: str = "production",
) -> dict[str, Any]:
    from datetime import datetime, timezone

    fhir_connector_id = ensure_fhir_sandbox_connector(
        client, org_id, environment_name=environment_name, actor_id=actor_id
    )
    agents = ensure_healthcare_agents(client, org_id, actor_id=actor_id)
    workflow_id = ensure_prior_auth_workflow(
        client,
        org_id,
        fhir_connector_id=fhir_connector_id,
        environment_name=environment_name,
        actor_id=actor_id,
    )

    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = dict((org_row.data or [{}])[0].get("settings") or {})
    now = datetime.now(timezone.utc).isoformat()
    settings["healthcare"] = {
        "installed": True,
        "installedAt": now,
        "installedBy": actor_id,
        "fhirConnectorId": fhir_connector_id,
        "priorAuthWorkflowId": workflow_id,
        "clinicalAdminAgentId": agents["clinicalAdminAgentId"],
        "patientServicesAgentId": agents["patientServicesAgentId"],
    }
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_HEALTHCARE_INSTALLED,
        resource_type="organization",
        resource_id=org_id,
        metadata={
            "fhirConnectorId": fhir_connector_id,
            "priorAuthWorkflowId": workflow_id,
        },
    )
    logger.info(
        "healthcare_vertical_installed org_id=%s workflow_id=%s fhir=%s",
        org_id,
        workflow_id,
        fhir_connector_id,
    )
    return {
        "installed": True,
        "installedAt": now,
        "fhirConnectorId": fhir_connector_id,
        "priorAuthWorkflowId": workflow_id,
        "clinicalAdminAgentId": agents["clinicalAdminAgentId"],
        "patientServicesAgentId": agents["patientServicesAgentId"],
        "hipaaRequired": True,
        "sandboxBaseUrl": FHIR_SANDBOX_BASE_URL,
    }
