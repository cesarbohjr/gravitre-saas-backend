"""STA-39: PagerDuty incident → Jira ticket + Slack notify workflow template."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import Settings
from app.workflows.constants import SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEVOPS_WORKFLOW_SEED_LABEL = "workflow:devops-incident"
DEVOPS_WORKFLOW_NAME = "PagerDuty incident → Jira + Slack"
DEFAULT_JIRA_PROJECT_KEY = "ENG"
DEFAULT_SLACK_CHANNEL = "#eng-alerts"


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def devops_workflow_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{DEVOPS_WORKFLOW_SEED_LABEL}"))


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


def build_devops_incident_workflow_definition(
    *,
    jira_connector_id: str | None,
    slack_connector_id: str | None,
    jira_project_key: str = DEFAULT_JIRA_PROJECT_KEY,
    slack_channel: str = DEFAULT_SLACK_CHANNEL,
    jira_assignee_account_id: str | None = None,
    issue_type: str = "Incident",
) -> dict[str, Any]:
    """Executable workflow: Jira create → assign → Slack post."""
    steps: list[dict[str, Any]] = []

    if jira_connector_id:
        steps.append(
            {
                "id": "jira_create",
                "name": "Create Jira incident ticket",
                "type": "invoke_tool",
                "config": {
                    "action": "jira.issues.create",
                    "connector_id": jira_connector_id,
                    "param_sources": {
                        "project_key": jira_project_key,
                        "summary": "$jira_summary",
                        "description": "$jira_description",
                        "issue_type": issue_type,
                    },
                },
            }
        )
        if jira_assignee_account_id:
            steps.append(
                {
                    "id": "jira_assign",
                    "name": "Assign Jira ticket",
                    "type": "invoke_tool",
                    "config": {
                        "action": "jira.issues.assign",
                        "connector_id": jira_connector_id,
                        "param_sources": {
                            "issue_key": {"from_step": "jira_create", "path": ["issue", "key"]},
                            "account_id": jira_assignee_account_id,
                        },
                    },
                }
            )

    if slack_connector_id:
        steps.append(
            {
                "id": "slack_notify",
                "name": "Post Slack alert",
                "type": "slack_post_message",
                "config": {
                    "connector_id": slack_connector_id,
                    "channel": slack_channel,
                    "message_input_key": "slack_message",
                },
            }
        )

    if not steps:
        steps.append({"id": "noop", "name": "Awaiting Jira/Slack connectors", "type": "noop"})

    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def enrich_devops_incident_parameters(
    base: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Map PagerDuty trigger payload into Jira/Slack step parameters."""
    out = dict(base)
    cfg = (workflow.get("config") or {}).get("devops") or {}
    incident = base.get("incident") if isinstance(base.get("incident"), dict) else {}
    pd = base.get("pagerduty_event") if isinstance(base.get("pagerduty_event"), dict) else {}

    summary = (
        incident.get("summary")
        or pd.get("summary")
        or "PagerDuty incident"
    )
    incident_id = incident.get("id") or pd.get("incidentId") or ""
    urgency = incident.get("urgency") or pd.get("urgency") or ""
    html_url = incident.get("html_url") or pd.get("htmlUrl") or ""

    out["jira_summary"] = f"[PD] {summary}"
    desc_lines = [
        f"PagerDuty incident: {summary}",
        f"Incident ID: {incident_id}",
        f"Urgency: {urgency}",
    ]
    if html_url:
        desc_lines.append(f"Link: {html_url}")
    out["jira_description"] = "\n".join(line for line in desc_lines if line)

    channel = str(cfg.get("slack_channel") or DEFAULT_SLACK_CHANNEL)
    slack_message = f":rotating_light: *PagerDuty incident* — {summary}"
    if html_url:
        slack_message += f"\n<{html_url}|View in PagerDuty>"
    out["slack_message"] = slack_message
    out["channel"] = channel

    assignee = cfg.get("jira_assignee_account_id")
    if assignee:
        out["jira_assignee_account_id"] = str(assignee)
    return out


