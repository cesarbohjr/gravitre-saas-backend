"""Shared models and aliases for chat connector execution."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

LIST_CREATE_INTENT = re.compile(
    r"\b(create|new|add|make)\s+(?:a\s+)?(?:contact\s+)?(?:list|group|segment)\b",
    re.I,
)

INTEGRATION_ALIASES: dict[str, tuple[str, ...]] = {
    "hubspot": ("hubspot", "crm"),
    "salesforce": ("salesforce", "sfdc"),
    "slack": ("slack",),
    "zendesk": ("zendesk", "support ticket", "support tickets"),
    "github": ("github", "gh", "pull request", "pull requests"),
    "jira": ("jira", "atlassian ticket"),
    "confluence": ("confluence", "wiki page", "wiki"),
    "monday": ("monday", "monday.com", "monday board"),
    "google_drive": ("google drive", "drive", "gdrive", "google sheet"),
    "google_sheets": ("google sheets", "spreadsheet", "sheet"),
    "google_docs": ("google docs", "google doc"),
    "google_calendar": ("google calendar", "calendar event", "calendar"),
    "gmail": ("gmail", "email", "send email", "send mail"),
    "microsoft365": ("microsoft 365", "m365", "outlook", "microsoft graph", "teams"),
    "microsoft_teams": ("teams", "microsoft teams"),
    "intercom": ("intercom",),
    "clickup": ("clickup", "click up"),
    "pipedrive": ("pipedrive",),
    "canva": ("canva", "design"),
    "figma": ("figma",),
    "stripe": ("stripe",),
    "pagerduty": ("pagerduty", "on-call", "oncall"),
    "quickbooks": ("quickbooks", "qbo"),
    "asana": ("asana",),
    "apollo": ("apollo", "apollo.io"),
    "notion": ("notion",),
    "odoo": ("odoo",),
    "netsuite": ("netsuite",),
    "workday": ("workday",),
    "constant_contact": ("constant contact",),
    "google_analytics": ("google analytics", "ga4", "analytics"),
}


@dataclass(frozen=True)
class ConnectorActionPlan:
    tool_name: str
    invoke_action: str
    integration: str
    kind: str
    label: str
    args: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    approval_reason: str | None = None
    destructive: bool = False
    inferred_fields: tuple[str, ...] = ()
    inference_sources: dict[str, str] = field(default_factory=dict)
