"""Marketplace 3.0 flagship: MSP Service Desk.

The public v1 bundle is certified against the Freshservice runtime profile.
Additional MSP providers must earn the same action, governance, and verification
coverage before they are represented as runtime-equivalent.
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


def _tool_step(
    step_id: str,
    name: str,
    action: str,
    *,
    param_sources: dict[str, Any] | None = None,
    connector: str = "freshservice",
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "action": action,
        "tool_action": action,
        "vendor": connector,
        "connector": connector,
        "selectedAction": action.split(".", 1)[-1],
        "selected_action": action.split(".", 1)[-1],
    }
    if param_sources:
        config["param_sources"] = param_sources
    return {
        "id": step_id,
        "name": name,
        "type": "invoke_tool",
        "config": config,
        "requires_connector": connector,
    }


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
    evidence_steps: list[dict[str, Any]] | None = None,
    action_steps_after: list[dict[str, Any]] | None = None,
    capability_groups: list[list[str]] | None = None,
    optional_connectors: list[str] | None = None,
    write_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    workflow_steps = list(evidence_steps or [])
    workflow_steps.append(
        _agent_step(
            f"{key}-analyze",
            f"{name} analysis",
            agent_seed,
            task,
        )
    )
    workflow_steps.extend(action_steps_after or [])
    runtime_inputs = sorted(
        {
            str(value)[1:]
            for step in workflow_steps
            if isinstance(step, dict)
            for value in (
                ((step.get("config") or {}).get("param_sources") or {}).values()
                if isinstance(step.get("config"), dict)
                and isinstance((step.get("config") or {}).get("param_sources"), dict)
                else []
            )
            if isinstance(value, str) and value.startswith("$") and len(value) > 1
        }
    )
    return {
        "key": key,
        "name": name,
        "description": description,
        "trigger": trigger,
        "workflow_steps": workflow_steps,
        "outcome_events": [outcome_event],
        "kpi_keys": kpis,
        "approvals": approvals or [],
        "verification": {
            "mode": "source_of_record",
            "provider_acceptance_is_terminal": False,
        },
        "runtime_inputs": runtime_inputs,
        "objective": description,
        "capability_groups": capability_groups or [["support.ticket.read", "support.ticket.list"]],
        "required_connector_groups": [list(_SERVICE_DESKS)],
        "optional_connectors": optional_connectors or [],
        "write_actions": write_actions or [],
    }


# Service desks a Play can observe; verification is certified for Freshservice.
_SERVICE_DESKS = ("halo_psa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk")

_RESOLVED_AT = "current.ticket.stats.resolved_at"
_DUE_BY = "current.ticket.due_by"
_CREATED_AT = "current.ticket.created_at"

# Metrics a service desk can verify per ticket from the source of record.
_VERIFIED_KPI_SEMANTICS: dict[str, dict[str, Any]] = {
    "mtta": {
        "kind": "business", "aggregation": "avg", "source_system": "freshservice", "source_record_type": "ticket",
        "verification_recipe": "freshservice-ticket-resolution",
        "evidence_strategy": "Minutes from ticket creation to first response, read from the ticket's stats.",
        "synonyms": ["response time", "time to acknowledge", "mtta", "first response time"],
    },
    "mttr": {
        "kind": "business", "aggregation": "avg", "source_system": "freshservice", "source_record_type": "ticket",
        "verification_recipe": "freshservice-ticket-resolution",
        "evidence_strategy": "Minutes from ticket creation to resolution, read from the ticket's stats.",
        "synonyms": ["resolution time", "time to resolve", "mttr", "ticket resolution time"],
    },
    "sla_compliance": {
        "kind": "business", "aggregation": "ratio", "numerator": "tickets_resolved_within_sla",
        "denominator": "tickets_resolved",
        "evidence_strategy": "Share of verified resolved tickets whose resolution time met the due date.",
        "synonyms": ["sla compliance", "sla", "sla attainment", "meet sla", "sla breaches"],
    },
    "tickets_rescued": {
        "kind": "business", "aggregation": "count", "source_system": "freshservice", "source_record_type": "ticket",
        "verification_recipe": "freshservice-ticket-resolution",
        "evidence_strategy": "A rescued ticket was resolved at or before its SLA due time.",
        "synonyms": ["tickets rescued", "sla saves", "breaches prevented"],
    },
}
_OPERATIONAL_NOTE = "Operational estimate; not verified per ticket by a source-of-record recipe yet."


def _msp_kpi(row: dict[str, Any]) -> dict[str, Any]:
    out = {**row, "department": "msp", "departments": ["msp", "support"]}
    semantics = _VERIFIED_KPI_SEMANTICS.get(row["key"])
    if semantics:
        out.update(semantics)
    else:
        out.update({"kind": "operational", "aggregation": "avg" if row["unit"] != "count" else "count",
                    "evidence_strategy": _OPERATIONAL_NOTE})
    out.setdefault("description", row["label"])
    return out


_MSP_RECIPES: list[dict[str, Any]] = [
    {
        "key": "freshservice-ticket-resolution",
        "source_system": "freshservice",
        "record_type": "ticket",
        "match_actions": ["freshservice.tickets.update_status"],
        "read_action": "freshservice.tickets.get",
        "record_id_param": "ticket_id",
        "record_id_fields": ["record_ids.ticket", "ticket_id", "entity_id", "id"],
        "read_params": {"include": "stats"},
        "verification_method": "service_desk_ticket_reread",
        "measure_after_hours": 1,
        "measure_window_days": 14,
        "contributions": [
            {"metric_key": "tickets_resolved", "when": {"field": _RESOLVED_AT, "op": "exists"}},
            {
                "metric_key": "tickets_resolved_within_sla",
                "when": {"all": [{"field": _RESOLVED_AT, "op": "exists"}, {"field": _RESOLVED_AT, "op": "lte", "value_field": _DUE_BY}]},
                "fail_when": {"field": _RESOLVED_AT, "op": "gt", "value_field": _DUE_BY},
            },
            {
                "metric_key": "tickets_rescued",
                "when": {"all": [{"field": _RESOLVED_AT, "op": "exists"}, {"field": _RESOLVED_AT, "op": "lte", "value_field": _DUE_BY}]},
                "fail_when": {"field": _RESOLVED_AT, "op": "gt", "value_field": _DUE_BY},
            },
            {
                "metric_key": "mttr",
                "when": {"field": _RESOLVED_AT, "op": "exists"},
                "value": {"duration_from": _CREATED_AT, "duration_to": _RESOLVED_AT, "duration_unit": "minutes"},
            },
            {
                "metric_key": "mtta",
                "when": {"field": "current.ticket.stats.first_responded_at", "op": "exists"},
                "value": {"duration_from": _CREATED_AT, "duration_to": "current.ticket.stats.first_responded_at", "duration_unit": "minutes"},
            },
        ],
    }
]


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

    kpis.extend(
        [
            {"key": "tickets_resolved", "label": "Tickets resolved", "unit": "count", "direction": "increase",
             "source": "service_tickets", "description": "Tickets a Play acted on that the service desk shows as resolved."},
            {"key": "tickets_resolved_within_sla", "label": "Tickets resolved within SLA", "unit": "count",
             "direction": "increase", "source": "service_tickets",
             "description": "Tickets a Play acted on that were resolved at or before their due time."},
        ]
    )
    for row in kpis:
        if row["key"] in {"tickets_resolved", "tickets_resolved_within_sla"}:
            row.update({"kind": "funnel", "aggregation": "count", "source_system": "freshservice",
                        "source_record_type": "ticket", "verification_recipe": "freshservice-ticket-resolution"})
    kpis = [_msp_kpi(row) for row in kpis]

    plays = [
        _play(
            "intelligent-ticket-intake",
            "Intelligent Ticket Intake",
            "Classify, prioritize, enrich, and route new service tickets using client, user, asset, SLA, and sentiment context.",
            kpis=["mtta", "sla_compliance", "automation_rate"],
            outcome_event="ticket_intake_completed",
            trigger={"type": "event", "event": "ticket.created"},
            agent_seed="agent:msp-service-coordinator",
            evidence_steps=[
                _tool_step(
                    "ticket-context",
                    "Fetch Freshservice ticket context",
                    "freshservice.tickets.get",
                    param_sources={"ticket_id": "$TICKET_ID"},
                ),
                _tool_step(
                    "ticket-activities",
                    "Fetch recent ticket activity",
                    "freshservice.tickets.activities",
                    param_sources={"ticket_id": "$TICKET_ID"},
                ),
            ],
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
            evidence_steps=[
                _tool_step(
                    "resolution-ticket-context",
                    "Fetch Freshservice ticket context",
                    "freshservice.tickets.get",
                    param_sources={"ticket_id": "$TICKET_ID", "include": "stats,assets"},
                ),
                _tool_step(
                    "resolution-ticket-activities",
                    "Fetch ticket activity history",
                    "freshservice.tickets.activities",
                    param_sources={"ticket_id": "$TICKET_ID"},
                ),
            ],
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
            evidence_steps=[
                _tool_step(
                    "sla-ticket-context",
                    "Fetch SLA ticket context",
                    "freshservice.tickets.get",
                    param_sources={"ticket_id": "$TICKET_ID", "include": "stats"},
                ),
                _tool_step(
                    "sla-ticket-activities",
                    "Fetch SLA ticket activity",
                    "freshservice.tickets.activities",
                    param_sources={"ticket_id": "$TICKET_ID"},
                ),
            ],
            task=(
                "Investigate why the ticket is stalled, identify the correct owner/escalation, and "
                "prepare a rescue action. Any consequential write requires approval and source-of-record verification."
            ),
            approvals=[
                {
                    "when": "freshservice.tickets.update_status",
                    "required": True,
                    "verification": "source_of_record_field_assert",
                }
            ],
            capability_groups=[["support.ticket.read"], ["support.ticket.update"]],
            write_actions=[{"capability": "support.ticket.update", "approval": "always"}],
            action_steps_after=[
                _tool_step(
                    "sla-approved-status-update",
                    "Apply approved Freshservice ticket status",
                    "freshservice.tickets.update_status",
                    param_sources={
                        "ticket_id": "$TICKET_ID",
                        "status": "$TARGET_STATUS",
                    },
                )
            ],
        ),
        _play(
            "stale-ticket-recovery",
            "Stale Ticket Recovery",
            "Find tickets stalled on technicians, customers, vendors, approvals, or missing information and restart the correct next step.",
            kpis=["backlog", "stale_ticket_rate", "mttr"],
            outcome_event="stale_ticket_reactivated",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:msp-service-coordinator",
            evidence_steps=[
                _tool_step(
                    "stale-ticket-list",
                    "List recently updated Freshservice tickets",
                    "freshservice.tickets.list",
                    param_sources={"per_page": 100},
                ),
            ],
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
            evidence_steps=[
                _tool_step(
                    "recurring-ticket-list",
                    "Load Freshservice incident sample",
                    "freshservice.tickets.list",
                    param_sources={"type": "Incident", "per_page": 100},
                ),
            ],
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
            evidence_steps=[
                _tool_step(
                    "client-update-context",
                    "Fetch verified Freshservice ticket status",
                    "freshservice.tickets.get",
                    param_sources={"ticket_id": "$TICKET_ID", "include": "stats"},
                ),
            ],
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
            evidence_steps=[
                _tool_step(
                    "knowledge-gap-ticket-list",
                    "Load service ticket sample",
                    "freshservice.tickets.list",
                    param_sources={"per_page": 100},
                ),
            ],
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
            evidence_steps=[
                _tool_step(
                    "optimization-ticket-list",
                    "Load service desk operating sample",
                    "freshservice.tickets.list",
                    param_sources={"per_page": 100},
                ),
            ],
            task=(
                "Review KPI trends and Play outcomes. Identify the highest-value operational bottlenecks, "
                "automation candidates, and workflow changes, tied to measurable baseline evidence."
            ),
        ),
    ]

    return {
        "marketplace_version": "3.0",
        "pack_id": "msp-service-desk",
        "department": "msp",
        "objectives": [
            {"key": "improve-sla", "statement": "Improve SLA compliance", "kpi_keys": ["sla_compliance", "tickets_rescued"]},
            {"key": "resolve-faster", "statement": "Resolve tickets faster", "kpi_keys": ["mttr", "mtta"]},
        ],
        "verification_recipes": _MSP_RECIPES,
        "governance": {
            "always_approve_actions": ["freshservice.tickets.update_status"],
            "max_autonomy": "act_with_approval",
        },
        "certification": {
            "minimum_plays": 6,
            "fixtures": {
                "freshservice-ticket-resolution": {
                    "record_id": "4521",
                    "current": {
                        "ticket": {
                            "id": 4521,
                            "created_at": "2026-10-01T10:00:00Z",
                            "due_by": "2026-10-01T18:00:00Z",
                            "stats": {"first_responded_at": "2026-10-01T10:20:00Z", "resolved_at": "2026-10-01T16:30:00Z"},
                        }
                    },
                }
            },
            "degraded_scenarios": [
                {"capability": "support.ticket.read", "unavailable_vendor": "freshservice", "reason": "auth_expired"},
            ],
        },
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
            "template_id": "msp-service-desk",
            "department": "msp",
            "sections": [
                {"title": "SLA", "kpi_keys": ["sla_compliance", "tickets_rescued", "tickets_resolved_within_sla", "tickets_resolved"]},
                {"title": "Speed", "kpi_keys": ["mtta", "mttr"]},
                {"title": "Operational estimates", "kpi_keys": [
                    "first_contact_resolution", "backlog", "reopen_rate", "automation_rate", "repeat_issue_rate",
                    "knowledge_gap_rate", "customer_update_latency", "csat", "stale_ticket_rate", "prevented_incidents",
                ]},
            ],
            "system_health_kpis": ["connector-health", "pending-approvals"],
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
        # First-party guidance skills are distributed as one reviewed, Git-pinned
        # capability package. Execution authority remains in Gravitre's runtime.
        "skills": ["msp-service-desk-skills-v1"],
        "skill_requirements": [
            "ticket-triage",
            "incident-diagnosis",
            "sla-analysis",
            "client-communication",
            "problem-management",
            "knowledge-gap-analysis",
            "service-operations-analysis",
        ],
        "skill_bindings": {
            "ticket-triage": "msp-service-desk-skills-v1",
            "incident-diagnosis": "msp-service-desk-skills-v1",
            "sla-analysis": "msp-service-desk-skills-v1",
            "client-communication": "msp-service-desk-skills-v1",
            "problem-management": "msp-service-desk-skills-v1",
            "knowledge-gap-analysis": "msp-service-desk-skills-v1",
            "service-operations-analysis": "msp-service-desk-skills-v1",
        },
        "runtime_profiles": [
            {
                "provider": "freshservice",
                "status": "production_verified",
                "actions": [
                    "freshservice.tickets.list",
                    "freshservice.tickets.get",
                    "freshservice.tickets.activities",
                    "freshservice.tickets.update_status",
                ],
            }
        ],
        "connector_alternatives": [
            ["freshservice"],
            ["microsoft_intune", "jumpcloud", "jamf_pro"],
            ["huntress", "sentinelone", "crowdstrike", "connectsecure"],
            ["microsoft_365", "slack", "microsoft_teams"],
        ],
    }


_MSP_SKILL_MD = """---
name: MSP Service Desk Skills
description: First-party Gravitre service-desk reasoning skills for Marketplace 3.0.
license: MIT
---