def ensure_devops_incident_workflow(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> str:
    """Upsert the DevOps incident workflow_def and UI workflow row."""
    workflow_id = devops_workflow_id(org_id)
    jira_id = _find_active_connector_id(client, org_id, "jira", environment_name=environment_name)
    slack_id = _find_active_connector_id(client, org_id, "slack", environment_name=environment_name)

    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings_row = (org_row.data or [{}])[0].get("settings") or {}
    onboarding = settings_row.get("onboarding") if isinstance(settings_row, dict) else {}
    devops_cfg = (onboarding.get("devops") if isinstance(onboarding, dict) else {}) or {}

    jira_project_key = str(devops_cfg.get("jira_project_key") or DEFAULT_JIRA_PROJECT_KEY)
    slack_channel = str(devops_cfg.get("slack_channel") or DEFAULT_SLACK_CHANNEL)
    jira_assignee = devops_cfg.get("jira_assignee_account_id")
    jira_assignee_str = str(jira_assignee) if jira_assignee else None

    definition = build_devops_incident_workflow_definition(
        jira_connector_id=jira_id,
        slack_connector_id=slack_id,
        jira_project_key=jira_project_key,
        slack_channel=slack_channel,
        jira_assignee_account_id=jira_assignee_str,
    )
    workflow_config = {
        "demo": True,
        "devops": {
            "jira_project_key": jira_project_key,
            "slack_channel": slack_channel,
            "jira_assignee_account_id": jira_assignee_str,
        },
    }

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": DEVOPS_WORKFLOW_NAME,
            "description": "On PagerDuty incident.triggered: create Jira ticket, assign owner, notify Slack.",
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
            "name": DEVOPS_WORKFLOW_NAME,
            "description": "PagerDuty incident triggers Jira ticket creation and Slack notification.",
            "status": "active",
            "environment": environment_name,
            "nodes": [
                {"id": "trigger", "type": "trigger", "name": "PagerDuty incident"},
                {"id": "jira", "type": "tool", "name": "Jira ticket"},
                {"id": "slack", "type": "tool", "name": "Slack notify"},
            ],
            "edges": [
                {"from": "trigger", "to": "jira"},
                {"from": "jira", "to": "slack"},
            ],
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    if isinstance(settings_row, dict):
        onboarding = dict(onboarding) if isinstance(onboarding, dict) else {}
        onboarding["demo_devops_workflow_id"] = workflow_id
        devops_onboarding = dict(devops_cfg)
        devops_onboarding.setdefault("jira_project_key", jira_project_key)
        devops_onboarding.setdefault("slack_channel", slack_channel)
        onboarding["devops"] = devops_onboarding
        settings_row["onboarding"] = onboarding
        client.table("organizations").update({"settings": settings_row}).eq("id", org_id).execute()

    logger.info(
        "devops_workflow_ensured org_id=%s workflow_id=%s jira=%s slack=%s",
        org_id,
        workflow_id,
        bool(jira_id),
        bool(slack_id),
    )
    return workflow_id


def ensure_pagerduty_devops_trigger(
    client: Any,
    org_id: str,
    pagerduty_connector_id: str,
    workflow_id: str,
) -> None:
    """Bind incident.triggered → DevOps workflow if not already configured."""
    from app.services.pagerduty_trigger_service import (
        get_pagerduty_triggers,
        set_pagerduty_triggers,
    )

    row = (
        client.table("connectors")
        .select("config")
        .eq("id", pagerduty_connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return
    connector = dict(row.data[0])
    triggers = get_pagerduty_triggers(connector)
    if any(
        str(t.get("workflow_id")) == workflow_id and t.get("event") in {"incident.triggered", "incident.trigger"}
        for t in triggers
    ):
        return

    triggers = list(triggers)
    triggers.append(
        {
            "id": str(uuid.uuid4()),
            "event": "incident.triggered",
            "workflow_id": workflow_id,
            "active": True,
            "label": "DevOps incident (STA-39)",
        }
    )
    set_pagerduty_triggers(client, org_id, pagerduty_connector_id, triggers)
    logger.info(
        "pagerduty_devops_trigger_installed org_id=%s connector_id=%s workflow_id=%s",
        org_id,
        pagerduty_connector_id,
        workflow_id,
    )


def on_pagerduty_connector_connected(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> None:
    """After PagerDuty OAuth: ensure DevOps workflow and default incident.triggered binding."""
    _ = settings
    try:
        workflow_id = ensure_devops_incident_workflow(client, org_id)
        ensure_pagerduty_devops_trigger(client, org_id, connector_id, workflow_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("devops_workflow_setup_failed org_id=%s error=%s", org_id, exc)
