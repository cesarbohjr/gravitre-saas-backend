"""MSP Service Desk 3.0 Outcome Pack.

This module defines the Marketplace 3.0 flagship MSP service desk bundle.
It is intentionally not added to the public seed catalog until certification
proves install, execution, KPI reconciliation, and source-of-record verification.
"""
from __future__ import annotations

from typing import Any

from app.workflows.constants import SCHEMA_VERSION


PACK_SLUG = "msp-service-desk-3"
PACK_TITLE = "MSP Service Desk 3.0"


def _agent_step(step_id: str, name: str, task: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": {
            "agent_seed": "agent:msp-service-desk-coordinator",
            "task": task,
        },
    }


def _play(
    key: str,
    name: str,
    description: str,
    *,
    trigger: dict[str, Any],
    kpis: list[str],
    outcome_event: str,
    task: str,
    approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "description": description,
        "trigger": trigger,
        "workflow_steps": [
            _agent_step(f"{key}-analyze", f"{name}: analyze", task),
        ],
        "outcome_events": [outcome_event],
        "kpi_keys": kpis,
        "approvals": approvals or [],
        "verification": {
            "mode": "source_of_record",
            "required": True,
            "status": "implementation",
            "note": "Provider-specific PSA write/read verification is required before Production Verified certification.",
        },
    }


