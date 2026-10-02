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


INTELLIGENT_TICKET_INTAKE = PlayDefinition(
    key="intelligent-ticket-intake",
    name="Intelligent Ticket Intake",
    version="1",
    objective="Classify, prioritize, enrich, and route new service tickets using client, user, asset, SLA, and sentiment context.",
    required_connector_groups=(("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"),),
    optional_connectors=("microsoft_intune", "jumpcloud", "jamf_pro", "microsoft_365"),
    outcome_metrics=("mtta", "sla_compliance", "automation_rate"),
)


RESOLUTION_COPILOT = PlayDefinition(
    key="resolution-copilot",
    name="Resolution Copilot",
    version="1",
    objective="Assemble ticket history, device context, runbooks, and prior resolutions into an evidence-backed remediation path.",
    required_connector_groups=(("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"),),
    optional_connectors=("microsoft_intune", "jumpcloud", "jamf_pro", "huntress", "sentinelone", "crowdstrike"),
    outcome_metrics=("mttr", "first_contact_resolution", "automation_rate"),
)


SLA_RESCUE = PlayDefinition(
    key="sla-rescue",
    name="SLA Rescue",
    version="1",
    objective="Detect service work approaching breach, identify why it is stalled, and coordinate a policy-safe intervention before the SLA is missed.",
    required_connector_groups=(("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"),),
    optional_connectors=("slack", "microsoft_teams"),
    outcome_metrics=("sla_compliance", "tickets_rescued", "mttr"),
)


STALE_TICKET_RECOVERY = PlayDefinition(
    key="stale-ticket-recovery",
    name="Stale Ticket Recovery",
    version="1",
    objective="Find tickets stalled on technicians, customers, vendors, approvals, or missing information and restart the correct next step.",
    required_connector_groups=(("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"),),
    optional_connectors=("slack", "microsoft_teams", "microsoft_365"),
    outcome_metrics=("backlog", "stale_ticket_rate", "mttr"),
)


RECURRING_PROBLEM_HUNTER = PlayDefinition(
    key="recurring-problem-hunter",
    name="Recurring Problem Hunter",
    version="1",
    objective="Cluster repeated incidents across clients, users, and assets to identify root recurring problems and preventive automation opportunities.",
    required_connector_groups=(("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"),),
    optional_connectors=("microsoft_intune", "huntress", "sentinelone", "connectsecure"),
    outcome_metrics=("repeat_issue_rate", "reopen_rate", "prevented_incidents"),
)


CLIENT_COMMUNICATION_MANAGER = PlayDefinition(
    key="client-communication-manager",
    name="Client Communication Manager",
    version="1",
    objective="Prepare timely, context-aware client updates from verified service status, SLA posture, sentiment, and business impact.",
    required_connector_groups=(("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"),),
    optional_connectors=("slack", "microsoft_teams", "microsoft_365"),
    outcome_metrics=("customer_update_latency", "csat", "sla_compliance"),
)


SERVICE_DESK_OPTIMIZATION_REVIEW = PlayDefinition(
    key="service-desk-optimization-review",
    name="Service Desk Optimization Review",
    version="1",
    objective="Review service desk performance, recurring bottlenecks, automation coverage, and technician workload to recommend measurable operating improvements.",
    required_connector_groups=(("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"),),
    optional_connectors=("slack", "microsoft_teams"),
    outcome_metrics=("mtta", "mttr", "sla_compliance", "automation_rate", "reopen_rate", "backlog"),
)


SECURITY_ALERT_TRIAGE = PlayDefinition(
    key="security-alert-triage",
    name="Security Alert Triage",
    version="1",
    objective="Correlate endpoint, identity, vulnerability, and service context to prioritize security alerts and suppress obvious noise.",
    required_connector_groups=(("huntress", "sentinelone", "crowdstrike"),),
    optional_connectors=("connectsecure", "okta", "duo", "jumpcloud", "microsoft_intune"),
    outcome_metrics=("mttd", "false_positive_rate", "security_automation_rate"),
)


