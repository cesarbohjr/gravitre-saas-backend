#!/usr/bin/env python3
"""Generate vendor_definitions.py for connector action catalog."""
from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "app" / "connectors" / "action_catalog" / "vendor_definitions.py"

# (vendor, display, category, docs_url, shipped, dept, v1, v2, v3)
# Each action: (suffix, name, scope_suffix)
VENDORS: list[tuple] = [
    (
        "salesforce",
        "Salesforce",
        "CRM / Marketing",
        "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/",
        True,
        "sales",
        [
            ("leads.get", "Get lead", "leads:read"),
            ("leads.search", "Search leads", "leads:read"),
            ("accounts.get", "Get account", "accounts:read"),
            ("opportunities.get", "Get opportunity", "opportunities:read"),
        ],
        [
            ("leads.create", "Create lead", "leads:write"),
            ("leads.update", "Update lead", "leads:write"),
            ("opportunities.create", "Create opportunity", "opportunities:write"),
            ("tasks.create", "Create task", "tasks:write"),
        ],
        [
            ("opportunities.update_stage", "Update opportunity stage", "opportunities:write"),
            ("accounts.update", "Update account", "accounts:write"),
            ("opportunities.update", "Update opportunity", "opportunities:write"),
        ],
    ),
    (
        "hubspot",
        "HubSpot",
        "CRM / Marketing",
        "https://developers.hubspot.com/docs/api/overview",
        True,
        "sales",
        [
            ("contacts.get", "Get contact", "contacts:read"),
            ("contacts.search", "Search contacts", "contacts:read"),
            ("deals.get", "Get deal", "deals:read"),
        ],
        [
            ("contacts.create", "Create contact", "contacts:write"),
            ("contacts.update", "Update contact", "contacts:write"),
            ("deals.create", "Create deal", "deals:write"),
            ("notes.create", "Create note", "notes:write"),
        ],
        [
            ("deals.update_stage", "Update deal stage", "deals:write"),
            ("sequences.enroll", "Enroll in sequence", "sequences:enroll"),
            ("lists.add_contact", "Add contact to list", "lists:write"),
        ],
    ),
    (
        "marketo",
        "Marketo",
        "CRM / Marketing",
        "https://developers.marketo.com/rest-api/",
        True,
        "marketing",
        [
            ("leads.get", "Get lead", "leads:read"),
            ("campaigns.list", "List campaigns", "campaigns:read"),
            ("programs.status", "Get program status", "programs:read"),
        ],
        [
            ("leads.update", "Update lead", "leads:write"),
            ("leads.create", "Create lead", "leads:write"),
            ("campaigns.schedule", "Schedule campaign", "campaigns:write"),
        ],
        [
            ("lists.add_to_static_list", "Add to static list", "lists:write"),
            ("leads.merge", "Merge leads", "leads:write"),
            ("programs.members.add", "Add program members", "programs:write"),
        ],
    ),
    (
        "segment",
        "Segment",
        "CRM / Marketing",
        "https://segment.com/docs/connections/sources/catalog/libraries/server/http-api/",
        True,
        "marketing",
        [
            ("sources.list", "List sources", "sources:read"),
            ("destinations.list", "List destinations", "destinations:read"),
            ("trackingplans.list", "List tracking plans", "trackingplans:read"),
        ],
        [
            ("identify", "Identify user", "identify"),
            ("track", "Track event", "track"),
            ("group", "Group account", "group"),
        ],
        [
            ("alias", "Alias user", "write"),
            ("page", "Track page view", "write"),
            ("batch", "Batch events", "write"),
        ],
    ),
    (
        "google_analytics",
        "Google Analytics",
        "CRM / Marketing",
        "https://developers.google.com/analytics/devguides/reporting/data/v1",
        True,
        "marketing",
        [
            ("properties.list", "List GA4 properties", "read"),
            ("reports.run", "Run report", "read"),
            ("metadata.list", "List dimensions/metrics", "read"),
        ],
        [
            ("audiences.create", "Create audience", "write"),
            ("conversions.create", "Create conversion", "write"),
        ],
        [
            ("reports.batch", "Batch reports", "read"),
            ("realtime.run", "Realtime report", "read"),
            ("funnels.run", "Funnel exploration", "read"),
        ],
    ),
    (
        "mailchimp",
        "Mailchimp",
        "CRM / Marketing",
        "https://mailchimp.com/developer/marketing/api/",
        False,
        "marketing",
        [
            ("audiences.list", "List audiences", "audiences:read"),
            ("members.get", "Get list member", "members:read"),
            ("campaigns.list", "List campaigns", "campaigns:read"),
        ],
        [
            ("members.add", "Add list member", "members:write"),
            ("campaigns.create", "Create campaign", "campaigns:write"),
            ("tags.add", "Add member tags", "tags:write"),
        ],
        [
            ("automations.trigger", "Trigger automation email", "automations:write"),
            ("segments.add_member", "Add to segment", "segments:write"),
            ("batch.subscribe", "Batch subscribe", "members:write"),
        ],
    ),
    (
        "mixpanel",
        "Mixpanel",
        "CRM / Marketing",
        "https://developer.mixpanel.com/reference/overview",
        False,
        "marketing",
        [
            ("events.query", "Query events", "events:read"),
            ("funnels.list", "List funnels", "funnels:read"),
            ("cohorts.list", "List cohorts", "cohorts:read"),
        ],
        [
            ("profiles.set", "Set user profile", "profiles:write"),
            ("events.track", "Track event", "events:write"),
        ],
        [
            ("cohorts.export", "Export cohort", "cohorts:read"),
            ("annotations.create", "Create annotation", "annotations:write"),
            ("engage.query", "Engage query", "engage:read"),
        ],
    ),
    (
        "constant_contact",
        "Constant Contact",
        "CRM / Marketing",
        "https://developer.constantcontact.com/api_guide/server_flow.html",
        False,
        "marketing",
        [
            ("contacts.list", "List contacts", "contacts:read"),
            ("contacts.get", "Get contact", "contacts:read"),
            ("campaigns.list", "List email campaigns", "campaigns:read"),
        ],
        [
            ("contacts.create", "Create contact", "contacts:write"),
            ("contacts.update", "Update contact", "contacts:write"),
            ("campaigns.create", "Create campaign", "campaigns:write"),
        ],
        [
            ("lists.add_contacts", "Add contacts to list", "lists:write"),
            ("tags.apply", "Apply contact tags", "tags:write"),
            ("campaigns.schedule", "Schedule campaign send", "campaigns:write"),
        ],
    ),
    (
        "hootsuite",
        "Hootsuite",
        "CRM / Marketing",
        "https://developer.hootsuite.com/docs/api-overview",
        False,
        "marketing",
        [
            ("organizations.list", "List organizations", "organizations:read"),
            ("messages.list", "List scheduled messages", "messages:read"),
            ("analytics.summary", "Social analytics summary", "analytics:read"),
        ],
        [
            ("messages.schedule", "Schedule post", "messages:write"),
            ("messages.update", "Update scheduled post", "messages:write"),
        ],
        [
            ("inbox.reply", "Reply in social inbox", "inbox:write"),
            ("approvals.submit", "Submit for approval", "approvals:write"),
            ("bulk.schedule", "Bulk schedule posts", "messages:write"),
        ],
    ),
    (
        "semrush",
        "SEMrush",
        "CRM / Marketing",
        "https://developer.semrush.com/api/v3/analytics/basic-docs/",
        False,
        "marketing",
        [
            ("domain.overview", "Domain overview", "analytics:read"),
            ("keywords.list", "Keyword analytics", "keywords:read"),
            ("backlinks.list", "Backlinks report", "backlinks:read"),
        ],
        [
            ("projects.create", "Create project", "projects:write"),
            ("position_tracking.add", "Add keywords to tracking", "tracking:write"),
        ],
        [
            ("batch.domain", "Batch domain reports", "analytics:read"),
            ("competitors.compare", "Competitor comparison", "analytics:read"),
            ("exports.run", "Run export job", "exports:write"),
        ],
    ),
    (
        "stackadapt",
        "StackAdapt",
        "CRM / Marketing",
        "https://docs.stackadapt.com/",
        False,
        "marketing",
        [
            ("campaigns.list", "List campaigns", "campaigns:read"),
            ("campaigns.get", "Get campaign", "campaigns:read"),
            ("stats.summary", "Campaign stats summary", "stats:read"),
        ],
        [
            ("campaigns.create", "Create campaign", "campaigns:write"),
            ("campaigns.update", "Update campaign", "campaigns:write"),
        ],
        [
            ("audiences.sync", "Sync audience segment", "audiences:write"),
            ("creatives.upload", "Upload creative assets", "creatives:write"),
            ("reports.export", "Export performance report", "reports:read"),
        ],
    ),
    (
        "linkedin",
        "LinkedIn",
        "Sales / Prospecting",
        "https://learn.microsoft.com/en-us/linkedin/marketing/",
        True,
        "sales",
        [
            ("prospect.enrich", "Enrich prospect profile", "prospects:read"),
            ("organizations.get", "Get company page", "organizations:read"),
            ("ads.accounts.list", "List ad accounts", "ads:read"),
        ],
        [
            ("leads.submit", "Submit lead gen form", "leads:write"),
            ("audience.update", "Update matched audience", "audiences:write"),
        ],
        [
            ("campaigns.optimize", "Suggest campaign optimization", "ads:write"),
            ("conversions.track", "Track conversion event", "conversions:write"),
            ("batch.enrich", "Batch enrich prospects", "prospects:read"),
        ],
    ),
    (
        "apollo",
        "Apollo",
        "Sales / Prospecting",
        "https://apolloio.github.io/apollo-api-docs/",
        False,
        "sales",
        [
            ("people.search", "Search people", "people:read"),
            ("organizations.search", "Search companies", "organizations:read"),
            ("contacts.get", "Get contact", "contacts:read"),
        ],
        [
            ("contacts.create", "Create contact", "contacts:write"),
            ("sequences.add", "Add to sequence", "sequences:write"),
        ],
        [
            ("enrichment.bulk", "Bulk enrich records", "enrichment:write"),
            ("tasks.create", "Create outreach task", "tasks:write"),
            ("signals.subscribe", "Subscribe intent signals", "signals:read"),
        ],
    ),
    (
        "stripe",
        "Stripe",
        "Payments / Finance",
        "https://docs.stripe.com/api",
        True,
        "finance",
        [
            ("invoices.list", "List invoices", "invoices:read"),
            ("subscriptions.get", "Get subscription", "subscriptions:read"),
            ("customers.get", "Get customer", "customers:read"),
        ],
        [
            ("customers.create", "Create customer", "customers:write"),
            ("invoices.create", "Create invoice", "invoices:write"),
            ("refunds.create", "Create refund", "refunds:write"),
        ],
        [
            ("subscriptions.update", "Update subscription", "subscriptions:write"),
            ("payment_intents.confirm", "Confirm payment", "payments:write"),
            ("checkout.sessions.create", "Create Checkout session", "checkout:write"),
        ],
    ),
    (
        "quickbooks",
        "QuickBooks",
        "Payments / Finance",
        "https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account",
        True,
        "finance",
        [
            ("invoices.list", "List invoices", "invoices:read"),
            ("invoices.get", "Get invoice", "invoices:read"),
            ("customers.list", "List customers", "customers:read"),
            ("companyinfo.get", "Get company info", "company:read"),
        ],
        [
            ("invoices.create", "Create invoice", "invoices:write"),
            ("customers.create", "Create customer", "customers:write"),
            ("payments.create", "Record payment", "payments:write"),
        ],
        [
            ("customers.search", "Search customers", "customers:read"),
            ("bills.list", "List bills", "bills:read"),
            ("journalentries.create", "Create journal entry", "write"),
        ],
    ),
    (
        "netsuite",
        "NetSuite",
        "Payments / Finance",
        "https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_1540391670.html",
        True,
        "finance",
        [
            ("customers.get", "Get customer", "customers:read"),
            ("invoices.list", "List invoices", "invoices:read"),
            ("salesorders.get", "Get sales order", "salesorders:read"),
        ],
        [
            ("customers.update", "Update customer", "write"),
            ("journalentries.create", "Create journal entry", "write"),
            ("salesorders.create", "Create sales order", "salesorders:write"),
        ],
        [
            ("items.get", "Get item catalog entry", "items:read"),
            ("invoices.get", "Get invoice detail", "invoices:read"),
            ("fulfillment.create", "Create item fulfillment", "fulfillment:write"),
        ],
    ),
    (
        "xero",
        "Xero",
        "Payments / Finance",
        "https://developer.xero.com/documentation/api/accounting/overview",
        False,
        "finance",
        [
            ("contacts.list", "List contacts", "contacts:read"),
            ("invoices.list", "List invoices", "invoices:read"),
            ("accounts.list", "List accounts", "accounts:read"),
        ],
        [
            ("invoices.create", "Create invoice", "invoices:write"),
            ("contacts.create", "Create contact", "contacts:write"),
            ("payments.create", "Create payment", "payments:write"),
        ],
        [
            ("banktransactions.import", "Import bank transactions", "bank:write"),
            ("reports.profitloss", "Profit and loss report", "reports:read"),
            ("batch.invoices", "Batch create invoices", "invoices:write"),
        ],
    ),
    (
        "plaid",
        "Plaid",
        "Payments / Finance",
        "https://plaid.com/docs/api/",
        False,
        "finance",
        [
            ("accounts.get", "Get linked accounts", "accounts:read"),
            ("transactions.list", "List transactions", "transactions:read"),
            ("balances.get", "Get balances", "balances:read"),
        ],
        [
            ("link.token.create", "Create Link token", "link:write"),
            ("public_token.exchange", "Exchange public token", "link:write"),
        ],
        [
            ("transactions.sync", "Sync transactions", "transactions:read"),
            ("identity.get", "Get identity", "identity:read"),
            ("investments.holdings", "Investment holdings", "investments:read"),
        ],
    ),
    (
        "slack",
        "Slack",
        "Communication",
        "https://api.slack.com/methods",
        True,
        "operations",
        [
            ("conversations.list", "List channels", "channels:read"),
            ("conversations.history", "Read channel messages", "messages:read"),
            ("users.list", "List workspace users", "users:read"),
        ],
        [
            ("post_message", "Post message", "messages:write"),
            ("conversations.create", "Create channel", "channels:write"),
            ("chat.update", "Update message", "messages:write"),
        ],
        [
            ("files.upload", "Upload file", "files:write"),
            ("reactions.add", "Add reaction", "reactions:write"),
            ("workflows.trigger", "Trigger workflow", "workflows:write"),
        ],
    ),
    (
        "microsoft_teams",
        "Microsoft Teams",
        "Communication",
        "https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview",
        False,
        "operations",
        [
            ("teams.list", "List teams", "teams:read"),
            ("channels.list", "List channels", "channels:read"),
            ("messages.list", "List channel messages", "messages:read"),
        ],
        [
            ("messages.send", "Send channel message", "messages:write"),
            ("meetings.create", "Create online meeting", "meetings:write"),
        ],
        [
            ("tabs.create", "Add channel tab", "tabs:write"),
            ("members.add", "Add team member", "members:write"),
            ("presence.set", "Set presence status", "presence:write"),
        ],
    ),
    (
        "microsoft365",
        "Microsoft 365",
        "Communication",
        "https://learn.microsoft.com/en-us/graph/api/overview",
        False,
        "operations",
        [
            ("users.get", "Get user profile", "users:read"),
            ("mail.messages.list", "List Outlook messages", "mail:read"),
            ("calendar.events.list", "List calendar events", "calendar:read"),
        ],
        [
            ("mail.send", "Send email", "mail:send"),
            ("calendar.events.create", "Create calendar event", "calendar:write"),
            ("files.upload", "Upload OneDrive file", "files:write"),
        ],
        [
            ("excel.workbook.update", "Update Excel range", "excel:write"),
            ("teams.notify", "Post Teams notification", "teams:write"),
            ("batch.mail", "Batch send mail", "mail:send"),
        ],
    ),
    (
        "gmail",
        "Gmail",
        "Communication",
        "https://developers.google.com/gmail/api/reference/rest",
        True,
        "operations",
        [
            ("messages.list", "List messages", "read"),
            ("messages.get", "Get message", "read"),
            ("labels.list", "List labels", "read"),
        ],
        [
            ("messages.send", "Send email", "send"),
            ("drafts.create", "Create draft", "write"),
            ("labels.create", "Create label", "write"),
        ],
        [
            ("threads.modify", "Modify thread labels", "write"),
            ("messages.batch", "Batch modify messages", "write"),
            ("watch.create", "Create push watch", "write"),
        ],
    ),
    (
        "google_calendar",
        "Google Calendar",
        "Communication",
        "https://developers.google.com/calendar/api/v3/reference",
        True,
        "operations",
        [
            ("freebusy", "Query free/busy", "read"),
            ("events.list", "List events", "read"),
            ("calendars.list", "List calendars", "read"),
        ],
        [
            ("events.create", "Create event", "write"),
            ("events.update", "Update event", "write"),
            ("events.delete", "Delete event", "write"),
        ],
        [
            ("events.quick_add", "Quick add event", "write"),
            ("acl.list", "List calendar ACL", "read"),
            ("batch.events", "Batch event changes", "write"),
        ],
    ),
    (
        "outlook",
        "Outlook",
        "Communication",
        "https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview",
        False,
        "operations",
        [
            ("messages.list", "List messages", "mail:read"),
            ("messages.get", "Get message", "mail:read"),
            ("folders.list", "List mail folders", "mail:read"),
        ],
        [
            ("messages.send", "Send message", "mail:send"),
            ("messages.reply", "Reply to message", "mail:send"),
        ],
        [
            ("rules.create", "Create inbox rule", "mail:write"),
            ("categories.apply", "Apply categories", "mail:write"),
            ("batch.send", "Batch send messages", "mail:send"),
        ],
    ),
    (
        "twilio",
        "Twilio",
        "Communication",
        "https://www.twilio.com/docs/usage/api",
        False,
        "operations",
        [
            ("messages.list", "List SMS messages", "messages:read"),
            ("calls.list", "List calls", "calls:read"),
            ("accounts.get", "Get account", "accounts:read"),
        ],
        [
            ("messages.create", "Send SMS", "messages:write"),
            ("calls.create", "Initiate call", "calls:write"),
        ],
        [
            ("verify.check", "Check verification code", "verify:write"),
            ("conversations.create", "Create conversation", "conversations:write"),
            ("studio.flows.execute", "Execute Studio flow", "studio:write"),
        ],
    ),
    (
        "sendgrid",
        "SendGrid",
        "Communication",
        "https://docs.sendgrid.com/api-reference",
        False,
        "operations",
        [
            ("messages.list", "List sent messages", "messages:read"),
            ("templates.list", "List templates", "templates:read"),
            ("stats.get", "Get email stats", "stats:read"),
        ],
        [
            ("mail.send", "Send transactional email", "mail:send"),
            ("contacts.upsert", "Upsert marketing contact", "contacts:write"),
        ],
        [
            ("campaigns.schedule", "Schedule campaign", "campaigns:write"),
            ("suppressions.add", "Add suppression", "suppressions:write"),
            ("batch.send", "Batch send mail", "mail:send"),
        ],
    ),
    (
        "email",
        "Email",
        "Communication",
        "https://datatracker.ietf.org/doc/html/rfc5321",
        True,
        "operations",
        [
            ("messages.queue", "View outbound queue", "queue:read"),
            ("delivery.status", "Delivery status", "delivery:read"),
        ],
        [
            ("send", "Send email", "send"),
        ],
        [
            ("send.template", "Send templated email", "send"),
            ("batch.send", "Batch send", "send"),
        ],
    ),
    (
        "pagerduty",
        "PagerDuty",
        "DevOps / Incidents",
        "https://developer.pagerduty.com/api-reference/",
        True,
        "support",
        [
            ("incidents.list", "List incidents", "incidents:read"),
            ("incidents.get", "Get incident", "incidents:read"),
            ("services.list", "List services", "services:read"),
            ("oncalls.list", "List on-calls", "oncalls:read"),
        ],
        [
            ("incidents.acknowledge", "Acknowledge incident", "incidents:write"),
            ("incidents.resolve", "Resolve incident", "incidents:write"),
            ("incidents.add_note", "Add incident note", "incidents:write"),
        ],
        [
            ("incidents.escalate", "Escalate incident", "incidents:write"),
            ("incidents.reassign", "Reassign incident", "incidents:write"),
            ("incidents.notes.list", "List incident notes", "incidents:read"),
        ],
    ),
    (
        "github",
        "GitHub",
        "DevOps / Incidents",
        "https://docs.github.com/en/rest",
        True,
        "operations",
        [
            ("pulls.list", "List pull requests", "pulls:read"),
            ("issues.get", "Get issue", "issues:read"),
            ("repos.get", "Get repository", "repos:read"),
        ],
        [
            ("issues.create", "Create issue", "issues:write"),
            ("issues.comment", "Comment on issue", "issues:write"),
            ("pulls.request_reviewer", "Request PR reviewer", "pulls:write"),
        ],
        [
            ("actions.dispatch", "Dispatch workflow", "actions:write"),
            ("pulls.merge", "Merge pull request", "pulls:write"),
            ("releases.create", "Create release", "releases:write"),
        ],
        [
            ("issues.list", "List issues", "issues:read"),
            ("pulls.get", "Get pull request", "pulls:read"),
            ("pulls.close", "Close pull request", "pulls:write"),
        ],
    ),
    (
        "notion",
        "Notion",
        "Operations / Workflow",
        "https://developers.notion.com/reference/intro",
        True,
        "operations",
        [
            ("pages.get", "Get page", "pages:read"),
            ("databases.query", "Query database", "databases:read"),
            ("users.list", "List users", "users:read"),
        ],
        [
            ("pages.create", "Create page", "pages:write"),
            ("pages.update", "Update page", "pages:write"),
            ("blocks.append", "Append blocks", "blocks:write"),
        ],
        [
            ("databases.create", "Create database", "databases:write"),
            ("search", "Search workspace", "search:read"),
            ("comments.create", "Add comment", "comments:write"),
        ],
    ),
    (
        "confluence",
        "Confluence",
        "Operations / Workflow",
        "https://developer.atlassian.com/cloud/confluence/rest/v2/intro/",
        True,
        "operations",
        [
            ("pages.get", "Get page", "pages:read"),
            ("spaces.list", "List spaces", "spaces:read"),
            ("pages.search", "Search pages", "pages:read"),
        ],
        [
            ("pages.create", "Create page", "pages:write"),
            ("pages.update", "Update page", "pages:write"),
            ("labels.add", "Add labels", "labels:write"),
        ],
        [
            ("attachments.upload", "Upload attachment", "attachments:write"),
            ("pages.move", "Move page", "pages:write"),
            ("export.pdf", "Export page PDF", "export:read"),
        ],
    ),
    (
        "jira",
        "Jira",
        "Operations / Workflow",
        "https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/",
        True,
        "operations",
        [
            ("issues.get", "Get issue", "issues:read"),
            ("issues.search", "Search issues", "issues:read"),
            ("projects.list", "List projects", "projects:read"),
        ],
        [
            ("issues.create", "Create issue", "issues:write"),
            ("issues.update", "Update issue", "issues:write"),
            ("issues.comment", "Add comment", "issues:write"),
        ],
        [
            ("issues.transition", "Transition issue", "issues:write"),
            ("issues.assign", "Assign issue", "issues:write"),
            ("issues.transitions.list", "List transitions", "issues:read"),
        ],
    ),
    (
        "airtable",
        "Airtable",
        "Operations / Workflow",
        "https://airtable.com/developers/web/api/introduction",
        False,
        "operations",
        [
            ("bases.list", "List bases", "bases:read"),
            ("records.list", "List records", "records:read"),
            ("records.get", "Get record", "records:read"),
        ],
        [
            ("records.create", "Create records", "records:write"),
            ("records.update", "Update records", "records:write"),
        ],
        [
            ("records.delete", "Delete records", "records:write"),
            ("webhooks.create", "Create webhook", "webhooks:write"),
            ("batch.records", "Batch upsert records", "records:write"),
        ],
    ),
    (
        "asana",
        "Asana",
        "Operations / Workflow",
        "https://developers.asana.com/docs",
        False,
        "operations",
        [
            ("tasks.get", "Get task", "tasks:read"),
            ("projects.list", "List projects", "projects:read"),
            ("users.list", "List users", "users:read"),
        ],
        [
            ("tasks.create", "Create task", "tasks:write"),
            ("tasks.update", "Update task", "tasks:write"),
            ("stories.create", "Add comment", "stories:write"),
        ],
        [
            ("tasks.add_project", "Add task to project", "tasks:write"),
            ("sections.move", "Move to section", "sections:write"),
            ("batch.tasks", "Batch task updates", "tasks:write"),
        ],
    ),
    (
        "monday",
        "Monday.com",
        "Operations / Workflow",
        "https://developer.monday.com/api-reference/docs",
        False,
        "operations",
        [
            ("boards.list", "List boards", "boards:read"),
            ("items.get", "Get item", "items:read"),
            ("users.list", "List users", "users:read"),
        ],
        [
            ("items.create", "Create item", "items:write"),
            ("items.update", "Update column values", "items:write"),
        ],
        [
            ("automations.trigger", "Trigger automation", "automations:write"),
            ("updates.create", "Post update", "updates:write"),
            ("batch.items", "Batch create items", "items:write"),
        ],
    ),
    (
        "clickup",
        "ClickUp",
        "Operations / Workflow",
        "https://clickup.com/api",
        False,
        "operations",
        [
            ("tasks.get", "Get task", "tasks:read"),
            ("lists.get", "Get list", "lists:read"),
            ("spaces.list", "List spaces", "spaces:read"),
        ],
        [
            ("tasks.create", "Create task", "tasks:write"),
            ("tasks.update", "Update task", "tasks:write"),
            ("comments.create", "Add comment", "comments:write"),
        ],
        [
            ("time_entries.create", "Log time entry", "time:write"),
            ("goals.update", "Update goal", "goals:write"),
            ("webhooks.create", "Create webhook", "webhooks:write"),
        ],
    ),
    (
        "zapier",
        "Zapier",
        "Operations / Workflow",
        "https://platform.zapier.com/docs",
        False,
        "operations",
        [
            ("zaps.list", "List Zaps", "zaps:read"),
            ("actions.list", "List app actions", "actions:read"),
            ("runs.list", "List Zap runs", "runs:read"),
        ],
        [
            ("zaps.enable", "Enable Zap", "zaps:write"),
            ("hooks.trigger", "Trigger webhook Zap", "hooks:write"),
        ],
        [
            ("tables.rows.upsert", "Upsert Zapier Tables row", "tables:write"),
            ("batch.trigger", "Batch trigger hooks", "hooks:write"),
            ("interfaces.submit", "Submit interface form", "interfaces:write"),
        ],
    ),
    (
        "n8n",
        "n8n",
        "Operations / Workflow",
        "https://docs.n8n.io/api/",
        False,
        "operations",
        [
            ("workflows.list", "List workflows", "workflows:read"),
            ("executions.list", "List executions", "executions:read"),
            ("credentials.list", "List credentials", "credentials:read"),
        ],
        [
            ("workflows.create", "Create workflow", "workflows:write"),
            ("workflows.activate", "Activate workflow", "workflows:write"),
        ],
        [
            ("executions.retry", "Retry failed execution", "executions:write"),
            ("webhooks.trigger", "Trigger webhook workflow", "webhooks:write"),
            ("batch.executions", "Batch run workflows", "executions:write"),
        ],
    ),
    (
        "motion",
        "Motion",
        "Operations / Workflow",
        "https://docs.usemotion.com/",
        False,
        "operations",
        [
            ("tasks.list", "List tasks", "tasks:read"),
            ("projects.list", "List projects", "projects:read"),
            ("schedules.get", "Get auto-schedule", "schedules:read"),
        ],
        [
            ("tasks.create", "Create task", "tasks:write"),
            ("tasks.update", "Update task", "tasks:write"),
        ],
        [
            ("calendar.optimize", "Optimize calendar", "calendar:write"),
            ("batch.reschedule", "Batch reschedule tasks", "tasks:write"),
            ("focus.block", "Create focus block", "calendar:write"),
        ],
    ),
    (
        "odoo",
        "Odoo",
        "Operations / Workflow",
        "https://www.odoo.com/documentation/17.0/developer/reference/external_api.html",
        True,
        "operations",
        [
            ("partners.get", "Get partner", "partners:read"),
            ("sales.orders.list", "List sales orders", "sales:read"),
            ("inventory.products.list", "List products", "inventory:read"),
        ],
        [
            ("partners.create", "Create partner", "partners:write"),
            ("sales.orders.create", "Create sales order", "sales:write"),
            ("invoices.create", "Create invoice", "invoices:write"),
        ],
        [
            ("manufacturing.orders.create", "Create MO", "manufacturing:write"),
            ("crm.leads.convert", "Convert lead", "crm:write"),
            ("batch.partners", "Batch upsert partners", "partners:write"),
        ],
        [
            ("partners.update", "Update partner", "partners:write"),
            ("sales.orders.confirm", "Confirm sales order", "sales:write"),
            ("invoices.post", "Post invoice", "invoices:write"),
        ],
    ),
    (
        "zendesk",
        "Zendesk",
        "Customer Support",
        "https://developer.zendesk.com/api-reference/",
        True,
        "support",
        [
            ("tickets.get", "Get ticket", "tickets:read"),
            ("tickets.list", "List tickets", "tickets:read"),
            ("users.get", "Get user", "users:read"),
        ],
        [
            ("tickets.create", "Create ticket", "tickets:write"),
            ("tickets.update", "Update ticket", "tickets:write"),
            ("tickets.add_tags", "Add ticket tags", "tickets:write"),
        ],
        [
            ("tickets.merge", "Merge tickets", "tickets:write"),
            ("macros.apply", "Apply macro", "macros:write"),
            ("side_conversations.create", "Create side conversation", "tickets:write"),
        ],
    ),
    (
        "intercom",
        "Intercom",
        "Customer Support",
        "https://developers.intercom.com/docs/references/rest-api/api.intercom.io/",
        False,
        "support",
        [
            ("contacts.get", "Get contact", "contacts:read"),
            ("conversations.list", "List conversations", "conversations:read"),
            ("tickets.list", "List tickets", "tickets:read"),
        ],
        [
            ("contacts.create", "Create contact", "contacts:write"),
            ("conversations.reply", "Reply to conversation", "conversations:write"),
            ("tickets.create", "Create ticket", "tickets:write"),
        ],
        [
            ("tags.apply", "Apply tags", "tags:write"),
            ("series.trigger", "Trigger series", "series:write"),
            ("notes.create", "Create user note", "notes:write"),
        ],
    ),
    (
        "freshdesk",
        "Freshdesk",
        "Customer Support",
        "https://developers.freshdesk.com/api/",
        False,
        "support",
        [
            ("tickets.get", "Get ticket", "tickets:read"),
            ("tickets.list", "List tickets", "tickets:read"),
            ("contacts.get", "Get contact", "contacts:read"),
        ],
        [
            ("tickets.create", "Create ticket", "tickets:write"),
            ("tickets.update", "Update ticket", "tickets:write"),
            ("notes.create", "Add private note", "notes:write"),
        ],
        [
            ("tickets.merge", "Merge tickets", "tickets:write"),
            ("automations.trigger", "Trigger scenario", "automations:write"),
            ("satisfaction.send", "Send CSAT survey", "satisfaction:write"),
        ],
    ),
    (
        "gorgias",
        "Gorgias",
        "Customer Support",
        "https://developers.gorgias.com/reference/introduction",
        False,
        "support",
        [
            ("tickets.get", "Get ticket", "tickets:read"),
            ("tickets.list", "List tickets", "tickets:read"),
            ("customers.get", "Get customer", "customers:read"),
        ],
        [
            ("tickets.create", "Create ticket", "tickets:write"),
            ("tickets.reply", "Reply to ticket", "tickets:write"),
            ("macros.apply", "Apply macro", "macros:write"),
        ],
        [
            ("rules.trigger", "Trigger rule", "rules:write"),
            ("tags.apply", "Apply tags", "tags:write"),
            ("satisfaction.request", "Request satisfaction", "satisfaction:write"),
        ],
    ),
    (
        "workday",
        "Workday",
        "HR / People",
        "https://community.workday.com/sites/default/files/file-hosting/restapi/index.html",
        True,
        "operations",
        [
            ("workers.get", "Get worker", "workers:read"),
            ("orgunits.list", "List org units", "orgunits:read"),
            ("positions.list", "List positions", "positions:read"),
        ],
        [
            ("timeoff.request", "Request time off", "timeoff:write"),
            ("jobs.update", "Update job profile", "jobs:write"),
        ],
        [
            ("timeoff.balance.get", "Get time off balance", "timeoff:read"),
            ("learning.enroll", "Enroll in course", "learning:write"),
            ("batch.workers.export", "Export workers", "workers:read"),
        ],
    ),
    (
        "bamboohr",
        "BambooHR",
        "HR / People",
        "https://documentation.bamboohr.com/reference",
        False,
        "operations",
        [
            ("employees.get", "Get employee", "employees:read"),
            ("employees.list", "List employees", "employees:read"),
            ("timeoff.requests.list", "List time off requests", "timeoff:read"),
        ],
        [
            ("employees.create", "Create employee", "employees:write"),
            ("timeoff.requests.create", "Create time off request", "timeoff:write"),
        ],
        [
            ("onboarding.tasks.assign", "Assign onboarding tasks", "onboarding:write"),
            ("reports.run", "Run custom report", "reports:read"),
            ("webhooks.create", "Create webhook", "webhooks:write"),
        ],
    ),
    (
        "gusto",
        "Gusto",
        "HR / People",
        "https://docs.gusto.com/app-integrations/reference",
        False,
        "operations",
        [
            ("employees.get", "Get employee", "employees:read"),
            ("payrolls.list", "List payrolls", "payrolls:read"),
            ("companies.get", "Get company", "companies:read"),
        ],
        [
            ("employees.create", "Create employee", "employees:write"),
            ("payrolls.run", "Run payroll", "payrolls:write"),
        ],
        [
            ("benefits.enroll", "Enroll in benefits", "benefits:write"),
            ("contractors.pay", "Pay contractor", "contractors:write"),
            ("reports.generate", "Generate payroll report", "reports:read"),
        ],
    ),
    (
        "adp",
        "ADP",
        "HR / People",
        "https://developers.adp.com/",
        False,
        "operations",
        [
            ("workers.get", "Get worker", "workers:read"),
            ("paystatements.list", "List pay statements", "pay:read"),
            ("events.list", "List HR events", "events:read"),
        ],
        [
            ("timecards.submit", "Submit timecard", "time:write"),
            ("profile.update", "Update worker profile", "workers:write"),
        ],
        [
            ("payroll.preview", "Preview payroll", "pay:write"),
            ("benefits.elect", "Benefits election", "benefits:write"),
            ("batch.workers.sync", "Sync workers", "workers:read"),
        ],
    ),
    (
        "aws_s3",
        "AWS S3",
        "Storage / Dev / Infra",
        "https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html",
        False,
        "operations",
        [
            ("buckets.list", "List buckets", "buckets:read"),
            ("objects.list", "List objects", "objects:read"),
            ("objects.head", "Head object metadata", "objects:read"),
        ],
        [
            ("objects.put", "Upload object", "objects:write"),
            ("objects.delete", "Delete object", "objects:write"),
        ],
        [
            ("presigned.get", "Generate presigned URL", "objects:read"),
            ("multipart.upload", "Multipart upload", "objects:write"),
            ("batch.delete", "Batch delete objects", "objects:write"),
        ],
    ),
    (
        "postgresql",
        "PostgreSQL",
        "Storage / Dev / Infra",
        "https://www.postgresql.org/docs/current/sql.html",
        True,
        "operations",
        [
            ("query.select", "Run SELECT query", "query:read"),
            ("tables.list", "List tables", "schema:read"),
            ("schemas.list", "List schemas", "schema:read"),
        ],
        [
            ("query.insert", "Run INSERT", "query:write"),
            ("query.update", "Run UPDATE", "query:write"),
        ],
        [
            ("query.explain", "EXPLAIN query plan", "query:read"),
            ("batch.upsert", "Batch upsert rows", "query:write"),
            ("migrations.apply", "Apply migration", "schema:write"),
        ],
    ),
    (
        "mongodb",
        "MongoDB",
        "Storage / Dev / Infra",
        "https://www.mongodb.com/docs/manual/reference/command/",
        False,
        "operations",
        [
            ("collections.list", "List collections", "collections:read"),
            ("documents.find", "Find documents", "documents:read"),
            ("indexes.list", "List indexes", "indexes:read"),
        ],
        [
            ("documents.insert", "Insert documents", "documents:write"),
            ("documents.update", "Update documents", "documents:write"),
        ],
        [
            ("aggregation.run", "Run aggregation pipeline", "documents:read"),
            ("change_streams.watch", "Watch change stream", "streams:read"),
            ("batch.bulk_write", "Bulk write operations", "documents:write"),
        ],
    ),
    (
        "snowflake",
        "Snowflake",
        "Storage / Dev / Infra",
        "https://docs.snowflake.com/en/developer-guide/sql-api/index",
        False,
        "operations",
        [
            ("query.execute", "Execute SQL query", "query:read"),
            ("warehouses.list", "List warehouses", "warehouses:read"),
            ("tables.describe", "Describe table", "schema:read"),
        ],
        [
            ("query.insert", "Insert via SQL", "query:write"),
            ("stages.put", "Upload to stage", "stages:write"),
        ],
        [
            ("tasks.run", "Run task", "tasks:write"),
            ("pipes.refresh", "Refresh pipe", "pipes:write"),
            ("batch.copy", "COPY INTO batch load", "load:write"),
        ],
    ),
    (
        "google_drive",
        "Google Drive",
        "Storage / Dev / Infra",
        "https://developers.google.com/drive/api/reference/rest/v3",
        True,
        "operations",
        [
            ("files.list", "List files", "read"),
            ("files.get", "Get file metadata", "read"),
            ("permissions.list", "List permissions", "read"),
        ],
        [
            ("files.create", "Create file", "write"),
            ("files.update", "Update file metadata", "write"),
            ("permissions.create", "Share file", "write"),
        ],
        [
            ("files.export", "Export Google Doc", "read"),
            ("changes.list", "List changes", "read"),
            ("batch.permissions", "Batch permission updates", "write"),
        ],
    ),
    (
        "google_docs",
        "Google Docs",
        "Storage / Dev / Infra",
        "https://developers.google.com/docs/api/reference/rest",
        True,
        "operations",
        [
            ("documents.get", "Get document", "read"),
            ("documents.batch_get", "Batch get documents", "read"),
        ],
        [
            ("documents.create", "Create document", "write"),
            ("documents.batch_update", "Batch update content", "write"),
        ],
        [
            ("documents.replace_text", "Replace all text", "write"),
            ("documents.insert_table", "Insert table", "write"),
            ("export.pdf", "Export as PDF", "read"),
        ],
    ),
    (
        "google_sheets",
        "Google Sheets",
        "Storage / Dev / Infra",
        "https://developers.google.com/sheets/api/reference/rest",
        True,
        "operations",
        [
            ("spreadsheets.get", "Get spreadsheet", "read"),
            ("values.get", "Get cell values", "read"),
            ("values.batch_get", "Batch get values", "read"),
        ],
        [
            ("values.update", "Update values", "write"),
            ("values.append", "Append rows", "write"),
            ("spreadsheets.create", "Create spreadsheet", "write"),
        ],
        [
            ("values.batch_update", "Batch update values", "write"),
            ("charts.add", "Add chart", "write"),
            ("pivot.create", "Create pivot table", "write"),
        ],
    ),
    (
        "absorb_lms",
        "Absorb LMS",
        "Learning / Creative",
        "https://docs.absorblms.com/",
        False,
        "operations",
        [
            ("courses.list", "List courses", "courses:read"),
            ("enrollments.list", "List enrollments", "enrollments:read"),
            ("users.get", "Get learner", "users:read"),
        ],
        [
            ("enrollments.create", "Enroll learner", "enrollments:write"),
            ("courses.create", "Create course", "courses:write"),
        ],
        [
            ("certificates.issue", "Issue certificate", "certificates:write"),
            ("reports.completion", "Completion report", "reports:read"),
            ("batch.enroll", "Batch enroll learners", "enrollments:write"),
        ],
    ),
    (
        "canva",
        "Canva",
        "Learning / Creative",
        "https://www.canva.dev/docs/connect/",
        False,
        "marketing",
        [
            ("designs.list", "List designs", "designs:read"),
            ("designs.get", "Get design", "designs:read"),
            ("folders.list", "List folders", "folders:read"),
        ],
        [
            ("designs.create", "Create design", "designs:write"),
            ("exports.create", "Export design", "exports:write"),
        ],
        [
            ("autofill.create", "Autofill brand template", "autofill:write"),
            ("brand.templates.list", "List brand templates", "brand:read"),
            ("batch.exports", "Batch export assets", "exports:write"),
        ],
    ),
]


