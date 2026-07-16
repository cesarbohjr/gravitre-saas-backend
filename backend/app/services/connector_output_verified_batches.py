"""Verified write-action batches (25 per batch) cleared from PENDING_OUTPUT_SCHEMA_ALLOWLIST.

Each batch is summary-verified via the generic write mapper (and connector-specific
mappers where they already exist). ``result_url`` may be null when the vendor has
no stable deep link — that is an intentional final contract.
"""
from __future__ import annotations

# Batch 1
VERIFIED_OUTPUT_BATCH_01: frozenset[str] = frozenset(
    {
        "absorb_lms.courses.create",
        "absorb_lms.enrollments.create",
        "adp.profile.update",
        "adp.timecards.submit",
        "airtable.records.create",
        "airtable.records.update",
        "apollo.contacts.create",
        "apollo.sequences.add",
        "asana.stories.create",
        "asana.tasks.create",
        "asana.tasks.update",
        "aws_s3.objects.delete",
        "aws_s3.objects.put",
        "bamboohr.employees.create",
        "bamboohr.timeoff.requests.create",
        "canva.designs.create",
        "canva.exports.create",
        "clay.enrichments.request",
        "clay.leads.push",
        "clickup.comments.create",
        "clickup.tasks.create",
        "clickup.tasks.update",
        "clio.conflict.checklist",
        "clio.intake.tasks",
        "clio.matters.create",
    }
)

# Batch 2
VERIFIED_OUTPUT_BATCH_02: frozenset[str] = frozenset(
    {
        "clio.tasks.create",
        "confluence.labels.add",
        "confluence.pages.create",
        "confluence.pages.update",
        "constant_contact.campaigns.create",
        "constant_contact.contacts.create",
        "constant_contact.contacts.update",
        "email.send",
        "fhir.prior_auth.checklist",
        "figma.comments.create",
        "figma.dev_resources.create",
        "freshdesk.notes.create",
        "freshdesk.tickets.create",
        "freshdesk.tickets.update",
        "github.issues.comment",
        "github.pulls.request_reviewer",
        "gmail.drafts.create",
        "gmail.labels.create",
        "google_analytics.audiences.create",
        "google_analytics.conversions.create",
        "google_calendar.events.create",
        "google_calendar.events.delete",
        "google_calendar.events.update",
        "google_docs.documents.batch_update",
        "google_docs.documents.create",
    }
)

# Batch 3
VERIFIED_OUTPUT_BATCH_03: frozenset[str] = frozenset(
    {
        "google_drive.files.create",
        "google_drive.files.update",
        "google_drive.permissions.create",
        "google_sheets.spreadsheets.create",
        "google_sheets.values.append",
        "google_sheets.values.update",
        "gorgias.macros.apply",
        "gorgias.tickets.create",
        "gorgias.tickets.reply",
        "greenhouse.candidates.create",
        "gusto.employees.create",
        "gusto.payrolls.run",
        "hootsuite.messages.schedule",
        "hootsuite.messages.update",
        "hubspot.contacts.delete",
        "hubspot.contacts.update",
        "hubspot.deals.delete",
        "hubspot.deals.update",
        "hubspot.notes.create",
        "hubspot.notes.delete",
        "intercom.contacts.create",
        "intercom.conversations.reply",
        "intercom.tickets.create",
        "jira.issues.comment",
        "jira.issues.update",
    }
)

# Batch 4
VERIFIED_OUTPUT_BATCH_04: frozenset[str] = frozenset(
    {
        "linkedin.audience.update",
        "linkedin.leads.submit",
        "mailchimp.campaigns.create",
        "mailchimp.members.add",
        "mailchimp.tags.add",
        "marketo.campaigns.schedule",
        "marketo.leads.create",
        "marketo.leads.update",
        "microsoft365.calendar.events.create",
        "microsoft365.files.upload",
        "microsoft365.mail.send",
        "microsoft365.teams.meetings.create",
        "microsoft365.teams.messages.send",
        "microsoft_teams.meetings.create",
        "microsoft_teams.messages.send",
        "mixpanel.events.track",
        "mixpanel.profiles.set",
        "monday.items.create",
        "monday.items.update",
        "mongodb.documents.insert",
        "mongodb.documents.update",
        "motion.tasks.create",
        "motion.tasks.update",
        "n8n.workflows.activate",
        "n8n.workflows.create",
    }
)

# Batch 5
VERIFIED_OUTPUT_BATCH_05: frozenset[str] = frozenset(
    {
        "netsuite.customers.update",
        "netsuite.journalentries.create",
        "netsuite.salesorders.create",
        "notion.blocks.append",
        "notion.pages.create",
        "notion.pages.update",
        "odoo.invoices.create",
        "odoo.partners.create",
        "odoo.sales.orders.create",
        "outlook.messages.reply",
        "outlook.messages.send",
        "pagerduty.incidents.acknowledge",
        "pagerduty.incidents.add_note",
        "pagerduty.incidents.resolve",
        "pipedrive.deals.create",
        "pipedrive.deals.update",
        "pipedrive.persons.create",
        "pipedrive.persons.update",
        "plaid.link.token.create",
        "plaid.public_token.exchange",
        "postgresql.query.insert",
        "postgresql.query.update",
        "quickbooks.customers.create",
        "quickbooks.invoices.create",
        "quickbooks.payments.create",
    }
)