VULNERABILITY_PRIORITIZER = PlayDefinition(
    key="vulnerability-prioritizer",
    name="Vulnerability Prioritizer",
    version="1",
    objective="Rank vulnerabilities using exploitability, asset importance, exposure, identity context, and business impact.",
    required_connector_groups=(("connectsecure",),),
    optional_connectors=("huntress", "sentinelone", "crowdstrike"),
    outcome_metrics=("critical_exposure_count", "remediation_sla"),
)


IDENTITY_COMPROMISE_INVESTIGATOR = PlayDefinition(
    key="identity-compromise-investigator",
    name="Identity Compromise Investigator",
    version="1",
    objective="Assemble identity, endpoint, MFA, directory, and recent activity evidence for suspected account compromise.",
    required_connector_groups=(("okta", "duo", "jumpcloud"),),
    optional_connectors=("microsoft_intune", "sentinelone", "crowdstrike"),
    outcome_metrics=("mttd", "identity_risk_open", "containment_time"),
)


CONTAINMENT_COORDINATOR = PlayDefinition(
    key="containment-coordinator",
    name="Containment Coordinator",
    version="1",
    objective="Prepare the smallest effective security containment plan and keep consequential actions approval-governed and source-of-record verified.",
    required_connector_groups=(("huntress", "sentinelone", "crowdstrike"),),
    optional_connectors=("okta", "duo", "jumpcloud", "microsoft_intune"),
    outcome_metrics=("containment_time", "verified_containments", "mttr_security"),
)


REMEDIATION_TRACKER = PlayDefinition(
    key="remediation-tracker",
    name="Remediation Tracker",
    version="1",
    objective="Track security remediation through completion and surface stalled, reopened, or SLA-risk findings.",
    required_connector_groups=(("connectsecure", "huntress", "sentinelone", "crowdstrike"),),
    outcome_metrics=("remediation_sla", "critical_exposure_count", "mttr_security"),
)


SECURITY_INCIDENT_BRIEF = PlayDefinition(
    key="security-incident-brief",
    name="Security Incident Brief",
    version="1",
    objective="Maintain a concise verified security incident timeline, impact summary, decisions, owners, and evidence gaps.",
    required_connector_groups=(("huntress", "sentinelone", "crowdstrike"),),
    optional_connectors=("okta", "duo", "jumpcloud"),
    outcome_metrics=("mttd", "containment_time", "mttr_security"),
)


POST_INCIDENT_REVIEW = PlayDefinition(
    key="post-incident-review",
    name="Post-Incident Review",
    version="1",
    objective="Produce a root-cause and control-improvement review from a verified incident timeline and remediation evidence.",
    outcome_metrics=("incident_recurrence_rate", "mttr_security"),
)


SECURITY_POSTURE_WATCH = PlayDefinition(
    key="security-posture-watch",
    name="Security Posture Watch",
    version="1",
    objective="Monitor cross-system security posture for deterioration, concentrated risk, overdue remediation, and emerging patterns.",
    optional_connectors=("connectsecure", "huntress", "sentinelone", "crowdstrike", "okta", "duo", "jumpcloud", "microsoft_intune"),
    outcome_metrics=("critical_exposure_count", "identity_risk_open", "remediation_sla", "security_automation_rate"),
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
    INTELLIGENT_TICKET_INTAKE,
    RESOLUTION_COPILOT,
    SLA_RESCUE,
    STALE_TICKET_RECOVERY,
    RECURRING_PROBLEM_HUNTER,
    CLIENT_COMMUNICATION_MANAGER,
    SERVICE_DESK_OPTIMIZATION_REVIEW,
    SECURITY_ALERT_TRIAGE,
    VULNERABILITY_PRIORITIZER,
    IDENTITY_COMPROMISE_INVESTIGATOR,
    CONTAINMENT_COORDINATOR,
    REMEDIATION_TRACKER,
    SECURITY_INCIDENT_BRIEF,
    POST_INCIDENT_REVIEW,
    SECURITY_POSTURE_WATCH,
)


def get_platform_play(key: str) -> PlayDefinition | None:
    wanted = str(key or "").strip().lower()
    for play in PLATFORM_PLAY_TEMPLATES:
        if play.key == wanted:
            return play
    return None
