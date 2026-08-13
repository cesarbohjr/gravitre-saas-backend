"""Canonical capability ontology — abstract operator intents above the ActionSpec catalog."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CapabilityKind = Literal["read", "write", "advanced"]


@dataclass(frozen=True)
class VendorCapabilityBinding:
    """Maps a canonical capability to one vendor's catalog action."""

    vendor: str
    action_key: str
    label: str
    kind: CapabilityKind = "write"


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    label: str
    description: str
    domain: str
    kind: CapabilityKind
    bindings: tuple[VendorCapabilityBinding, ...]


CAPABILITY_REGISTRY: dict[str, CapabilityDefinition] = {
    "crm.contact.create": CapabilityDefinition(
        capability_id="crm.contact.create",
        label="Create CRM contact",
        description="Create a person/contact record in the customer's connected CRM.",
        domain="crm",
        kind="write",
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.contacts.create", "HubSpot contact"),
            VendorCapabilityBinding("salesforce", "salesforce.leads.create", "Salesforce lead"),
            VendorCapabilityBinding("pipedrive", "pipedrive.persons.create", "Pipedrive person"),
            VendorCapabilityBinding("engagebay", "engagebay.contacts.create", "EngageBay contact"),
        ),
    ),
    "crm.contact.search": CapabilityDefinition(
        capability_id="crm.contact.search",
        label="Search CRM contacts",
        description="Search people/contacts/leads in the customer's connected CRM.",
        domain="crm",
        kind="read",
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.contacts.search", "HubSpot contact search", kind="read"),
            VendorCapabilityBinding("salesforce", "salesforce.leads.search", "Salesforce lead search", kind="read"),
            VendorCapabilityBinding("pipedrive", "pipedrive.persons.search", "Pipedrive person search", kind="read"),
        ),
    ),
    "messaging.channel.post": CapabilityDefinition(
        capability_id="messaging.channel.post",
        label="Post channel message",
        description="Send a message to a team channel in the customer's connected chat system.",
        domain="messaging",
        kind="write",
        bindings=(
            VendorCapabilityBinding("slack", "slack.post_message", "Slack message"),
            VendorCapabilityBinding("microsoft_teams", "microsoft_teams.messages.send", "Teams message"),
        ),
    ),
    "email.send": CapabilityDefinition(
        capability_id="email.send",
        label="Send email",
        description="Send an email via the customer's connected mail provider.",
        domain="communication",
        kind="write",
        bindings=(
            VendorCapabilityBinding("gmail", "gmail.messages.send", "Gmail message"),
            VendorCapabilityBinding("sendgrid", "sendgrid.mail.send", "SendGrid mail"),
            VendorCapabilityBinding("outlook", "outlook.messages.send", "Outlook message"),
        ),
    ),
    "calendar.event.create": CapabilityDefinition(
        capability_id="calendar.event.create",
        label="Create calendar event",
        description="Create a calendar event in the customer's connected calendar.",
        domain="calendar",
        kind="write",
        bindings=(
            VendorCapabilityBinding("google_calendar", "google_calendar.events.create", "Google Calendar event"),
            VendorCapabilityBinding(
                "microsoft365",
                "microsoft365.calendar.events.create",
                "Microsoft 365 calendar event",
            ),
        ),
    ),
    "document.search": CapabilityDefinition(
        capability_id="document.search",
        label="Search documents",
        description="Search files or pages in the customer's connected document store.",
        domain="documents",
        kind="read",
        bindings=(
            VendorCapabilityBinding("google_drive", "google_drive.search_files", "Google Drive search", kind="read"),
            VendorCapabilityBinding("notion", "notion.search_files", "Notion workspace search", kind="read"),
        ),
    ),
    "analytics.query": CapabilityDefinition(
        capability_id="analytics.query",
        label="Run analytics query",
        description="Query analytics/reporting data from the customer's connected analytics tool.",
        domain="analytics",
        kind="read",
        bindings=(
            VendorCapabilityBinding(
                "google_analytics",
                "google_analytics.reports.run",
                "GA4 report",
                kind="read",
            ),
        ),
    ),
    "payment.refund": CapabilityDefinition(
        capability_id="payment.refund",
        label="Issue payment refund",
        description="Refund a payment via the customer's connected payments provider.",
        domain="payments",
        kind="write",
        bindings=(
            VendorCapabilityBinding("stripe", "stripe.refunds.create", "Stripe refund"),
        ),
    ),
}


def get_capability(capability_id: str) -> CapabilityDefinition | None:
    return CAPABILITY_REGISTRY.get(str(capability_id or "").strip().lower())


def list_capability_ids() -> list[str]:
    return sorted(CAPABILITY_REGISTRY.keys())
