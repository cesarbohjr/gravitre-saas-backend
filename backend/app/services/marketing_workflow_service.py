"""STA-42: GA4 + HubSpot → Marketing Agent summary → Slack workflow template."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.workflows.constants import SCHEMA_VERSION

logger = logging.getLogger(__name__)

MARKETING_WORKFLOW_SEED_LABEL = "workflow:marketing-attribution"
MARKETING_WORKFLOW_NAME = "GA4 + HubSpot → Marketing summary → Slack"
DEFAULT_SLACK_CHANNEL = "#marketing"

DEFAULT_GA4_DIMENSIONS = ["sessionCampaignName", "sessionDefaultChannelGroup"]
DEFAULT_GA4_METRICS = ["sessions", "conversions", "totalUsers"]

DEFAULT_HUBSPOT_FILTER_GROUPS = [
    {
        "filters": [
            {
                "propertyName": "lifecyclestage",
                "operator": "IN",
                "values": ["lead", "marketingqualifiedlead", "subscriber"],
            }
        ]
    }
]

DEFAULT_HUBSPOT_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "lifecyclestage",
    "hs_analytics_source",
    "hs_latest_source",
]

MARKETING_AGENT_TASK = (
    "Summarize GA4 campaign and channel performance alongside recent HubSpot leads. "
    "Highlight top campaigns, traffic trends, lead volume, source mix, and 2–3 recommended "
    "marketing actions. Keep the summary concise for a Slack channel post."
)


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def marketing_workflow_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{MARKETING_WORKFLOW_SEED_LABEL}"))


def marketing_agent_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), "gravitre-seed:agent:marketing"))


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


def build_marketing_attribution_workflow_definition(
    *,
    org_id: str,
    ga4_connector_id: str | None,
    hubspot_connector_id: str | None,
    slack_connector_id: str | None,
    slack_channel: str = DEFAULT_SLACK_CHANNEL,
) -> dict[str, Any]:
    """Executable workflow: GA4 report → HubSpot contacts → Marketing Agent → Slack."""
    steps: list[dict[str, Any]] = []
    agent_id = marketing_agent_id(org_id)

    if ga4_connector_id:
        steps.append(
            {
                "id": "ga4_report",
                "name": "Pull GA4 campaign report",
                "type": "invoke_tool",
                "config": {
                    "action": "analytics.reports.run",
                    "connector_id": ga4_connector_id,
                    "param_sources": {
                        "start_date": "$ga4_start_date",
                        "end_date": "$ga4_end_date",
                        "dimensions": DEFAULT_GA4_DIMENSIONS,
                        "metrics": DEFAULT_GA4_METRICS,
                    },
                },
            }
        )

    if hubspot_connector_id:
        steps.append(
            {
                "id": "hubspot_leads",
                "name": "Search recent HubSpot leads",
                "type": "invoke_tool",
                "config": {
                    "action": "hubspot.contacts.search",
                    "connector_id": hubspot_connector_id,
                    "param_sources": {
                        "filter_groups": DEFAULT_HUBSPOT_FILTER_GROUPS,
                        "properties": DEFAULT_HUBSPOT_PROPERTIES,
                        "limit": 25,
                    },
                },
            }
        )

    steps.append(
        {
            "id": "marketing_summary",
            "name": "Marketing attribution summary",
            "type": "agent",
            "metadata": {
                "agent_id": agent_id,
                "task": MARKETING_AGENT_TASK,
                "briefing_from_steps": True,
            },
        }
    )

    if slack_connector_id:
        steps.append(
            {
                "id": "slack_summary",
                "name": "Post summary to Slack",
                "type": "slack_post_message",
                "config": {
                    "connector_id": slack_connector_id,
                    "channel": slack_channel,
                    "message_from_step": {"from_step": "marketing_summary", "path": ["summary"]},
                },
            }
        )

    if len(steps) == 1:
        steps.insert(0, {"id": "noop", "name": "Awaiting GA4/HubSpot connectors", "type": "noop"})

    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def enrich_marketing_attribution_parameters(
    base: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Default GA4 date range and HubSpot filters for manual or scheduled runs."""
    out = dict(base)
    cfg = (workflow.get("config") or {}).get("marketing") or {}

    out.setdefault("ga4_start_date", str(cfg.get("ga4_start_date") or "7daysAgo"))
    out.setdefault("ga4_end_date", str(cfg.get("ga4_end_date") or "today"))

    if not out.get("hubspot_filter_groups"):
        week_ago_ms = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)
        out["hubspot_filter_groups"] = [
            {
                "filters": [
                    {
                        "propertyName": "lastmodifieddate",
                        "operator": "GTE",
                        "value": str(week_ago_ms),
                    }
                ]
            }
        ]

    channel = str(cfg.get("slack_channel") or DEFAULT_SLACK_CHANNEL)
    out.setdefault("channel", channel)
    return out