def build_msp_service_desk_3_config() -> dict[str, Any]:
    """Return the complete Marketplace 3.0 configuration for the flagship MSP pack."""
    kpis = [
        {"key": "mtta", "label": "Mean time to acknowledge", "unit": "minutes", "direction": "decrease", "source": "service_tickets"},
        {"key": "mttr", "label": "Mean time to resolve", "unit": "minutes", "direction": "decrease", "source": "service_tickets"},
        {"key": "sla_compliance", "label": "SLA compliance", "unit": "percent", "direction": "increase", "source": "service_tickets"},
        {"key": "automation_rate", "label": "Automation rate", "unit": "percent", "direction": "increase", "source": "play_runs"},
        {"key": "backlog", "label": "Open ticket backlog", "unit": "count", "direction": "decrease", "source": "service_tickets"},
        {"key": "reopen_rate", "label": "Ticket reopen rate", "unit": "percent", "direction": "decrease", "source": "service_tickets"},
        {"key": "first_contact_resolution", "label": "First-contact resolution", "unit": "percent", "direction": "increase", "source": "service_tickets"},
        {"key": "tickets_rescued", "label": "SLA-risk tickets rescued", "unit": "count", "direction": "increase", "source": "outcome_events"},
        {"key": "knowledge_gap_rate", "label": "Knowledge gap rate", "unit": "percent", "direction": "decrease", "source": "knowledge_signals"},
        {"key": "hours_saved", "label": "Estimated technician hours saved", "unit": "hours", "direction": "increase", "source": "outcome_events"},
    ]

    plays = [
        _play(
            "intelligent-ticket-intake",
            "Intelligent Ticket Intake",
            "Classify, prioritize, enrich, and route new service requests using client, user, asset, SLA, and sentiment context.",
            trigger={"type": "event", "event": "ticket.created"},
            kpis=["mtta", "sla_compliance", "automation_rate", "hours_saved"],
            outcome_event="ticket_triaged",
            task=(
                "Review a newly created service ticket. Determine category, urgency, likely owner, "
                "business impact, SLA risk, missing context, and the next safe action. Do not claim "
                "the ticket was modified unless a provider write is subsequently verified."
            ),
        ),
        _play(
            "resolution-copilot",
            "Resolution Copilot",
            "Assemble prior incidents, runbooks, device context, and known fixes into an evidence-backed remediation plan.",
            trigger={"type": "manual"},
            kpis=["mttr", "first_contact_resolution", "hours_saved"],
            outcome_event="resolution_plan_generated",
            task=(
                "Build a resolution plan from the ticket context, service runbooks, known-problem "
                "history, and available device/security evidence. Separate verified evidence from hypotheses."
            ),
            approvals=[{"type": "required_before_external_write", "scope": "remediation"}],
        ),
        _play(
            "sla-rescue",
            "SLA Rescue",
            "Detect tickets approaching breach, identify the blocking condition, and coordinate an intervention before the SLA is missed.",
            trigger={"type": "threshold", "signal": "sla_remaining_minutes", "operator": "<=", "value": 60},
            kpis=["sla_compliance", "tickets_rescued", "mttr"],
            outcome_event="ticket_sla_rescued",
            task=(
                "Review an SLA-risk ticket. Identify why it is stalled, the current owner, missing "
                "information or approvals, and the safest intervention. Require verification before "
                "recording the SLA as rescued."
            ),
        ),
        _play(
            "stale-ticket-recovery",
            "Stale Ticket Recovery",
            "Find tickets stalled on technicians, customers, vendors, approvals, or missing information and restart the correct next step.",
            trigger={"type": "scheduled", "cadence": "hourly"},
            kpis=["backlog", "mttr", "automation_rate", "hours_saved"],
            outcome_event="stale_ticket_recovered",
            task=(
                "Identify stale tickets and classify the blocking party or dependency. Recommend the "
                "next step, escalation, or communication required to restart progress."
            ),
        ),
        _play(
            "recurring-problem-hunter",
            "Recurring Problem Hunter",
            "Cluster repeated incidents across clients, users, and assets to surface root recurring problems and preventive opportunities.",
            trigger={"type": "scheduled", "cadence": "daily"},
            kpis=["reopen_rate", "backlog", "hours_saved"],
            outcome_event="recurring_problem_identified",
            task=(
                "Analyze repeated service issues and group them by symptom, asset, client, cause, and "
                "known resolution. Flag candidate root problems and preventive automation opportunities."
            ),
        ),
        _play(
            "client-communication-manager",
            "Client Communication Manager",
            "Prepare timely client updates grounded in verified service status, SLA posture, sentiment, and business impact.",
            trigger={"type": "event", "event": "ticket.status_changed"},
            kpis=["sla_compliance", "mtta", "hours_saved"],
            outcome_event="client_update_prepared",
            task=(
                "Prepare a concise customer-facing update using only verified ticket state and known "
                "next steps. Never invent ETA, resolution status, or completed work."
            ),
            approvals=[{"type": "required_before_external_write", "scope": "client_message"}],
        ),
        _play(
            "knowledge-gap-miner",
            "Knowledge Gap Miner",
            "Turn repeated questions, escalations, unresolved searches, and failed runs into prioritized KB and SOP improvements.",
            trigger={"type": "scheduled", "cadence": "weekly"},
            kpis=["knowledge_gap_rate", "first_contact_resolution", "hours_saved"],
            outcome_event="knowledge_gap_identified",
            task=(
                "Review failed retrievals, repeated tickets, escalations, and unresolved service work. "
                "Propose missing knowledge, runbook, or decision-rule content with supporting evidence."
            ),
        ),
        _play(
            "service-desk-optimization-review",
            "Service Desk Optimization Review",
            "Review service desk performance, bottlenecks, technician workload, recurring issues, and automation coverage to recommend measurable improvements.",
            trigger={"type": "scheduled", "cadence": "weekly"},
            kpis=["mtta", "mttr", "sla_compliance", "automation_rate", "backlog", "reopen_rate", "hours_saved"],
            outcome_event="service_desk_optimization_reviewed",
            task=(
                "Produce a weekly operating review from service KPIs and Play outcomes. Identify the "
                "largest bottlenecks, recurring causes, automation opportunities, and the top three "
                "changes most likely to improve service performance."
            ),
        ),
    ]

    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": (
                "MSP service desks lose technician capacity to manual triage, stalled tickets, repeated "
                "issues, inconsistent communication, and reactive SLA management."
            ),
            "target_outcome": (
                "Reduce response and resolution time, improve SLA compliance, increase first-contact "
                "resolution, and convert repetitive service work into governed automation."
            ),
            "baseline_metric": "mttr",
            "success_criteria": [
                "All eight Plays install onto Gravitre's canonical Play/workflow runtime.",
                "Every Play emits declared outcome events and reconciles to dashboard KPIs.",
                "Consequential provider writes remain approval-gated and source-of-record verified.",
                "At least one supported PSA path passes golden-path and failure-path certification.",
            ],
            "outcome_events": [
                "ticket_triaged",
                "resolution_plan_generated",
                "ticket_sla_rescued",
                "stale_ticket_recovered",
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
                "seed_label": "agent:msp-service-desk-coordinator",
                "name": "MSP Service Desk Coordinator",
                "purpose": "Coordinate service-desk Plays, surface risks, and keep execution grounded in verified service data.",
                "role": "Service Operations",
                "department": "Operations",
                "persona_key": "DEVOPS",
                "systems": [
                    "zendesk",
                    "halo_psa",
                    "autotask",
                    "syncro",
                    "servicenow",
                    "freshservice",
                    "microsoft_intune",
                    "huntress",
                    "sentinelone",
                ],
                "capabilities": [
                    "ticket-triage",
                    "sla-risk",
                    "incident-analysis",
                    "knowledge-gap-analysis",
                    "service-optimization",
                ],
                "guardrails": [
                    "Never represent provider acceptance as completion.",
                    "Require approval before consequential external writes.",
                    "Verify consequential writes against the source of record.",
                ],
                "config": {"marketplaceSlug": PACK_SLUG},
            },
            {
                "seed_label": "agent:msp-service-desk-analyst",
                "name": "MSP Service Desk Analyst",
                "purpose": "Analyze recurring incidents, service trends, knowledge gaps, and operational performance.",
                "role": "Service Intelligence",
                "department": "Operations",
                "persona_key": "DEVOPS",
                "systems": ["zendesk", "halo_psa", "autotask", "syncro", "servicenow", "freshservice"],
                "capabilities": ["trend-analysis", "problem-management", "kpi-analysis"],
                "guardrails": ["Distinguish measured facts from inferred causes."],
                "config": {"marketplaceSlug": PACK_SLUG},
            },
        ],
        "plays": plays,
        "knowledge": [
            {
                "seed_label": "rag:msp-sla-matrix",
                "title": "MSP SLA Matrix",
                "type": "manual",
                "metadata": {"description": "Upload client SLA definitions, escalation rules, and service commitments."},
            },
            {
                "seed_label": "rag:msp-service-runbooks",
                "title": "MSP Service Runbooks",
                "type": "manual",
                "metadata": {"description": "Upload troubleshooting runbooks, standard remediation steps, and escalation procedures."},
            },
            {
                "seed_label": "rag:msp-client-communication",
                "title": "MSP Client Communication Standards",
                "type": "manual",
                "metadata": {"description": "Upload approved client communication tone, update cadence, and escalation language."},
            },
        ],
        "dataset": {
            "entities": [
                {
                    "name": "service_tickets",
                    "source": "psa",
                    "primary_key": "ticket_id",
                    "fields": [
                        "ticket_id", "client_id", "requester_id", "asset_id", "status", "priority",
                        "category", "assigned_to", "created_at", "acknowledged_at", "resolved_at",
                        "sla_due_at", "reopened_count", "sentiment",
                    ],
                },
                {
                    "name": "service_clients",
                    "source": "psa",
                    "primary_key": "client_id",
                    "fields": ["client_id", "name", "sla_policy", "service_tier", "account_health"],
                },
                {
                    "name": "service_assets",
                    "source": "rmm_or_mdm",
                    "primary_key": "asset_id",
                    "fields": ["asset_id", "client_id", "device_type", "os", "compliance_state", "security_state"],
                },
                {
                    "name": "service_outcomes",
                    "source": "gravitre_outcome_events",
                    "primary_key": "event_id",
                    "fields": ["event_id", "play_key", "ticket_id", "outcome_type", "verified", "occurred_at"],
                },
            ],
            "metrics": [
                {"key": "mtta", "label": "MTTA", "formula": "avg(acknowledged_at - created_at)", "unit": "minutes"},
                {"key": "mttr", "label": "MTTR", "formula": "avg(resolved_at - created_at)", "unit": "minutes"},
                {"key": "sla_compliance", "label": "SLA compliance", "formula": "resolved_within_sla / resolved_tickets", "unit": "percent"},
                {"key": "automation_rate", "label": "Automation rate", "formula": "automated_completed / completed_play_runs", "unit": "percent"},
                {"key": "backlog", "label": "Open ticket backlog", "formula": "count(open_tickets)", "unit": "count"},
                {"key": "reopen_rate", "label": "Reopen rate", "formula": "reopened_tickets / resolved_tickets", "unit": "percent"},
                {"key": "first_contact_resolution", "label": "First-contact resolution", "formula": "first_contact_resolved / resolved_tickets", "unit": "percent"},
                {"key": "tickets_rescued", "label": "Tickets rescued", "formula": "count(ticket_sla_rescued)", "unit": "count"},
                {"key": "knowledge_gap_rate", "label": "Knowledge gap rate", "formula": "knowledge_gap_events / service_requests", "unit": "percent"},
                {"key": "hours_saved", "label": "Hours saved", "formula": "sum(estimated_minutes_saved) / 60", "unit": "hours"},
            ],
        },
        "dashboard": {
            "title": "MSP Service Desk Outcomes",
            "refresh_mode": "event",
            "metrics": [
                {"kpi_key": "mtta", "label": "MTTA", "visualization": "trend", "description": "Average time from ticket creation to acknowledgment."},
                {"kpi_key": "mttr", "label": "MTTR", "visualization": "trend", "description": "Average time from ticket creation to verified resolution."},
                {"kpi_key": "sla_compliance", "label": "SLA compliance", "visualization": "progress", "description": "Share of resolved tickets meeting the configured SLA."},
                {"kpi_key": "automation_rate", "label": "Automation rate", "visualization": "trend", "description": "Share of completed service Play work automated by Gravitre."},
                {"kpi_key": "backlog", "label": "Backlog", "visualization": "metric", "description": "Current open ticket count."},
                {"kpi_key": "reopen_rate", "label": "Reopen rate", "visualization": "trend", "description": "Share of resolved tickets reopened."},
                {"kpi_key": "first_contact_resolution", "label": "First-contact resolution", "visualization": "trend", "description": "Share of tickets resolved on first meaningful service contact."},
                {"kpi_key": "tickets_rescued", "label": "SLA-risk tickets rescued", "visualization": "metric", "description": "Verified SLA-risk tickets recovered before breach."},
                {"kpi_key": "knowledge_gap_rate", "label": "Knowledge gap rate", "visualization": "trend", "description": "Rate of service work exposing missing or insufficient knowledge."},
                {"kpi_key": "hours_saved", "label": "Technician hours saved", "visualization": "trend", "description": "Estimated technician time saved by verified Play outcomes."},
            ],
        },
        "skills": [
            "ticket-triage",
            "incident-analysis",
            "sla-risk-analysis",
            "problem-management",
            "knowledge-gap-analysis",
            "service-kpi-analysis",
        ],
        "skill_requirements": [],
        "skill_bindings": {},
        "runtime_profiles": [],
        "connector_alternatives": [
            ["zendesk", "halo_psa", "autotask", "syncro", "servicenow", "freshservice"],
            ["microsoft_intune", "jumpcloud", "jamf_pro"],
            ["huntress", "sentinelone", "crowdstrike", "connectsecure"],
        ],
    }


def build_msp_service_desk_3_asset() -> dict[str, Any]:
    """Return seed-style Marketplace metadata without publishing it to the catalog."""
    return {
        "slug": PACK_SLUG,
        "title": PACK_TITLE,
        "description": (
            "Eight governed service-desk Plays that reduce manual triage, protect SLA, surface "
            "recurring problems, improve knowledge, and measure verified service outcomes."
        ),
        "asset_type": "outcome_pack",
        "category": "outcome_pack",
        "department": "Operations",
        "tags": ["msp", "service-desk", "outcome-pack", "marketplace-3", "uncertified"],
        "business_outcome": "Reduce MTTA/MTTR and SLA breaches while increasing service automation and technician capacity.",
        "use_case": "MSP service desk operations",
        "estimated_hours_saved": 20.0,
        "pricing_type": "paid",
        "price_cents": 19900,
        "pack_tier": 3,
        "required_connectors": [],
        "install_variables": [
            {
                "key": "PRIMARY_PSA",
                "label": "Primary PSA / service desk",
                "required": True,
                "description": "Select the connected PSA/service desk that will become the source of record after provider certification.",
            }
        ],
        "pack_children": [],
        "config": build_msp_service_desk_3_config(),
        "certification_status": "implementation",
    }