# Batch 6
VERIFIED_OUTPUT_BATCH_06: frozenset[str] = frozenset(
    {
        "real_estate.handoff.brief",
        "real_estate.listing.publish",
        "real_estate.mls.note",
        "salesforce.accounts.create",
        "salesforce.leads.create",
        "salesforce.leads.update",
        "salesforce.opportunities.create",
        "salesforce.tasks.create",
        "segment.group",
        "segment.identify",
        "segment.track",
        "semrush.position_tracking.add",
        "semrush.projects.create",
        "sendgrid.contacts.upsert",
        "sendgrid.mail.send",
        "slack.chat.update",
        "slack.conversations.create",
        "snowflake.query.insert",
        "snowflake.stages.put",
        "stackadapt.campaigns.create",
        "stackadapt.campaigns.update",
        "stripe.customers.create",
        "stripe.invoices.create",
        "stripe.refunds.create",
        "twilio.calls.create",
    }
)

# Batch 7 (remainder)
VERIFIED_OUTPUT_BATCH_07: frozenset[str] = frozenset(
    {
        "twilio.messages.create",
        "webhook.post",
        "workday.jobs.update",
        "workday.timeoff.request",
        "xero.contacts.create",
        "xero.invoices.create",
        "xero.payments.create",
        "zapier.hooks.trigger",
        "zapier.zaps.enable",
        "zendesk.tickets.add_tags",
        "zendesk.tickets.close",
        "zendesk.tickets.update",
    }
)

VERIFIED_OUTPUT_BATCH_08: frozenset[str] = frozenset(
    {
        "ahrefs.projects.create",
        "ahrefs.rank_tracker.add",
        "ahrefs.brand_radar.prompts.track",
        "ai_visibility_ui.prompts.batch",
        "finseo.prompts.track",
        "hubspot.associations.create",
    }
)

VERIFIED_ADVANCED_OUTPUT_BATCH_14: frozenset[str] = frozenset(
    {
        "ahrefs.brand_radar.exports.run",
        "ai_visibility_ui.captures.export",
        "finseo.exports.run",
    }
)

VERIFIED_OUTPUT_BATCHES: tuple[frozenset[str], ...] = (
    VERIFIED_OUTPUT_BATCH_01,
    VERIFIED_OUTPUT_BATCH_02,
    VERIFIED_OUTPUT_BATCH_03,
    VERIFIED_OUTPUT_BATCH_04,
    VERIFIED_OUTPUT_BATCH_05,
    VERIFIED_OUTPUT_BATCH_06,
    VERIFIED_OUTPUT_BATCH_07,
    VERIFIED_OUTPUT_BATCH_08,
)

CLEARED_OUTPUT_SCHEMA_ACTIONS: frozenset[str] = frozenset().union(*VERIFIED_OUTPUT_BATCHES)

# ---------------------------------------------------------------------------
# Advanced (kind=advanced) write-like actions — cleared in batches of 25
# ---------------------------------------------------------------------------

VERIFIED_ADVANCED_OUTPUT_BATCH_08: frozenset[str] = frozenset(
    {
        "absorb_lms.batch.enroll",
        "adp.batch.workers.sync",
        "airtable.records.delete",
        "airtable.webhooks.create",
        "apollo.contacts.delete",
        "apollo.contacts.update",
        "apollo.sequences.remove",
        "apollo.signals.subscribe",
        "apollo.tasks.create",
        "asana.sections.move",
        "asana.tasks.add_project",
        "asana.tasks.delete",
        "aws_s3.batch.delete",
        "aws_s3.multipart.upload",
        "bamboohr.onboarding.tasks.assign",
        "bamboohr.reports.run",
        "bamboohr.webhooks.create",
        "canva.autofill.create",
        "canva.batch.exports",
        "canva.designs.delete",
        "clay.crm.sync",
        "clickup.goals.update",
        "clickup.tasks.bulk_update",
        "clickup.tasks.delete",
        "clickup.time_entries.create",
    }
)

VERIFIED_ADVANCED_OUTPUT_BATCH_09: frozenset[str] = frozenset(
    {
        "clickup.webhooks.create",
        "confluence.attachments.upload",
        "confluence.pages.move",
        "constant_contact.campaigns.schedule",
        "constant_contact.contacts.delete",
        "constant_contact.lists.add_contacts",
        "constant_contact.tags.apply",
        "email.batch.send",
        "engagebay.tasks.create",
        "figma.batch.images.export",
        "figma.comments.delete",
        "freshdesk.automations.trigger",
        "freshdesk.satisfaction.send",
        "freshdesk.tickets.merge",
        "github.actions.dispatch",
        "github.pulls.close",
        "github.pulls.merge",
        "github.releases.create",
        "gmail.watch.create",
        "google_analytics.funnels.run",
        "google_analytics.realtime.run",
        "google_calendar.events.quick_add",
        "google_docs.documents.insert_table",
        "google_drive.files.export",
        "google_sheets.charts.add",
    }
)

