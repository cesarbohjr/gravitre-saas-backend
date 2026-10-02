"""Marketplace 3.0 flagship: Security Operations.

The v1 executable profile is deliberately conservative: Freshservice provides the
registered source-of-record reads used by every Play. Endpoint, identity, and
vulnerability products remain enrichment/roadmap systems until their governed
Gravitre action contracts exist. No containment write is advertised as executable.
"""
from __future__ import annotations

from typing import Any


SECURITY_OPERATIONS_PLAY_KEYS = (
    "security-alert-triage",
    "incident-context-builder",
    "identity-risk-review",
    "vulnerability-prioritizer",
    "containment-coordinator",
    "remediation-verification-review",
    "security-incident-brief",
    "post-incident-review",
)


def _tool_step(
    step_id: str,
    name: str,
    action: str,
    *,
    param_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "action": action,
        "tool_action": action,
        "vendor": "freshservice",
        "connector": "freshservice",
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
        "requires_connector": "freshservice",
    }


def _agent_step(step_id: str, name: str, agent_seed: str, task: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": {"agent_seed": agent_seed, "task": task},
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
    evidence_steps: list[dict[str, Any]],
    approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    steps = list(evidence_steps)
    steps.append(_agent_step(f"{key}-analyze", f"{name} analysis", agent_seed, task))
    runtime_inputs = sorted(
        {
            str(value)[1:]
            for step in steps
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
        "workflow_steps": steps,
        "outcome_events": [outcome_event],
        "kpi_keys": kpis,
        "approvals": approvals or [],
        "verification": {
            "mode": "source_of_record",
            "provider_acceptance_is_terminal": False,
        },
        "runtime_inputs": runtime_inputs,
    }


def build_security_operations_outcome_pack_config() -> dict[str, Any]:
    kpis = [
        {"key": "security_queue_age", "label": "Security queue age", "unit": "minutes", "direction": "decrease", "source": "security_service_records"},
        {"key": "incident_context_time", "label": "Incident context assembly time", "unit": "minutes", "direction": "decrease", "source": "play_outcomes"},
        {"key": "critical_workload", "label": "Critical security workload", "unit": "count", "direction": "decrease", "source": "security_service_records"},
        {"key": "vulnerability_priority_age", "label": "Critical vulnerability priority age", "unit": "hours", "direction": "decrease", "source": "security_service_records"},
        {"key": "containment_readiness_time", "label": "Containment readiness time", "unit": "minutes", "direction": "decrease", "source": "play_outcomes"},
        {"key": "remediation_sla", "label": "Remediation SLA compliance", "unit": "percent", "direction": "increase", "source": "security_service_records"},
        {"key": "verification_gap_rate", "label": "Remediation verification gap rate", "unit": "percent", "direction": "decrease", "source": "play_outcomes"},
        {"key": "communication_latency", "label": "Incident communication latency", "unit": "minutes", "direction": "decrease", "source": "security_service_records"},
        {"key": "post_incident_completion", "label": "Post-incident review completion", "unit": "percent", "direction": "increase", "source": "play_outcomes"},
        {"key": "security_automation_rate", "label": "Security operations automation rate", "unit": "percent", "direction": "increase", "source": "play_runs"},
        {"key": "hours_saved", "label": "Security analyst hours saved", "unit": "hours", "direction": "increase", "source": "play_outcomes"},
    ]

    plays = [
        _play(
            "security-alert-triage",
            "Security Alert Triage",
            "Prioritize security-related records by severity, business exposure, recurrence, and evidence quality.",
            kpis=["security_queue_age", "critical_workload", "security_automation_rate"],
            outcome_event="security_alert_triaged",
            trigger={"type": "event", "event": "security.ticket_created"},
            agent_seed="agent:security-operations-coordinator",
            evidence_steps=[
                _tool_step("alert-ticket", "Fetch security ticket", "freshservice.tickets.get", param_sources={"ticket_id": "$TICKET_ID"}),
                _tool_step("alert-activity", "Fetch security ticket activity", "freshservice.tickets.activities", param_sources={"ticket_id": "$TICKET_ID"}),
            ],
            task="Classify urgency and evidence confidence. Separate confirmed facts from hypotheses and identify the next safe investigation step.",
        ),
        _play(
            "incident-context-builder",
            "Incident Context Builder",
            "Assemble a verified incident timeline, owners, affected services, prior activity, and missing evidence before response decisions.",
            kpis=["incident_context_time", "security_queue_age"],
            outcome_event="incident_context_built",
            trigger={"type": "event", "event": "security.incident_opened"},
            agent_seed="agent:security-incident-investigator",
            evidence_steps=[
                _tool_step("incident-ticket", "Fetch incident record", "freshservice.tickets.get", param_sources={"ticket_id": "$TICKET_ID", "include": "stats"}),
                _tool_step("incident-activity", "Fetch incident activity", "freshservice.tickets.activities", param_sources={"ticket_id": "$TICKET_ID"}),
            ],
            task="Build a chronological evidence record, label unknowns, and identify the minimum additional evidence required.",
        ),
        _play(
            "identity-risk-review",
            "Identity Risk Review",
            "Surface identity-related incidents that warrant deeper review without inventing identity-provider evidence that is not connected.",
            kpis=["critical_workload", "security_queue_age"],
            outcome_event="identity_risk_reviewed",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:security-identity-analyst",
            evidence_steps=[
                _tool_step("identity-ticket-list", "List security service records", "freshservice.tickets.list", param_sources={"per_page": 100}),
            ],
            task="Identify identity-related cases from available source records, rank review priority, and explicitly state when provider identity evidence is unavailable.",
        ),
        _play(
            "vulnerability-prioritizer",
            "Vulnerability Prioritizer",
            "Prioritize vulnerability and remediation work using severity, affected service, exposure evidence, age, and business impact.",
            kpis=["vulnerability_priority_age", "remediation_sla", "critical_workload"],
            outcome_event="vulnerability_work_prioritized",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:security-risk-analyst",
            evidence_steps=[
                _tool_step("vulnerability-ticket-list", "List vulnerability work", "freshservice.tickets.list", param_sources={"per_page": 100}),
            ],
            task="Rank remediation work using only available evidence. Never assert exploitability or exposure unless the source record supports it.",
        ),
        _play(
            "containment-coordinator",
            "Containment Coordinator",
            "Prepare the smallest evidence-backed containment plan, required approvals, rollback considerations, and verification steps.",
            kpis=["containment_readiness_time", "critical_workload"],
            outcome_event="containment_plan_prepared",
            trigger={"type": "event", "event": "security.containment_recommended"},
            agent_seed="agent:security-response-coordinator",
            evidence_steps=[
                _tool_step("containment-ticket", "Fetch incident record", "freshservice.tickets.get", param_sources={"ticket_id": "$TICKET_ID"}),
                _tool_step("containment-activity", "Fetch incident activity", "freshservice.tickets.activities", param_sources={"ticket_id": "$TICKET_ID"}),
            ],
            approvals=[{"when": "external_containment_write", "required": True}],
            task="Prepare containment options and approval requirements. Do not execute or claim containment; endpoint/identity writes are not part of the v1 executable profile.",
        ),
        _play(
            "remediation-verification-review",
            "Remediation Verification Review",
            "Find remediation work marked complete but lacking sufficient source evidence, and flag overdue or reopened findings.",
            kpis=["remediation_sla", "verification_gap_rate", "critical_workload"],
            outcome_event="remediation_verification_reviewed",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:security-risk-analyst",
            evidence_steps=[
                _tool_step("remediation-list", "List remediation work", "freshservice.tickets.list", param_sources={"per_page": 100}),
            ],
            task="Distinguish planned, accepted, and independently verified remediation. Flag any completion claim that lacks source-of-record evidence.",
        ),
        _play(
            "security-incident-brief",
            "Security Incident Brief",
            "Maintain a concise internal incident brief covering timeline, impact, decisions, owners, evidence gaps, and next actions.",
            kpis=["communication_latency", "incident_context_time"],
            outcome_event="security_incident_brief_updated",
            trigger={"type": "event", "event": "security.incident_updated"},
            agent_seed="agent:security-incident-investigator",
            evidence_steps=[
                _tool_step("brief-ticket", "Fetch incident record", "freshservice.tickets.get", param_sources={"ticket_id": "$TICKET_ID"}),
                _tool_step("brief-activity", "Fetch incident activity", "freshservice.tickets.activities", param_sources={"ticket_id": "$TICKET_ID"}),
            ],
            task="Create a factual internal brief. Label uncertainty and never present a recommendation as a completed action.",
        ),
        _play(
            "post-incident-review",
            "Post-Incident Review",
            "Produce a blameless review of root causes, control gaps, recurrence patterns, remediation evidence, and measurable follow-up actions.",
            kpis=["post_incident_completion", "verification_gap_rate", "hours_saved"],
            outcome_event="post_incident_review_completed",
            trigger={"type": "event", "event": "security.incident_closed"},
            agent_seed="agent:security-learning-analyst",
            evidence_steps=[
                _tool_step("pir-ticket", "Fetch closed incident", "freshservice.tickets.get", param_sources={"ticket_id": "$TICKET_ID"}),
                _tool_step("pir-activity", "Fetch closed incident activity", "freshservice.tickets.activities", param_sources={"ticket_id": "$TICKET_ID"}),
            ],
            task="Produce a blameless evidence-backed review with root causes, control gaps, accountable follow-up work, and measurable prevention criteria.",
        ),
    ]

    skill_package = "security-operations-skills"
    skill_requirements = [
        "security-alert-triage",
        "incident-assessment",
        "identity-risk-analysis",
        "vulnerability-prioritization",
        "containment-planning",
        "incident-communications",
        "post-incident-review",
    ]

    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": "Security operations lose response time when alerts, incident context, vulnerability work, containment planning, communications, and remediation proof are fragmented.",
            "target_outcome": "Reduce security investigation and coordination time while improving remediation prioritization, verification discipline, and measurable incident readiness.",
            "baseline_metric": "security_queue_age",
            "success_criteria": [
                "All eight Plays install into Gravitre's canonical Play/workflow runtime.",
                "Every executable v1 action is a registered source-of-record read.",
                "Containment remains approval-gated planning until governed endpoint/identity write contracts exist.",
                "Every KPI resolves from the installed dataset or verified Play outcomes.",
                "A measured declared outcome event is required before Outcome Verified status can be earned.",
            ],
            "outcome_events": [play["outcome_events"][0] for play in plays],
            "kpis": kpis,
            "verification_required": True,
        },
        "agents": [
            {"seed_label": "agent:security-operations-coordinator", "name": "Security Operations Coordinator", "purpose": "Coordinate alert triage, queue prioritization, and security operating flow.", "role": "Security Operations Coordinator", "department": "Security Operations", "capabilities": ["security-alert-triage", "incident-assessment"], "systems": ["freshservice", "huntress", "sentinelone", "crowdstrike"]},
            {"seed_label": "agent:security-incident-investigator", "name": "Security Incident Investigator", "purpose": "Build defensible incident timelines and evidence-backed assessments.", "role": "Incident Investigator", "department": "Security Operations", "capabilities": ["incident-assessment", "incident-communications"], "systems": ["freshservice", "okta", "jumpcloud", "microsoft_intune"]},
            {"seed_label": "agent:security-identity-analyst", "name": "Identity Risk Analyst", "purpose": "Identify and prioritize identity-related incident evidence and missing provider context.", "role": "Identity Risk Analyst", "department": "Security Operations", "capabilities": ["identity-risk-analysis"], "systems": ["freshservice", "okta", "jumpcloud"]},
            {"seed_label": "agent:security-risk-analyst", "name": "Security Risk Analyst", "purpose": "Prioritize vulnerability/remediation work and verify remediation evidence.", "role": "Security Risk Analyst", "department": "Security Operations", "capabilities": ["vulnerability-prioritization"], "systems": ["freshservice", "connectsecure", "huntress"]},
            {"seed_label": "agent:security-response-coordinator", "name": "Containment Coordinator", "purpose": "Prepare proportionate containment plans, approvals, rollback, and verification requirements.", "role": "Containment Coordinator", "department": "Security Operations", "capabilities": ["containment-planning"], "systems": ["freshservice", "sentinelone", "crowdstrike", "microsoft_intune"]},
            {"seed_label": "agent:security-learning-analyst", "name": "Security Learning Analyst", "purpose": "Turn verified incident evidence into post-incident learning and measurable preventive work.", "role": "Security Learning Analyst", "department": "Security Operations", "capabilities": ["post-incident-review"], "systems": ["freshservice"]},
        ],
        "plays": plays,
        "knowledge": [
            {"seed_label": "security-incident-policy", "title": "Incident Response Policy", "type": "manual", "metadata": {"purpose": "Severity, escalation, command, evidence, and notification rules."}},
            {"seed_label": "security-containment-runbooks", "title": "Containment Runbooks", "type": "manual", "metadata": {"purpose": "Approved containment, rollback, and verification procedures."}},
            {"seed_label": "security-remediation-sla", "title": "Security Remediation SLA", "type": "manual", "metadata": {"purpose": "Severity-based remediation targets and exception rules."}},
            {"seed_label": "security-comms", "title": "Incident Communication Standards", "type": "manual", "metadata": {"purpose": "Internal/external incident communication templates and approval boundaries."}},
            {"seed_label": "security-pir", "title": "Post-Incident Review Standard", "type": "manual", "metadata": {"purpose": "Blameless PIR structure, evidence expectations, and follow-up ownership."}},
        ],
        "dataset": {
            "entities": [
                {"name": "security_service_records", "source": "freshservice", "primary_key": "ticket_id", "fields": ["ticket_id", "type", "category", "priority", "status", "owner", "created_at", "updated_at", "due_at", "resolved_at", "closed_at"]},
                {"name": "security_activity", "source": "freshservice", "primary_key": "activity_id", "fields": ["activity_id", "ticket_id", "actor", "event_type", "created_at", "metadata"]},
                {"name": "security_assets", "source": "optional_security_connectors", "primary_key": "asset_id", "fields": ["asset_id", "provider", "asset_type", "criticality", "status"]},
                {"name": "identity_findings", "source": "optional_identity_connectors", "primary_key": "finding_id", "fields": ["finding_id", "provider", "identity_id", "risk_level", "status", "created_at"]},
                {"name": "vulnerability_findings", "source": "optional_security_connectors", "primary_key": "finding_id", "fields": ["finding_id", "provider", "severity", "asset_id", "status", "detected_at", "due_at", "verified_at"]},
                {"name": "play_outcomes", "source": "gravitre_verified_outcomes", "primary_key": "outcome_id", "fields": ["outcome_id", "play_key", "status", "verified_at", "metric_delta"]},
            ],
            "metrics": [
                {"key": row["key"], "label": row["label"], "formula": f"verified_metric('{row['key']}')", "unit": row["unit"]}
                for row in kpis
            ],
        },
        "dashboard": {
            "title": "Security Operations Command Center",
            "refresh_mode": "event",
            "metrics": [
                {"kpi_key": row["key"], "label": row["label"], "visualization": "trend" if row["unit"] in {"minutes", "hours", "percent"} else "metric", "description": f"Marketplace 3.0 security KPI: {row['label']}."}
                for row in kpis
            ],
        },
        "skills": [skill_package],
        "skill_requirements": skill_requirements,
        "skill_bindings": {skill: skill_package for skill in skill_requirements},
        "runtime_profiles": [
            {
                "provider": "freshservice",
                "status": "tested",
                "actions": [
                    "freshservice.tickets.list",
                    "freshservice.tickets.get",
                    "freshservice.tickets.activities",
                ],
            }
        ],
        "connector_alternatives": [
            ["freshservice"],
            ["huntress", "sentinelone", "crowdstrike", "connectsecure"],
            ["okta", "jumpcloud"],
            ["microsoft_intune", "jamf_pro"],
        ],
    }
