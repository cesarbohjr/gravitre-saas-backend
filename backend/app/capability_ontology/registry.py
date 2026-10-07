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
    # Planner-only capabilities are composed by the objective planner and
    # Outcome Pack workflows; they are not injected as chat tools.
    chat_tool: bool = True


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
    "analytics.traffic_overview": CapabilityDefinition(
        capability_id="analytics.traffic_overview",
        label="Website traffic overview",
        description=(
            "Broad website-traffic summary from connected analytics — users, sessions, "
            "views, source mix, and period-over-period change without asking the user "
            "to design API queries. Search Console is an optional companion when connected."
        ),
        domain="analytics",
        kind="read",
        bindings=(
            VendorCapabilityBinding(
                "google_analytics",
                "google_analytics.reports.run",
                "GA4 traffic overview",
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
    "search.performance": CapabilityDefinition(
        capability_id="search.performance",
        label="Search performance",
        description="Read search impressions, clicks, and page performance from Search Console.",
        domain="analytics",
        kind="read",
        bindings=(
            VendorCapabilityBinding(
                "google_search_console",
                "google_search_console.searchAnalytics.query",
                "GSC search analytics",
                kind="read",
            ),
        ),
    ),
    "crm.deals.read": CapabilityDefinition(
        capability_id="crm.deals.read",
        label="Read CRM deals",
        description="Search or list high-value deals in the customer's connected CRM.",
        domain="crm",
        kind="read",
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.deals.search", "HubSpot deals", kind="read"),
        ),
    ),
    "finance.invoices.read": CapabilityDefinition(
        capability_id="finance.invoices.read",
        label="Read invoices",
        description="List invoices from the customer's connected finance system.",
        domain="finance",
        kind="read",
        bindings=(
            VendorCapabilityBinding(
                "quickbooks",
                "quickbooks.invoices.list",
                "QuickBooks invoices",
                kind="read",
            ),
            VendorCapabilityBinding("xero", "xero.invoices.list", "Xero invoices", kind="read"),
            VendorCapabilityBinding("netsuite", "netsuite.invoices.list", "NetSuite invoices", kind="read"),
            VendorCapabilityBinding("stripe", "stripe.invoices.list", "Stripe invoices", kind="read"),
        ),
    ),
    "support.tickets.read": CapabilityDefinition(
        capability_id="support.tickets.read",
        label="Read support tickets",
        description="List tickets from the customer's connected support system.",
        domain="support",
        kind="read",
        bindings=(
            VendorCapabilityBinding("zendesk", "zendesk.tickets.list", "Zendesk tickets", kind="read"),
        ),
    ),

    # --- Planner capabilities (objective planner + Outcome Pack workflows) ---
    # Each lists every eligible provider as an OR alternative. Vendor
    # "gravitre" is a built-in resource (no customer connection required).
    "prospect.discovery": CapabilityDefinition(
        capability_id="prospect.discovery",
        label="Discover prospects",
        description="Find people who match an ideal customer profile.",
        domain="prospecting",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("apollo", "apollo.people.search", "Apollo people search", kind="read"),
            VendorCapabilityBinding("pdl", "pdl.person.identify", "People Data Labs identify", kind="read"),
            VendorCapabilityBinding("clay", "clay.people.enrich", "Clay people search", kind="read"),
            VendorCapabilityBinding("linkedin", "linkedin.prospect.enrich", "LinkedIn prospect", kind="read"),
            VendorCapabilityBinding("gravitre", "gravitre.web.research", "Web research", kind="read"),
        ),
    ),
    "company.discovery": CapabilityDefinition(
        capability_id="company.discovery",
        label="Discover target accounts",
        description="Find companies that match an ideal customer profile.",
        domain="prospecting",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("apollo", "apollo.organizations.search", "Apollo company search", kind="read"),
            VendorCapabilityBinding("pdl", "pdl.company.enrich", "People Data Labs company", kind="read"),
            VendorCapabilityBinding("clay", "clay.companies.enrich", "Clay company search", kind="read"),
            VendorCapabilityBinding("hubspot", "hubspot.companies.search", "HubSpot companies", kind="read"),
            VendorCapabilityBinding("gravitre", "gravitre.web.research", "Web research", kind="read"),
        ),
    ),
    "prospect.enrichment": CapabilityDefinition(
        capability_id="prospect.enrichment",
        label="Enrich prospects",
        description="Verify and enrich a person's role, company and contact details.",
        domain="prospecting",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("apollo", "apollo.people.match", "Apollo match", kind="read"),
            VendorCapabilityBinding("pdl", "pdl.person.enrich", "People Data Labs enrich", kind="read"),
            VendorCapabilityBinding("clay", "clay.people.enrich", "Clay enrich", kind="read"),
            VendorCapabilityBinding("gravitre", "gravitre.web.research", "Web research", kind="read"),
        ),
    ),
    "crm.contact.read": CapabilityDefinition(
        capability_id="crm.contact.read",
        label="Read CRM contact",
        description="Read one contact or lead from the connected CRM.",
        domain="crm",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.contacts.get", "HubSpot contact", kind="read"),
            VendorCapabilityBinding("salesforce", "salesforce.leads.get", "Salesforce lead", kind="read"),
            VendorCapabilityBinding("pipedrive", "pipedrive.persons.get", "Pipedrive person", kind="read"),
        ),
    ),
    "crm.contact.update": CapabilityDefinition(
        capability_id="crm.contact.update",
        label="Update CRM contact",
        description="Update a contact or lead in the connected CRM.",
        domain="crm",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.contacts.update", "HubSpot contact"),
            VendorCapabilityBinding("salesforce", "salesforce.leads.update", "Salesforce lead"),
            VendorCapabilityBinding("pipedrive", "pipedrive.persons.update", "Pipedrive person"),
        ),
    ),
    "crm.company.update": CapabilityDefinition(
        capability_id="crm.company.update",
        label="Update CRM company",
        description="Update an account or company record in the connected CRM.",
        domain="crm",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.companies.update", "HubSpot company"),
            VendorCapabilityBinding("salesforce", "salesforce.accounts.update", "Salesforce account"),
        ),
    ),
    "crm.deal.read": CapabilityDefinition(
        capability_id="crm.deal.read",
        label="Read CRM deal",
        description="Read one deal or opportunity from the connected CRM.",
        domain="crm",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.deals.get", "HubSpot deal", kind="read"),
            VendorCapabilityBinding("salesforce", "salesforce.opportunities.get", "Salesforce opportunity", kind="read"),
            VendorCapabilityBinding("pipedrive", "pipedrive.deals.get", "Pipedrive deal", kind="read"),
        ),
    ),
    "crm.deal.create": CapabilityDefinition(
        capability_id="crm.deal.create",
        label="Create CRM deal",
        description="Create a deal or opportunity in the connected CRM.",
        domain="crm",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.deals.create", "HubSpot deal"),
            VendorCapabilityBinding("salesforce", "salesforce.opportunities.create", "Salesforce opportunity"),
            VendorCapabilityBinding("pipedrive", "pipedrive.deals.create", "Pipedrive deal"),
        ),
    ),
    "crm.deal.update": CapabilityDefinition(
        capability_id="crm.deal.update",
        label="Update CRM deal",
        description="Update a deal or opportunity stage or fields in the connected CRM.",
        domain="crm",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.deals.update", "HubSpot deal"),
            VendorCapabilityBinding("salesforce", "salesforce.opportunities.update", "Salesforce opportunity"),
            VendorCapabilityBinding("pipedrive", "pipedrive.deals.update", "Pipedrive deal"),
        ),
    ),
    "crm.pipeline.read": CapabilityDefinition(
        capability_id="crm.pipeline.read",
        label="Read CRM pipeline",
        description="Page through deals or opportunities in the connected CRM.",
        domain="crm",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.deals.search", "HubSpot deals", kind="read"),
            VendorCapabilityBinding("salesforce", "salesforce.query", "Salesforce SOQL", kind="read"),
            VendorCapabilityBinding("pipedrive", "pipedrive.deals.list", "Pipedrive deals", kind="read"),
        ),
    ),
    "crm.meeting.read": CapabilityDefinition(
        capability_id="crm.meeting.read",
        label="Read booked meetings",
        description="Read meetings booked with contacts in the connected CRM.",
        domain="crm",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.meetings.search", "HubSpot meetings", kind="read"),
        ),
    ),
    "crm.task.create": CapabilityDefinition(
        capability_id="crm.task.create",
        label="Create follow-up task",
        description="Create a follow-up task or note for a seller in the connected CRM.",
        domain="crm",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.notes.create", "HubSpot note"),
            VendorCapabilityBinding("salesforce", "salesforce.tasks.create", "Salesforce task"),
            VendorCapabilityBinding("apollo", "apollo.tasks.create", "Apollo task"),
        ),
    ),
    "outreach.sequence.enroll": CapabilityDefinition(
        capability_id="outreach.sequence.enroll",
        label="Enroll in outreach sequence",
        description="Enroll an approved contact in an email outreach sequence.",
        domain="outreach",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.sequences.enroll", "HubSpot sequence"),
            VendorCapabilityBinding("apollo", "apollo.sequences.add", "Apollo sequence"),
        ),
    ),
    "outreach.activity.read": CapabilityDefinition(
        capability_id="outreach.activity.read",
        label="Read outreach activity",
        description="Read delivered emails and replies for a contact.",
        domain="outreach",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("hubspot", "hubspot.contacts.outreach", "HubSpot email activity", kind="read"),
            VendorCapabilityBinding("hubspot", "hubspot.emails.search", "HubSpot emails", kind="read"),
            VendorCapabilityBinding("gmail", "gmail.messages.list", "Gmail messages", kind="read"),
        ),
    ),
    "web.research": CapabilityDefinition(
        capability_id="web.research",
        label="Web research",
        description="Research public web sources for companies, people and topics.",
        domain="research",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("gravitre", "gravitre.web.research", "Web research", kind="read"),
        ),
    ),
    "seo.keyword_research": CapabilityDefinition(
        capability_id="seo.keyword_research",
        label="Keyword research",
        description="Find keyword demand and ranking opportunities.",
        domain="seo",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("semrush", "semrush.keywords.list", "Semrush keywords", kind="read"),
            VendorCapabilityBinding("ahrefs", "ahrefs.keywords.list", "Ahrefs keywords", kind="read"),
            VendorCapabilityBinding(
                "google_search_console",
                "google_search_console.searchAnalytics.query",
                "Search Console queries",
                kind="read",
            ),
        ),
    ),
    "seo.competitor_analysis": CapabilityDefinition(
        capability_id="seo.competitor_analysis",
        label="SEO competitor analysis",
        description="Compare organic visibility against competitors.",
        domain="seo",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("semrush", "semrush.competitors.compare", "Semrush competitors", kind="read"),
            VendorCapabilityBinding("ahrefs", "ahrefs.competitors.compare", "Ahrefs competitors", kind="read"),
            VendorCapabilityBinding("gravitre", "gravitre.web.research", "Web research", kind="read"),
        ),
    ),
    "seo.rank_tracking": CapabilityDefinition(
        capability_id="seo.rank_tracking",
        label="Track rankings",
        description="Start tracking rankings for target keywords.",
        domain="seo",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("semrush", "semrush.position_tracking.add", "Semrush tracking"),
            VendorCapabilityBinding("ahrefs", "ahrefs.rank_tracker.add", "Ahrefs rank tracker"),
        ),
    ),
    "seo.page_performance": CapabilityDefinition(
        capability_id="seo.page_performance",
        label="Page search performance",
        description="Read clicks, impressions and position for one page from Search Console.",
        domain="seo",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding(
                "google_search_console",
                "google_search_console.searchAnalytics.query",
                "Search Console page performance",
                kind="read",
            ),
        ),
    ),
    "support.ticket.read": CapabilityDefinition(
        capability_id="support.ticket.read",
        label="Read service ticket",
        description="Read one ticket with SLA and resolution fields from the service desk.",
        domain="support",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("freshservice", "freshservice.tickets.get", "Freshservice ticket", kind="read"),
            VendorCapabilityBinding("zendesk", "zendesk.tickets.get", "Zendesk ticket", kind="read"),
            VendorCapabilityBinding("freshdesk", "freshdesk.tickets.get", "Freshdesk ticket", kind="read"),
        ),
    ),
    "support.ticket.list": CapabilityDefinition(
        capability_id="support.ticket.list",
        label="List service tickets",
        description="List recent tickets from the service desk.",
        domain="support",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("freshservice", "freshservice.tickets.list", "Freshservice tickets", kind="read"),
            VendorCapabilityBinding("zendesk", "zendesk.tickets.list", "Zendesk tickets", kind="read"),
            VendorCapabilityBinding("freshdesk", "freshdesk.tickets.list", "Freshdesk tickets", kind="read"),
        ),
    ),
    "support.ticket.update": CapabilityDefinition(
        capability_id="support.ticket.update",
        label="Update service ticket",
        description="Update a ticket's status, owner or priority in the service desk.",
        domain="support",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("freshservice", "freshservice.tickets.update_status", "Freshservice status"),
            VendorCapabilityBinding("zendesk", "zendesk.tickets.update", "Zendesk ticket"),
            VendorCapabilityBinding("freshdesk", "freshdesk.tickets.update", "Freshdesk ticket"),
        ),
    ),
    "billing.subscription.read": CapabilityDefinition(
        capability_id="billing.subscription.read",
        label="Read subscription",
        description="Read a customer's subscription status and value from billing.",
        domain="billing",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("stripe", "stripe.subscriptions.get", "Stripe subscription", kind="read"),
        ),
    ),
    "cs.conversation.read": CapabilityDefinition(
        capability_id="cs.conversation.read",
        label="Read customer conversations",
        description="Read recent customer conversations and support history.",
        domain="customer_success",
        kind="read",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("intercom", "intercom.conversations.list", "Intercom conversations", kind="read"),
            VendorCapabilityBinding("zendesk", "zendesk.tickets.list", "Zendesk tickets", kind="read"),
            VendorCapabilityBinding("freshdesk", "freshdesk.tickets.list", "Freshdesk tickets", kind="read"),
        ),
    ),
    "cs.customer.message": CapabilityDefinition(
        capability_id="cs.customer.message",
        label="Message customer",
        description="Send an approved message to a customer.",
        domain="customer_success",
        kind="write",
        chat_tool=False,
        bindings=(
            VendorCapabilityBinding("intercom", "intercom.conversations.reply", "Intercom reply"),
            VendorCapabilityBinding("gmail", "gmail.messages.send", "Gmail"),
            VendorCapabilityBinding("hubspot", "hubspot.sequences.enroll", "HubSpot sequence"),
        ),
    ),
}


def get_capability(capability_id: str) -> CapabilityDefinition | None:
    return CAPABILITY_REGISTRY.get(str(capability_id or "").strip().lower())


def list_capability_ids() -> list[str]:
    return sorted(CAPABILITY_REGISTRY.keys())


BUILTIN_VENDORS = frozenset({"gravitre"})


def capability_actions(capability_id: str) -> tuple[str, ...]:
    """Every alternative catalog action for a capability, in preference order."""
    definition = get_capability(capability_id)
    if definition is None:
        return ()
    return tuple(binding.action_key for binding in definition.bindings)