VERIFIED_ADVANCED_OUTPUT_BATCH_10: frozenset[str] = frozenset(
    {
        "google_sheets.pivot.create",
        "google_sheets.values.batch_update",
        "gorgias.rules.trigger",
        "gorgias.satisfaction.request",
        "gorgias.tags.apply",
        "greenhouse.offers.create",
        "gusto.benefits.enroll",
        "hootsuite.approvals.submit",
        "hootsuite.bulk.schedule",
        "hootsuite.inbox.reply",
        "hubspot.deals.update_stage",
        "hubspot.lists.add_contact",
        "hubspot.sequences.enroll",
        "hubspot.tickets.create",
        "intercom.contacts.delete",
        "intercom.notes.create",
        "intercom.series.trigger",
        "intercom.tags.apply",
        "jira.issues.assign",
        "linkedin.conversions.track",
        "mailchimp.automations.trigger",
        "mailchimp.batch.subscribe",
        "mailchimp.segments.add_member",
        "marketo.leads.merge",
        "marketo.lists.add_to_static_list",
    }
)

VERIFIED_ADVANCED_OUTPUT_BATCH_11: frozenset[str] = frozenset(
    {
        "marketo.programs.members.add",
        "microsoft365.excel.workbook.update",
        "microsoft365.sharepoint.files.delete",
        "microsoft365.sharepoint.files.upload",
        "microsoft365.teams.members.add",
        "microsoft365.teams.presence.set",
        "microsoft365.teams.tabs.create",
        "microsoft_teams.members.add",
        "microsoft_teams.presence.set",
        "microsoft_teams.tabs.create",
        "mixpanel.annotations.create",
        "mixpanel.cohorts.export",
        "monday.automations.trigger",
        "monday.items.delete",
        "monday.updates.create",
        "mongodb.aggregation.run",
        "mongodb.change_streams.watch",
        "motion.batch.reschedule",
        "n8n.executions.retry",
        "n8n.webhooks.trigger",
        "netsuite.fulfillment.create",
        "notion.comments.create",
        "notion.databases.create",
        "odoo.invoices.post",
        "odoo.manufacturing.orders.create",
    }
)

VERIFIED_ADVANCED_OUTPUT_BATCH_12: frozenset[str] = frozenset(
    {
        "odoo.partners.update",
        "odoo.sales.orders.confirm",
        "outlook.batch.send",
        "outlook.categories.apply",
        "outlook.rules.create",
        "pagerduty.incidents.escalate",
        "pagerduty.incidents.reassign",
        "pipedrive.deals.update_stage",
        "plaid.transactions.sync",
        "postgresql.batch.upsert",
        "postgresql.migrations.apply",
        "quickbooks.journalentries.create",
        "real_estate.mls.sync",
        "salesforce.accounts.update",
        "salesforce.opportunities.update",
        "salesforce.opportunities.update_stage",
        "semrush.exports.run",
        "sendgrid.batch.send",
        "sendgrid.campaigns.schedule",
        "sendgrid.suppressions.add",
        "slack.files.upload",
        "slack.reactions.add",
        "slack.workflows.trigger",
        "snowflake.batch.copy",
        "snowflake.tasks.run",
    }
)

VERIFIED_ADVANCED_OUTPUT_BATCH_13: frozenset[str] = frozenset(
    {
        "stackadapt.audiences.sync",
        "stackadapt.creatives.upload",
        "stackadapt.reports.export",
        "stripe.checkout.sessions.create",
        "stripe.payment_intents.confirm",
        "stripe.subscriptions.update",
        "twilio.conversations.create",
        "webhook.post.replay",
        "workday.batch.workers.export",
        "workday.learning.enroll",
        "xero.banktransactions.import",
        "zapier.batch.trigger",
        "zapier.interfaces.submit",
        "zapier.tables.rows.upsert",
        "zendesk.macros.apply",
        "zendesk.side_conversations.create",
        "zendesk.tickets.merge",
        "hubspot.lists.create",
    }
)

VERIFIED_ADVANCED_OUTPUT_BATCHES: tuple[frozenset[str], ...] = (
    VERIFIED_ADVANCED_OUTPUT_BATCH_08,
    VERIFIED_ADVANCED_OUTPUT_BATCH_09,
    VERIFIED_ADVANCED_OUTPUT_BATCH_10,
    VERIFIED_ADVANCED_OUTPUT_BATCH_11,
    VERIFIED_ADVANCED_OUTPUT_BATCH_12,
    VERIFIED_ADVANCED_OUTPUT_BATCH_13,
    VERIFIED_ADVANCED_OUTPUT_BATCH_14,
)

CLEARED_ADVANCED_OUTPUT_SCHEMA_ACTIONS: frozenset[str] = frozenset().union(
    *VERIFIED_ADVANCED_OUTPUT_BATCHES
)