def ensure_marketing_attribution_workflow(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> str:
    """Upsert the marketing attribution workflow_def and UI workflow row."""
    workflow_id = marketing_workflow_id(org_id)
    ga4_id = _find_active_connector_id(client, org_id, "google_analytics", environment_name=environment_name)
    hubspot_id = _find_active_connector_id(client, org_id, "hubspot", environment_name=environment_name)
    slack_id = _find_active_connector_id(client, org_id, "slack", environment_name=environment_name)

    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings_row = (org_row.data or [{}])[0].get("settings") or {}
    onboarding = settings_row.get("onboarding") if isinstance(settings_row, dict) else {}
    marketing_cfg = (onboarding.get("marketing") if isinstance(onboarding, dict) else {}) or {}

    slack_channel = str(marketing_cfg.get("slack_channel") or DEFAULT_SLACK_CHANNEL)

    definition = build_marketing_attribution_workflow_definition(
        org_id=org_id,
        ga4_connector_id=ga4_id,
        hubspot_connector_id=hubspot_id,
        slack_connector_id=slack_id,
        slack_channel=slack_channel,
    )
    workflow_config = {
        "demo": True,
        "marketing": {
            "slack_channel": slack_channel,
            "ga4_start_date": "7daysAgo",
            "ga4_end_date": "today",
        },
    }

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": MARKETING_WORKFLOW_NAME,
            "description": (
                "Pull GA4 campaign metrics and recent HubSpot leads, summarize with the "
                "Marketing Agent, and post to Slack."
            ),
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
            "name": MARKETING_WORKFLOW_NAME,
            "description": "Weekly-style marketing attribution digest for campaign and lead performance.",
            "status": "active",
            "environment": environment_name,
            "nodes": [
                {"id": "trigger", "type": "trigger", "name": "Manual / scheduled"},
                {"id": "ga4", "type": "tool", "name": "GA4 report"},
                {"id": "hubspot", "type": "tool", "name": "HubSpot leads"},
                {"id": "agent", "type": "agent", "name": "Marketing summary"},
                {"id": "slack", "type": "tool", "name": "Slack post"},
            ],
            "edges": [
                {"from": "trigger", "to": "ga4"},
                {"from": "ga4", "to": "hubspot"},
                {"from": "hubspot", "to": "agent"},
                {"from": "agent", "to": "slack"},
            ],
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    if isinstance(settings_row, dict):
        onboarding = dict(onboarding) if isinstance(onboarding, dict) else {}
        onboarding["demo_marketing_workflow_id"] = workflow_id
        marketing_onboarding = dict(marketing_cfg)
        marketing_onboarding.setdefault("slack_channel", slack_channel)
        onboarding["marketing"] = marketing_onboarding
        settings_row["onboarding"] = onboarding
        client.table("organizations").update({"settings": settings_row}).eq("id", org_id).execute()

    logger.info(
        "marketing_workflow_ensured org_id=%s workflow_id=%s ga4=%s hubspot=%s slack=%s",
        org_id,
        workflow_id,
        bool(ga4_id),
        bool(hubspot_id),
        bool(slack_id),
    )
    return workflow_id


def on_marketing_connectors_updated(
    client: Any,
    org_id: str,
    settings: Settings,
) -> None:
    """After HubSpot or GA4 OAuth: refresh marketing attribution workflow definition."""
    _ = settings
    try:
        ensure_marketing_attribution_workflow(client, org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("marketing_workflow_setup_failed org_id=%s error=%s", org_id, exc)
