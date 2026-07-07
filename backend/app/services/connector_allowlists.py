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
        "asana.stories.create",
        "aws_s3.objects.delete",
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
        "gusto.employees.create",
        "gusto.payrolls.run",
        "hootsuite.messages.schedule",
        "hootsuite.messages.update",
        "microsoft_teams.meetings.create",
        "microsoft_teams.messages.send",
        "plaid.link.token.create",
        "plaid.public_token.exchange",
        "real_estate.handoff.brief",
        "real_estate.listing.publish",
        "real_estate.mls.note",
        "semrush.position_tracking.add",
        "semrush.projects.create",
        "stackadapt.campaigns.create",
        "stackadapt.campaigns.update",
        "workday.jobs.update",
        "workday.timeoff.request",
    }
)