# MSP Service Desk Skills

This reviewed first-party capability bundle provides guidance-only skills for:
- ticket triage
- incident diagnosis
- SLA analysis
- client communication
- problem management
- knowledge-gap analysis
- service-operations analysis

These skills never own execution authority. Connector reads/writes, approvals, source-of-record verification, Runs, and outcome truth remain owned by Gravitre's canonical runtime.
"""

_MSP_SKILL_MANIFEST = {
    "schema": "gravitre.capability.v1",
    "format": "gravitre",
    "name": "MSP Service Desk Skills",
    "version": "1.0.0",
    "description": "First-party guidance skills for the Gravitre Marketplace 3.0 MSP Service Desk pack.",
    "license": "MIT",
    "skills": [
        {"name": "ticket-triage"},
        {"name": "incident-diagnosis"},
        {"name": "sla-analysis"},
        {"name": "client-communication"},
        {"name": "problem-management"},
        {"name": "knowledge-gap-analysis"},
        {"name": "service-operations-analysis"},
    ],
    "permissions": [],
}


def build_msp_service_desk_skill_package_config() -> dict[str, Any]:
    return {
        "provenance_mode": "git_pinned",
        "repository_url": "https://github.com/cesarbohjr/gravitre-saas-backend",
        "commit_sha": "e35e61a5b6fd499895cf526930187383aed36027",
        "package_path": "capability_packages/msp-service-desk-skills",
        "content_digest": "sha256:b11dae59a9cfaaf651c94354d3a95ce8b6138b53557b2cd5c32c6ad7a253cdb3",
        "snapshot_digest": "sha256:6a20e422fb2abcf45a72282e62d6b146694e23f6fb04b9b70591906a9bdc3fe7",
        "manifest": _MSP_SKILL_MANIFEST,
        "resources": [
            {
                "path": "SKILL.md",
                "kind": "reference",
                "content": _MSP_SKILL_MD,
                "executable": False,
            }
        ],
        "package_format": "gravitre",
        "license": "MIT",
        "license_policy": "allow",
        "risk_level": "low",
        "signature_status": "unsigned",
        "publisher_name": "Gravitre",
        "publisher_trust_scope": "none",
        "security_scan": {
            "risk": "low",
            "blocked": False,
            "findings": [],
            "executionPerformed": False,
        },
    }


def msp_service_desk_marketplace3_assets() -> list[Any]:
    # Lazy import avoids a seed_catalog import cycle.
    from app.marketplace.seed_catalog import CatalogAsset

    outcome_config = build_msp_service_desk_outcome_pack_config()
    freshservice = {
        "connectorType": "freshservice",
        "label": "Freshservice",
        "required": True,
        "connectPath": "/connectors?type=freshservice",
        "requirementNote": (
            "Production Verified Marketplace 3.0 runtime for v1. "
            "Writes require approval and source-of-record verification."
        ),
    }

    agents = [
        CatalogAsset(
            slug=f"msp3-{str(agent['seed_label']).split(':')[-1]}",
            title=str(agent["name"]),
            description=str(agent["purpose"]),
            asset_type="ai_agent",
            category="ai_agent",
            department="MSP Service Desk",
            tags=["msp", "service-desk", "agent", "marketplace-3"],
            config=agent,
            required_connectors=[freshservice],
        )
        for agent in outcome_config["agents"]
    ]

    plays = [
        CatalogAsset(
            slug=f"msp3-play-{play['key']}",
            title=str(play["name"]),
            description=str(play["description"]),
            asset_type="play",
            category="play",
            department="MSP Service Desk",
            tags=["msp", "service-desk", "play", "marketplace-3"],
            config=play,
            required_connectors=[freshservice],
            business_outcome=str(play["outcome_events"][0]),
            use_case=str(play["description"]),
        )
        for play in outcome_config["plays"]
    ]

    skill_package = CatalogAsset(
        slug="msp-service-desk-skills-v1",
        title="MSP Service Desk Skills",
        description="Seven reviewed first-party guidance skills for the Marketplace 3.0 service-desk pack.",
        asset_type="capability_package",
        category="capability_package",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "skills", "marketplace-3", "gravitre"],
        config=build_msp_service_desk_skill_package_config(),
    )

    knowledge = CatalogAsset(
        slug="msp-service-desk-3-knowledge",
        title="MSP Service Desk 3.0 Knowledge",
        description="Runbooks, SLA policy, client communication standards, and known-issue context.",
        asset_type="knowledge_pack",
        category="knowledge_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "knowledge", "marketplace-3"],
        config={"documents": outcome_config["knowledge"]},
    )

    dataset = CatalogAsset(
        slug="msp-service-desk-3-dataset",
        title="MSP Service Desk 3.0 Dataset",
        description="Normalized service-ticket, verified-outcome, and KPI definitions for measurable service operations.",
        asset_type="dataset_pack",
        category="dataset_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "dataset", "marketplace-3"],
        config=outcome_config["dataset"],
        required_connectors=[freshservice],
    )

    dashboard = CatalogAsset(
        slug="msp-service-desk-3-dashboard",
        title="MSP Service Desk Command Center",
        description="KPI dashboard for service speed, SLA, backlog, quality, automation, and recurring operational risk.",
        asset_type="dashboard_pack",
        category="dashboard_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "dashboard", "kpi", "marketplace-3"],
        config=outcome_config["dashboard"],
    )

    child_slugs = (
        [agent.slug for agent in agents]
        + [play.slug for play in plays]
        + [skill_package.slug, knowledge.slug, dataset.slug, dashboard.slug]
    )
    outcome = CatalogAsset(
        slug="msp-service-desk-3",
        title="MSP Service Desk 3.0",
        description=(
            "Operate a measurable MSP service desk with eight outcome-driven Plays, "
            "three specialized agents, reviewed skills, governed Freshservice execution, "
            "service knowledge, normalized KPIs, and an installed command dashboard."
        ),
        asset_type="outcome_pack",
        category="outcome_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "outcome-pack", "marketplace-3", "production-verified"],
        pricing_type="paid",
        price_cents=19900,
        pack_tier=3,
        config=outcome_config,
        required_connectors=[freshservice],
        pack_children=child_slugs,
        business_outcome=(
            "Reduce service response and resolution time while improving SLA compliance "
            "and verified automation."
        ),
        use_case="MSP service desk operations",
        estimated_hours_saved=40.0,
    )
    return agents + plays + [skill_package, knowledge, dataset, dashboard, outcome]
