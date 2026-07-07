"""Explicit governance debt allowlists — shrink by removing entries after fixing debt."""
from __future__ import annotations

ORPHAN_HANDLER_ALLOWLIST: frozenset[str] = frozenset(
    {
    }
)

API_IMPORT_EXCEPTION_ALLOWLIST: frozenset[str] = frozenset(
    {
    }
)

PENDING_WORKFLOW_SCHEMA_ALLOWLIST: frozenset[str] = frozenset(
    {
        "absorb_lms.courses.create",
        "absorb_lms.enrollments.create",
        "adp.profile.update",
        "adp.timecards.submit",
        "apollo.sequences.add",
        "asana.stories.create",
        "aws_s3.objects.delete",
        "aws_s3.objects.put",
        "bamboohr.employees.create",
        "bamboohr.timeoff.requests.create",
        "canva.designs.create",
        "canva.exports.create",
        "clay.enrichments.request",
        "clay.leads.push",
        "clio.conflict.checklist",
        "clio.intake.tasks",
        "clio.matters.create",
        "clio.tasks.create",
        "confluence.labels.add",
        "constant_contact.campaigns.create",
        "constant_contact.contacts.create",
        "constant_contact.contacts.update",
        "email.send",
        "engagebay.contacts.create",
        "engagebay.contacts.update",
        "fhir.prior_auth.checklist",
        "figma.comments.create",
        "figma.dev_resources.create",
        "google_analytics.audiences.create",
        "google_analytics.conversions.create",
        "gusto.employees.create",
        "gusto.payrolls.run",
        "hootsuite.messages.schedule",
        "hootsuite.messages.update",
        "linkedin.audience.update",
        "linkedin.leads.submit",
        "microsoft_teams.meetings.create",
        "microsoft_teams.messages.send",
        "mixpanel.events.track",
        "mixpanel.profiles.set",
        "mongodb.documents.insert",
        "mongodb.documents.update",
        "motion.tasks.update",
        "n8n.workflows.activate",
        "n8n.workflows.create",
        "netsuite.customers.update",
        "netsuite.journalentries.create",
        "odoo.invoices.create",
        "odoo.partners.create",
        "odoo.sales.orders.create",
        "pagerduty.incidents.add_note",
        "plaid.link.token.create",
        "plaid.public_token.exchange",
        "postgresql.query.insert",
        "postgresql.query.update",
        "real_estate.handoff.brief",
        "real_estate.listing.publish",
        "real_estate.mls.note",
        "semrush.position_tracking.add",
        "semrush.projects.create",
        "snowflake.query.insert",
        "snowflake.stages.put",
        "stackadapt.campaigns.create",
        "stackadapt.campaigns.update",
        "workday.jobs.update",
        "workday.timeoff.request",
        "zapier.hooks.trigger",
        "zapier.zaps.enable",
    }
)
