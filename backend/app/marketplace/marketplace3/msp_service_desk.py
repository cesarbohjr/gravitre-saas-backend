"""Marketplace 3.0 flagship blueprint: MSP Service Desk.

This blueprint is intentionally not seeded into the public Marketplace yet.
It must pass Marketplace 3.0 certification before publication.
"""
from __future__ import annotations

from typing import Any


MSP_SERVICE_DESK_PLAY_KEYS = (
    "intelligent-ticket-intake",
    "resolution-copilot",
    "sla-rescue",
    "stale-ticket-recovery",
    "recurring-problem-hunter",
    "client-communication-manager",
    "knowledge-gap-miner",
    "service-desk-optimization-review",
)


def _agent_step(step_id: str, name: str, agent_seed: str, task: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": {
            "agent_seed": agent_seed,
            "task": task,
        },
    }


def _play(
    key: str,
    name: str,
    description: str,
    *,
    kpis: list[str],
    outcome_event: str,
    trigger: dict[str, Any],
    agent_seed: str,
    task: str,
    approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "description": description,
        "trigger": trigger,
        "workflow_steps": [
            _agent_step(
                f"{key}-analyze",
                f"{name} analysis",
                agent_seed,
                task,
            )
        ],
        "outcome_events": [outcome_event],
        "kpi_keys": kpis,
        "approvals": approvals or [],
        "verification": {
            "mode": "source_of_record",
            "provider_acceptance_is_terminal": False,
        },
    }


