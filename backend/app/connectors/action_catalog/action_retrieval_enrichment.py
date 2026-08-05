"""Optional retrieval enrichment: synthetic examples + tags (G.5 Phase 4.2 sample).

Used for evaluation of whether embedding/mapper candidate accuracy improves
beyond Phase 4/F8 when/why descriptions. Not a full-catalog rollout — only the
15–20 sample actions below are enriched until evidence justifies expansion.
"""
from __future__ import annotations

from typing import Any

# Default OFF — G.5 Phase 4.2 A/B showed delta_correct=0 on the G.1 probe.
# Probe / eval flips this on; catalog-wide rollout declined.
ENRICHMENT_ENABLED: bool = False

# action_id -> {examples: [...], tags: [...]}
ACTION_RETRIEVAL_ENRICHMENT: dict[str, dict[str, Any]] = {
    # F4 object-confusable set
    "github.issues.list": {
        "examples": [
            "search GitHub issues mentioning billing",
            "list open issues in the repo about auth",
        ],
        "tags": ["issues", "bugs", "tickets", "search", "github"],
    },
    "github.pulls.list": {
        "examples": [
            "list open pull requests awaiting review",
            "show PRs that mention billing",
        ],
        "tags": ["pulls", "prs", "code-review", "github"],
    },
    "clickup.tasks.list": {
        "examples": [
            "list my open ClickUp tasks",
            "show ClickUp tasks assigned to me",
        ],
        "tags": ["tasks", "todos", "clickup", "list"],
    },
    "clickup.spaces.list": {
        "examples": [
            "list ClickUp spaces in the workspace",
            "show available ClickUp spaces",
        ],
        "tags": ["spaces", "workspace", "clickup"],
    },
    "salesforce.contacts.search": {
        "examples": [
            "find Salesforce contacts named Sarah",
            "search Salesforce for contact Sarah Smith",
        ],
        "tags": ["contacts", "people", "crm", "salesforce", "search"],
    },
    "salesforce.leads.search": {
        "examples": [
            "search Salesforce leads in California",
            "find open Salesforce leads about pricing",
        ],
        "tags": ["leads", "prospects", "crm", "salesforce"],
    },
    # Broader G.1 vendors
    "asana.tasks.create": {
        "examples": [
            "create a task in Asana called Follow up with Acme",
            "add an Asana task for the Acme follow-up",
        ],
        "tags": ["tasks", "create", "asana", "todo"],
    },
    "notion.pages.create": {
        "examples": [
            "create a Notion page titled Q3 plan",
            "make a new Notion doc for Q3 planning",
        ],
        "tags": ["pages", "docs", "notion", "create"],
    },
    "airtable.records.list": {
        "examples": [
            "find records in Airtable for Acme",
            "list Airtable rows matching Acme",
        ],
        "tags": ["records", "rows", "airtable", "search"],
    },
    "monday.items.create": {
        "examples": [
            "create a Monday.com item for onboarding",
            "add a Monday board item named onboarding",
        ],
        "tags": ["items", "boards", "monday", "create"],
    },
    "linear.issues.create": {
        "examples": [
            "create a Linear issue titled Fix login",
            "file a Linear bug: Fix login",
        ],
        "tags": ["issues", "bugs", "linear", "create"],
    },
    "zendesk.tickets.list": {
        "examples": [
            "list open Zendesk tickets",
            "show Zendesk support tickets that are open",
        ],
        "tags": ["tickets", "support", "zendesk", "list"],
    },
    "intercom.conversations.search": {
        "examples": [
            "search Intercom conversations about refund",
            "find Intercom chats mentioning refunds",
        ],
        "tags": ["conversations", "chat", "intercom", "search"],
    },
    "hubspot.contacts.search": {
        "examples": [
            "Search HubSpot for Acme contacts",
            "find HubSpot contacts at Acme",
        ],
        "tags": ["contacts", "crm", "hubspot", "search"],
    },
    "apollo.lists.create": {
        "examples": [
            "Create an Apollo contact list named MSP Prospects",
            "make a new Apollo list for outreach",
        ],
        "tags": ["lists", "labels", "apollo", "create"],
    },
    "gmail.messages.send": {
        "examples": [
            "Send an email to Stephanie about the proposal",
            "email Stephanie the proposal draft",
        ],
        "tags": ["email", "send", "gmail", "message"],
    },
    "slack.chat.postMessage": {
        "examples": [
            "post a Slack message to #ops about the deploy",
            "send Slack note to the ops channel",
        ],
        "tags": ["slack", "message", "notify", "chat"],
    },
    "hubspot.lists.create": {
        "examples": [
            "Create a HubSpot static list named MSPs",
            "make a HubSpot contact list called MSPs",
        ],
        "tags": ["lists", "segments", "hubspot", "create"],
    },
}


def enrichment_for_action(action_id: str | None) -> dict[str, Any] | None:
    if not ENRICHMENT_ENABLED:
        return None
    key = str(action_id or "").strip().lower()
    if not key:
        return None
    row = ACTION_RETRIEVAL_ENRICHMENT.get(key)
    return dict(row) if isinstance(row, dict) else None


def enrichment_document_suffix(action_id: str | None) -> str:
    if not ENRICHMENT_ENABLED:
        return ""
    row = enrichment_for_action(action_id)
    if not row:
        return ""
    parts: list[str] = []
    tags = row.get("tags") or []
    if isinstance(tags, list) and tags:
        parts.append("tags: " + ", ".join(str(t) for t in tags[:8]))
    examples = row.get("examples") or []
    if isinstance(examples, list) and examples:
        parts.append("examples: " + " | ".join(str(e) for e in examples[:2]))
    return " | ".join(parts)
