"""Versioned platform Play templates.

Templates describe outcome intent and dependency requirements only. They do not
contain executable workflow steps and cannot execute actions. A tenant/runtime
instance must bind to canonical workflow ids before execution is possible.
"""
from __future__ import annotations

from app.plays.contracts import PlayDefinition


CUSTOMER_RESCUE = PlayDefinition(
    key="customer-rescue",
    name="Customer Rescue",
    version="1",
    objective="Find customers with credible retention risk, assemble evidence, and prepare an intervention.",
    required_signals=("prediction_generated",),
    required_connector_groups=(
        ("hubspot", "salesforce"),
        ("zendesk", "intercom", "freshdesk"),
    ),
    required_read_action_groups=(
        ("hubspot.contacts.search", "salesforce.contacts.search"),
        ("zendesk.tickets.list", "intercom.conversations.list", "freshdesk.tickets.list"),
    ),
    write_action_groups=(
        ("hubspot.contacts.update", "salesforce.accounts.update"),
        ("zendesk.tickets.update", "intercom.conversations.reply", "freshdesk.tickets.update"),
    ),
)


REVENUE_RECOVERY = PlayDefinition(
    key="revenue-recovery",
    name="Revenue Recovery",
    version="1",
    objective="Find stalled or recoverable revenue and assemble source evidence before any action.",
    required_connector_groups=(("stripe", "quickbooks"),),
    required_read_action_groups=(("stripe.invoices.list", "quickbooks.invoices.list"),),
    write_action_groups=(
        ("stripe.subscriptions.update", "quickbooks.invoices.create", "hubspot.deals.update"),
    ),
    outcome_metrics=("arr",),
)


MARKETING_PERFORMANCE = PlayDefinition(
    key="marketing-performance",
    name="Marketing Performance",
    version="1",
    objective="Connect marketing spend and engagement evidence to lead quality and downstream pipeline.",
    required_connector_groups=(
        ("google_ads", "meta_marketing"),
        ("google_analytics",),
    ),
    required_read_action_groups=(
        ("google_ads.reports.performance", "meta_marketing.campaigns.list"),
        ("google_analytics.reports.run",),
    ),
    outcome_metrics=("mql", "cac"),
)


CLIENT_RISK_RADAR = PlayDefinition(
    key="client-risk-radar",
    name="Client Risk Radar",
    version="1",
    objective="Combine service, commercial, finance, and security signals to identify accounts that need intervention before churn or escalation.",
    required_signals=("prediction_generated",),
    required_connector_groups=(
        ("hubspot", "salesforce"),
        ("zendesk", "intercom", "freshdesk", "front", "freshservice"),
    ),
    optional_connectors=("quickbooks", "stripe", "huntress", "sentinelone", "crowdstrike"),
    outcome_metrics=("customer_health", "revenue_at_risk", "sla_compliance"),
)


REVENUE_LEAK_HUNTER = PlayDefinition(
    key="revenue-leak-hunter",
    name="Revenue Leak Hunter",
    version="1",
    objective="Find recoverable revenue hidden in overdue invoices, stalled opportunities, renewals, billing exceptions, and operational gaps.",
    required_connector_groups=(
        ("stripe", "quickbooks", "xero", "sage_intacct"),
        ("hubspot", "salesforce"),
    ),
    optional_connectors=("chargebee", "recurly", "pax8"),
    outcome_metrics=("revenue_recovered", "revenue_at_risk", "dso"),
)


PROCESS_DRIFT_DETECTOR = PlayDefinition(
    key="process-drift-detector",
    name="Process Drift Detector",
    version="1",
    objective="Detect repeated departures from SOPs, SLAs, approval policy, and expected workflow behavior before they become systemic failures.",
    required_signals=("workflow_completed",),
    optional_connectors=("slack", "microsoft_teams", "jira", "servicenow", "freshservice"),
    outcome_metrics=("policy_compliance", "exception_rate", "sla_compliance"),
)


KNOWLEDGE_GAP_MINER = PlayDefinition(
    key="knowledge-gap-miner",
    name="Knowledge Gap Miner",
    version="1",
    objective="Turn repeated questions, failed retrievals, escalations, and unresolved cases into prioritized knowledge and SOP improvement opportunities.",
    required_signals=("workflow_failed",),
    optional_connectors=("zendesk", "intercom", "freshdesk", "front", "slack", "microsoft_teams"),
    outcome_metrics=("knowledge_gap_rate", "escalation_rate", "repeat_issue_rate"),
)


EXECUTIVE_MORNING_COMMAND_BRIEF = PlayDefinition(
    key="executive-morning-command-brief",
    name="Executive Morning Command Brief",
    version="1",
    objective="Produce a concise cross-department operating brief covering material changes, risks, actions already completed, approvals required, and emerging opportunities.",
    optional_connectors=(
        "hubspot", "salesforce", "quickbooks", "xero", "zendesk", "freshservice",
        "slack", "microsoft_teams", "google_analytics", "google_ads",
    ),
    outcome_metrics=("revenue_at_risk", "cash_risk", "sla_compliance", "automation_rate"),
)


AUTONOMOUS_EXCEPTION_MANAGER = PlayDefinition(
    key="autonomous-exception-manager",
    name="Autonomous Exception Manager",
    version="1",
    objective="Detect failed or ambiguous workflow states, investigate the exception, attempt policy-safe recovery, verify the result, and escalate only when required.",
    required_signals=("workflow_failed",),
    optional_connectors=("slack", "microsoft_teams", "jira", "servicenow"),
    outcome_metrics=("exception_resolution_time", "auto_recovery_rate", "human_escalation_rate"),
)


PLATFORM_PLAY_TEMPLATES: tuple[PlayDefinition, ...] = (
    CUSTOMER_RESCUE,
    REVENUE_RECOVERY,
    MARKETING_PERFORMANCE,
    CLIENT_RISK_RADAR,
    REVENUE_LEAK_HUNTER,
    PROCESS_DRIFT_DETECTOR,
    KNOWLEDGE_GAP_MINER,
    EXECUTIVE_MORNING_COMMAND_BRIEF,
    AUTONOMOUS_EXCEPTION_MANAGER,
)


def get_platform_play(key: str) -> PlayDefinition | None:
    wanted = str(key or "").strip().lower()
    for play in PLATFORM_PLAY_TEMPLATES:
        if play.key == wanted:
            return play
    return None