def build_msp_service_desk_outcome_pack_config() -> dict[str, Any]:
    kpis = [
        {
            "key": "mtta",
            "label": "Mean time to acknowledge",
            "unit": "minutes",
            "direction": "decrease",
            "source": "service_tickets",
        },
        {
            "key": "mttr",
            "label": "Mean time to resolve",
            "unit": "minutes",
            "direction": "decrease",
            "source": "service_tickets",
        },
        {
            "key": "sla_compliance",
            "label": "SLA compliance",
            "unit": "percent",
            "direction": "increase",
            "source": "service_tickets",
        },
        {
            "key": "first_contact_resolution",
            "label": "First-contact resolution",
            "unit": "percent",
            "direction": "increase",
            "source": "service_tickets",
        },
        {
            "key": "backlog",
            "label": "Open ticket backlog",
            "unit": "count",
            "direction": "decrease",
            "source": "service_tickets",
        },
        {
            "key": "reopen_rate",
            "label": "Ticket reopen rate",
            "unit": "percent",
            "direction": "decrease",
            "source": "service_tickets",
        },
        {
            "key": "automation_rate",
            "label": "Service desk automation rate",
            "unit": "percent",
            "direction": "increase",
            "source": "play_runs",
        },
        {
            "key": "tickets_rescued",
            "label": "Tickets rescued before SLA breach",
            "unit": "count",
            "direction": "increase",
            "source": "play_outcomes",
        },
        {
            "key": "repeat_issue_rate",
            "label": "Repeat issue rate",
            "unit": "percent",
            "direction": "decrease",
            "source": "service_tickets",
        },
        {
            "key": "knowledge_gap_rate",
            "label": "Knowledge gap rate",
            "unit": "percent",
            "direction": "decrease",
            "source": "play_outcomes",
        },
        {
            "key": "customer_update_latency",
            "label": "Customer update latency",
            "unit": "minutes",
            "direction": "decrease",
            "source": "service_tickets",
        },
        {
            "key": "csat",
            "label": "Customer satisfaction",
            "unit": "score",
            "direction": "increase",
            "source": "service_tickets",
        },
        {
            "key": "stale_ticket_rate",
            "label": "Stale ticket rate",
            "unit": "percent",
            "direction": "decrease",
            "source": "service_tickets",
        },
        {
            "key": "prevented_incidents",
            "label": "Prevented recurring incidents",
            "unit": "count",
            "direction": "increase",
            "source": "play_outcomes",
        },
    ]

    plays = [
        _play(
            "intelligent-ticket-intake",
            "Intelligent Ticket Intake",
            "Classify, prioritize, enrich, and route new service tickets using client, user, asset, SLA, and sentiment context.",
            kpis=["mtta", "sla_compliance", "automation_rate"],
            outcome_event="ticket_intake_completed",
            trigger={"type": "event", "event": "ticket.created"},
            agent_seed="agent:msp-service-coordinator",
            task=(
                "Review new ticket context, identify category and urgency, detect SLA/business impact, "
                "and prepare the correct queue/routing recommendation. Do not claim a provider update "
                "until the source of record confirms it."
            ),
        ),
        _play(
            "resolution-copilot",
            "Resolution Copilot",
            "Assemble ticket history, device context, runbooks, and prior resolutions into an evidence-backed remediation path.",
            kpis=["mttr", "first_contact_resolution", "automation_rate"],
            outcome_event="resolution_path_prepared",
            trigger={"type": "event", "event": "ticket.assigned"},
            agent_seed="agent:msp-resolution-engineer",
            task=(
                "Assemble evidence from service history and assigned runbooks. Produce a remediation "
                "plan, identify missing evidence, and separate recommendations from actions."
            ),
        ),
        _play(
            "sla-rescue",
            "SLA Rescue",
            "Detect service work approaching breach and coordinate a policy-safe intervention before the SLA is missed.",
            kpis=["sla_compliance", "tickets_rescued", "mttr"],
            outcome_event="ticket_sla_saved",
            trigger={"type": "threshold", "metric": "sla_minutes_remaining", "lte": 60},
            agent_seed="agent:msp-service-coordinator",
            task=(
                "Investigate why the ticket is stalled, identify the correct owner/escalation, and "
                "prepare a rescue action. Any consequential write requires approval and source-of-record verification."
            ),
            approvals=[{"when": "external_write", "required": True}],
        ),
        _play(
            "stale-ticket-recovery",
            "Stale Ticket Recovery",
            "Find tickets stalled on technicians, customers, vendors, approvals, or missing information and restart the correct next step.",
            kpis=["backlog", "stale_ticket_rate", "mttr"],
            outcome_event="stale_ticket_reactivated",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:msp-service-coordinator",
            task=(
                "Classify why each stale ticket is blocked and recommend the smallest valid next step. "
                "Do not fabricate customer/vendor responses."
            ),
        ),
        _play(
            "recurring-problem-hunter",
            "Recurring Problem Hunter",
            "Cluster repeated incidents to identify root recurring problems and preventive automation opportunities.",
            kpis=["repeat_issue_rate", "reopen_rate", "prevented_incidents"],
            outcome_event="recurring_problem_identified",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:msp-service-analyst",
            task=(
                "Cluster repeated issues by client, user, asset, category, and symptoms. Produce evidence "
                "for a problem record, knowledge update, or preventive automation opportunity."
            ),
        ),
        _play(
            "client-communication-manager",
            "Client Communication Manager",
            "Prepare timely, context-aware client updates from verified service status and business impact.",
            kpis=["customer_update_latency", "csat", "sla_compliance"],
            outcome_event="client_update_prepared",
            trigger={"type": "event", "event": "ticket.status_changed"},
            agent_seed="agent:msp-service-coordinator",
            task=(
                "Draft a concise client update using only verified ticket status, known impact, and next "
                "steps. Flag uncertainty rather than inventing progress."
            ),
            approvals=[{"when": "send_external_message", "required": True}],
        ),
        _play(
            "knowledge-gap-miner",
            "Knowledge Gap Miner",
            "Turn repeated escalations, unresolved searches, and failed resolutions into prioritized knowledge improvements.",
            kpis=["knowledge_gap_rate", "repeat_issue_rate", "first_contact_resolution"],
            outcome_event="knowledge_gap_identified",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:msp-service-analyst",
            task=(
                "Analyze repeated unresolved cases, escalations, and missing runbook evidence. Propose "
                "specific knowledge articles, SOP changes, or decision rules with source examples."
            ),
        ),
        _play(
            "service-desk-optimization-review",
            "Service Desk Optimization Review",
            "Review service desk performance, bottlenecks, automation coverage, and workload to recommend measurable improvements.",
            kpis=["mtta", "mttr", "sla_compliance", "automation_rate", "reopen_rate", "backlog"],
            outcome_event="service_desk_optimization_reviewed",
            trigger={"type": "scheduled", "cadence": "weekly"},
            agent_seed="agent:msp-service-analyst",
            task=(
                "Review KPI trends and Play outcomes. Identify the highest-value operational bottlenecks, "
                "automation candidates, and workflow changes, tied to measurable baseline evidence."
            ),
        ),
    ]

    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": (
                "MSP service desks lose technician capacity to manual triage, stale work, repeated issues, "
                "inconsistent client communication, and preventable SLA breaches."
            ),
            "target_outcome": (
                "Reduce service desk response/resolution time while increasing SLA compliance, first-contact "
                "resolution, automation coverage, and measurable technician capacity."
            ),
            "baseline_metric": "mttr",
            "success_criteria": [
                "All eight Plays install into the canonical Gravitre Play/workflow runtime.",
                "Every consequential external write remains approval-governed and source-of-record verified.",
                "The installed dashboard resolves every declared KPI from connected service data or verified Play outcomes.",
                "At least one verified service outcome event is produced before Outcome Verified certification.",
            ],
            "outcome_events": [
                "ticket_intake_completed",
                "resolution_path_prepared",
                "ticket_sla_saved",
                "stale_ticket_reactivated",
                "recurring_problem_identified",
                "client_update_prepared",
                "knowledge_gap_identified",
                "service_desk_optimization_reviewed",
            ],
            "kpis": kpis,
            "verification_required": True,
        },
        "agents": [
            {
                "seed_label": "agent:msp-service-coordinator",
                "name": "MSP Service Coordinator",
                "purpose": "Coordinate ticket intake, SLA rescue, stale work recovery, and client communication.",
                "role": "Service Desk Coordinator",
                "department": "MSP Service Desk",
                "capabilities": ["triage", "routing", "sla-management", "client-communication"],
                "systems": ["zendesk", "freshservice", "servicenow", "halo_psa", "autotask", "connectwise", "syncro"],
            },
            {
                "seed_label": "agent:msp-resolution-engineer",
                "name": "MSP Resolution Engineer",
                "purpose": "Assemble technical evidence and remediation paths from service history, device context, and runbooks.",
                "role": "Technical Resolution",
                "department": "MSP Service Desk",
                "capabilities": ["diagnosis", "remediation-planning", "runbook-retrieval"],
                "systems": ["microsoft_intune", "jumpcloud", "jamf_pro", "huntress", "sentinelone", "crowdstrike"],
            },
            {
                "seed_label": "agent:msp-service-analyst",
                "name": "MSP Service Analyst",
                "purpose": "Identify recurring problems, knowledge gaps, KPI trends, and service optimization opportunities.",
                "role": "Service Operations Analyst",
                "department": "MSP Service Desk",
                "capabilities": ["trend-analysis", "problem-management", "knowledge-gap-analysis", "kpi-review"],
                "systems": ["zendesk", "freshservice", "servicenow", "halo_psa", "autotask", "connectwise", "syncro"],
            },
        ],
        "plays": plays,
        "knowledge": [
            {
                "seed_label": "service-runbooks",
                "title": "Service Desk Runbooks",
                "type": "manual",
                "metadata": {"purpose": "Technical troubleshooting and remediation procedures."},
            },
            {
                "seed_label": "sla-policy",
                "title": "SLA and Escalation Policy",
                "type": "manual",
                "metadata": {"purpose": "Priority, SLA, escalation, and ownership rules."},
            },
            {
                "seed_label": "client-comms",
                "title": "Client Communication Standards",
                "type": "manual",
                "metadata": {"purpose": "Approved tone, update cadence, and communication templates."},
            },
            {
                "seed_label": "known-issues",
                "title": "Known Issues and Problem Records",
                "type": "manual",
                "metadata": {"purpose": "Recurring issue patterns and known remediation history."},
            },
        ],
        "dataset": {
            "entities": [
                {
                    "name": "service_tickets",
                    "source": "psa_or_service_desk_connector",
                    "primary_key": "ticket_id",
                    "fields": [
                        "ticket_id", "client_id", "requester_id", "asset_id", "category", "priority",
                        "status", "assigned_to", "created_at", "acknowledged_at", "resolved_at",
                        "sla_due_at", "reopened", "csat_score", "last_customer_update_at",
                    ],
                },
                {
                    "name": "play_outcomes",
                    "source": "gravitre_verified_outcomes",
                    "primary_key": "outcome_id",
                    "fields": ["outcome_id", "play_key", "ticket_id", "status", "verified_at", "metric_delta"],
                },
            ],
            "metrics": [
                {"key": "mtta", "label": "MTTA", "formula": "avg(acknowledged_at - created_at)", "unit": "minutes"},
                {"key": "mttr", "label": "MTTR", "formula": "avg(resolved_at - created_at)", "unit": "minutes"},
                {"key": "sla_compliance", "label": "SLA compliance", "formula": "resolved_within_sla / resolved_total * 100", "unit": "percent"},
                {"key": "first_contact_resolution", "label": "First-contact resolution", "formula": "first_contact_resolved / resolved_total * 100", "unit": "percent"},
                {"key": "backlog", "label": "Backlog", "formula": "count(open_tickets)", "unit": "count"},
                {"key": "reopen_rate", "label": "Reopen rate", "formula": "reopened_tickets / resolved_total * 100", "unit": "percent"},
                {"key": "automation_rate", "label": "Automation rate", "formula": "verified_automated_outcomes / eligible_work * 100", "unit": "percent"},
                {"key": "tickets_rescued", "label": "Tickets rescued", "formula": "count(ticket_sla_saved)", "unit": "count"},
                {"key": "repeat_issue_rate", "label": "Repeat issue rate", "formula": "repeat_issue_tickets / ticket_total * 100", "unit": "percent"},
                {"key": "knowledge_gap_rate", "label": "Knowledge gap rate", "formula": "knowledge_gap_outcomes / analyzed_cases * 100", "unit": "percent"},
                {"key": "customer_update_latency", "label": "Customer update latency", "formula": "avg(last_customer_update_at - status_changed_at)", "unit": "minutes"},
                {"key": "csat", "label": "CSAT", "formula": "avg(csat_score)", "unit": "score"},
                {"key": "stale_ticket_rate", "label": "Stale ticket rate", "formula": "stale_tickets / open_tickets * 100", "unit": "percent"},
                {"key": "prevented_incidents", "label": "Prevented incidents", "formula": "count(verified_preventive_outcomes)", "unit": "count"},
            ],
        },
        "dashboard": {
            "title": "MSP Service Desk Command Center",
            "refresh_mode": "event",
            "metrics": [
                {
                    "kpi_key": row["key"],
                    "label": row["label"],
                    "visualization": "trend" if row["unit"] in {"minutes", "percent", "score"} else "metric",
                    "description": f"Marketplace 3.0 service KPI: {row['label']}.",
                }
                for row in kpis
            ],
        },
        "skills": [
            "ticket-triage",
            "incident-diagnosis",
            "sla-analysis",
            "client-communication",
            "problem-management",
            "knowledge-gap-analysis",
            "service-operations-analysis",
        ],
        "connector_alternatives": [
            ["halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"],
            ["microsoft_intune", "jumpcloud", "jamf_pro"],
            ["huntress", "sentinelone", "crowdstrike", "connectsecure"],
            ["microsoft_365", "slack", "microsoft_teams"],
        ],
    }