def emit_vendor(defn: tuple) -> str:
    vendor, display, category, docs, shipped, dept, v1, v2, v3 = defn
    lines = [
        "    build_vendor(",
        f'        "{vendor}",',
        f'        "{display}",',
        f'        "{category}",',
        f'        "{docs}",',
        f"        shipped={str(shipped)},",
        f'        department="{dept}",',
        f"        v1=(",
    ]
    for suffix, name, scope in v1:
        lines.append(
            f'            action("{vendor}", "{suffix}", "{name}", tier="v1", kind="read", scope_suffix="{scope}", idempotent=True),'
        )
    lines.append("        ),")
    lines.append("        v2=(")
    for suffix, name, scope in v2:
        lines.append(
            f'            action("{vendor}", "{suffix}", "{name}", tier="v2", kind="write", scope_suffix="{scope}", destructive=True),'
        )
    lines.append("        ),")
    lines.append("        v3=(")
    for suffix, name, scope in v3:
        kind = "advanced"
        lines.append(
            f'            action("{vendor}", "{suffix}", "{name}", tier="v3", kind="{kind}", scope_suffix="{scope}"),'
        )
    lines.append("        ),")
    lines.append("    ),")
    return "\n".join(lines)


def main() -> None:
    body = "\n".join(emit_vendor(v) for v in VENDORS)
    content = (
        '"""Auto-generated vendor action + demo workflow definitions."""\n'
        "from __future__ import annotations\n\n"
        "from app.connectors.action_catalog.builder import action, build_vendor\n\n"
        "VENDOR_DEFINITIONS: tuple = (\n"
        f"{body}\n"
        ")\n"
    )
    OUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT} ({len(VENDORS)} vendors)")


if __name__ == "__main__":
    main()
