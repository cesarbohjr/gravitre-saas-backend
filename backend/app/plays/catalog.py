"""Versioned platform Play templates.

Templates describe outcome intent and dependency requirements only. They do not
contain executable workflow steps and cannot execute actions. A tenant/runtime
instance must bind to canonical workflow ids before execution is possible.
"""
from __future__ import annotations

from app.plays.contracts import PlayDefinition
from app.marketplace.marketplace3.department_portfolio import PACK_SPECS


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
    objective="Prioritize security alerts using identity, endpoint, severity, business-impact, and recent activity evidence.",
    required_connector_groups=(("okta",),),
    optional_connectors=("huntress", "sentinelone", "crowdstrike", "connectsecure", "microsoft_intune"),
    outcome_metrics=("mttd", "triage_time", "false_positive_rate"),
)


VULNERABILITY_PRIORITIZER = PlayDefinition(
    key="vulnerability-prioritizer",
    name="Vulnerability Prioritizer",
    version="1",
    objective="Rank vulnerabilities by exploitability, asset criticality, identity exposure, recurrence, and business impact.",
    optional_connectors=("connectsecure", "microsoft_intune", "huntress", "sentinelone", "crowdstrike"),
    outcome_metrics=("critical_vulnerability_backlog", "remediation_sla", "risk_reduction"),
)


IDENTITY_COMPROMISE_INVESTIGATOR = PlayDefinition(
    key="identity-compromise-investigator",
    name="Identity Compromise Investigator",
    version="1",
    objective="Correlate identity events and user context to investigate suspicious sign-ins, risk changes, and account compromise indicators.",
    required_connector_groups=(("okta",),),
    optional_connectors=("duo", "microsoft_365", "microsoft_intune", "crowdstrike", "sentinelone"),
    outcome_metrics=("investigation_time", "identity_risk_cases", "mttd"),
)


CONTAINMENT_COORDINATOR = PlayDefinition(
    key="containment-coordinator",
    name="Containment Coordinator",
    version="1",
    objective="Assemble containment options, affected identities/assets, approval requirements, and a verified execution plan without bypassing human authority.",
    required_connector_groups=(("okta",),),
    optional_connectors=("sentinelone", "crowdstrike", "microsoft_intune", "huntress"),
    outcome_metrics=("containment_time", "approval_latency", "mttr"),
)


SECURITY_REMEDIATION_TRACKER = PlayDefinition(
    key="security-remediation-tracker",
    name="Security Remediation Tracker",
    version="1",
    objective="Track open remediation work to source-of-record confirmation and escalate overdue or unverifiable remediation.",
    optional_connectors=("connectsecure", "microsoft_intune", "huntress", "sentinelone", "crowdstrike", "jira"),
    outcome_metrics=("remediation_sla", "open_security_actions", "verification_inconclusive_rate"),
)


SECURITY_INCIDENT_BRIEF = PlayDefinition(
    key="security-incident-brief",
    name="Security Incident Brief",
    version="1",
    objective="Maintain an evidence-backed incident timeline, impact summary, current containment state, decisions, and required approvals.",
    required_connector_groups=(("okta",),),
    optional_connectors=("huntress", "sentinelone", "crowdstrike", "slack", "microsoft_teams"),
    outcome_metrics=("incident_update_latency", "mttr", "stakeholder_update_rate"),
)


POST_INCIDENT_REVIEW = PlayDefinition(
    key="post-incident-review",
    name="Post-Incident Review",
    version="1",
    objective="Produce a source-backed post-incident review with root cause, control gaps, remediation owners, and measurable prevention actions.",
    optional_connectors=("okta", "huntress", "sentinelone", "crowdstrike", "jira"),
    outcome_metrics=("repeat_incident_rate", "remediation_completion_rate", "control_gap_count"),
)


SECURITY_POSTURE_WATCH = PlayDefinition(
    key="security-posture-watch",
    name="Security Posture Watch",
    version="1",
    objective="Continuously monitor security posture trends and surface material deterioration, recurring identity risk, overdue remediation, and emerging control gaps.",
    required_connector_groups=(("okta",),),
    optional_connectors=("connectsecure", "microsoft_intune", "huntress", "sentinelone", "crowdstrike"),
    outcome_metrics=("risk_score", "critical_vulnerability_backlog", "identity_risk_cases", "remediation_sla"),
)


def _department_portfolio_plays() -> tuple[PlayDefinition, ...]:
    plays: list[PlayDefinition] = []
    for spec in PACK_SPECS.values():
        required_connector_groups = tuple((connector,) for connector in spec["connectors"])
        optional_connectors = tuple(spec["optional"])
        for key, name, description, action, kpi_key in spec["plays"]:
            plays.append(
                PlayDefinition(
                    key=key,
                    name=name,
                    version="1",
                    objective=description,
                    required_connector_groups=required_connector_groups,
                    optional_connectors=optional_connectors,
                    required_read_action_groups=((action,),),
                    outcome_metrics=(kpi_key,),
                )
            )
    return tuple(plays)


DEPARTMENT_PORTFOLIO_PLAYS = _department_portfolio_plays()


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
    SECURITY_REMEDIATION_TRACKER,
    SECURITY_INCIDENT_BRIEF,
    POST_INCIDENT_REVIEW,
    SECURITY_POSTURE_WATCH,
    *DEPARTMENT_PORTFOLIO_PLAYS,
)


def get_platform_play(key: str) -> PlayDefinition | None:
    wanted = str(key or "").strip().lower()
    for play in PLATFORM_PLAY_TEMPLATES:
        if play.key == wanted:
            return play
    return None
