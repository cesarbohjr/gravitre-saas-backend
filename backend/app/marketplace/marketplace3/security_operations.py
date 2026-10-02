"""Marketplace 3.0 flagship blueprint: Security Operations.

This blueprint is deliberately certification-gated. It is not public Marketplace
inventory until connector actions, skill bindings, and runtime profiles have
passed Marketplace 3.0 certification.
"""
from __future__ import annotations

from typing import Any


SECURITY_OPERATIONS_PLAY_KEYS = (
    "security-alert-triage",
    "vulnerability-prioritizer",
    "identity-compromise-investigator",
    "containment-coordinator",
    "remediation-tracker",
    "security-incident-brief",
    "post-incident-review",
    "security-posture-watch",
)


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
    approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "description": description,
        "trigger": trigger,
        "workflow_steps": [
            _agent_step(f"{key}-analyze", f"{name} analysis", agent_seed, task),
        ],
        "outcome_events": [outcome_event],
        "kpi_keys": kpis,
        "approvals": approvals or [],
        "verification": {
            "mode": "source_of_record",
            "provider_acceptance_is_terminal": False,
        },
    }


def build_security_operations_outcome_pack_config() -> dict[str, Any]:
    kpis = [
        {"key": "mttd", "label": "Mean time to detect", "unit": "minutes", "direction": "decrease", "source": "security_incidents"},
        {"key": "mttr_security", "label": "Mean time to remediate", "unit": "minutes", "direction": "decrease", "source": "security_incidents"},
        {"key": "critical_exposure_count", "label": "Critical exposures", "unit": "count", "direction": "decrease", "source": "security_findings"},
        {"key": "containment_time", "label": "Containment time", "unit": "minutes", "direction": "decrease", "source": "security_incidents"},
        {"key": "remediation_sla", "label": "Remediation SLA compliance", "unit": "percent", "direction": "increase", "source": "security_findings"},
        {"key": "false_positive_rate", "label": "False positive rate", "unit": "percent", "direction": "decrease", "source": "security_alerts"},
        {"key": "identity_risk_open", "label": "Open identity risks", "unit": "count", "direction": "decrease", "source": "identity_findings"},
        {"key": "security_automation_rate", "label": "Security automation rate", "unit": "percent", "direction": "increase", "source": "play_runs"},
        {"key": "verified_containments", "label": "Verified containments", "unit": "count", "direction": "increase", "source": "play_outcomes"},
        {"key": "incident_recurrence_rate", "label": "Incident recurrence rate", "unit": "percent", "direction": "decrease", "source": "security_incidents"},
    ]

    plays = [
        _play(
            "security-alert-triage", "Security Alert Triage",
            "Correlate endpoint, identity, vulnerability, and service context to prioritize alerts and suppress obvious noise.",
            kpis=["mttd", "false_positive_rate", "security_automation_rate"],
            outcome_event="security_alert_triaged",
            trigger={"type": "event", "event": "security.alert_created"},
            agent_seed="agent:security-operations-coordinator",
            task="Correlate alert evidence across connected security systems, classify severity and confidence, and distinguish confirmed facts from hypotheses.",
        ),
        _play(
            "vulnerability-prioritizer", "Vulnerability Prioritizer",
            "Rank vulnerabilities using exploitability, asset importance, exposure, identity context, and business impact.",
            kpis=["critical_exposure_count", "remediation_sla"],
            outcome_event="vulnerability_priority_assigned",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:security-risk-analyst",
            task="Prioritize vulnerabilities from verified evidence. Explain ranking drivers and never infer exploitability without supporting data.",
        ),
        _play(
            "identity-compromise-investigator", "Identity Compromise Investigator",
            "Assemble identity, endpoint, MFA, directory, and recent activity evidence for suspected account compromise.",
            kpis=["mttd", "identity_risk_open", "containment_time"],
            outcome_event="identity_compromise_investigated",
            trigger={"type": "event", "event": "identity.risk_detected"},
            agent_seed="agent:security-incident-investigator",
            task="Build an evidence-backed compromise assessment using identity and endpoint signals, identify missing evidence, and recommend next investigative steps.",
        ),
        _play(
            "containment-coordinator", "Containment Coordinator",
            "Prepare the smallest effective containment plan and route consequential actions through approval and source-of-record verification.",
            kpis=["containment_time", "verified_containments", "mttr_security"],
            outcome_event="security_containment_verified",
            trigger={"type": "event", "event": "incident.containment_recommended"},
            agent_seed="agent:security-operations-coordinator",
            task="Prepare a containment plan proportional to evidence and impact. Do not claim containment until the provider state has been re-read and verified.",
            approvals=[{"when": "external_write", "required": True}],
        ),
        _play(
            "remediation-tracker", "Remediation Tracker",
            "Track security remediation through completion and flag findings that are stalled, reopened, or approaching SLA breach.",
            kpis=["remediation_sla", "critical_exposure_count", "mttr_security"],
            outcome_event="security_remediation_verified",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:security-risk-analyst",
            task="Review remediation evidence, distinguish planned from completed work, and escalate overdue or unverifiable fixes.",
        ),
        _play(
            "security-incident-brief", "Security Incident Brief",
            "Maintain a concise verified incident timeline, impact summary, decisions, owners, and outstanding evidence gaps.",
            kpis=["mttd", "containment_time", "mttr_security"],
            outcome_event="security_incident_brief_updated",
            trigger={"type": "event", "event": "incident.updated"},
            agent_seed="agent:security-incident-investigator",
            task="Create a factual incident brief from verified events and explicitly label uncertainty, decisions, and unresolved evidence gaps.",
        ),
        _play(
            "post-incident-review", "Post-Incident Review",
            "Produce a root-cause and control-improvement review from the verified incident timeline and remediation evidence.",
            kpis=["incident_recurrence_rate", "mttr_security"],
            outcome_event="post_incident_review_completed",
            trigger={"type": "event", "event": "incident.closed"},
            agent_seed="agent:security-risk-analyst",
            task="Produce a blameless evidence-backed post-incident review with root causes, control gaps, owners, and measurable preventive actions.",
        ),
        _play(
            "security-posture-watch", "Security Posture Watch",
            "Monitor cross-system security posture for deterioration, concentration of risk, overdue remediation, and emerging operational patterns.",
            kpis=["critical_exposure_count", "identity_risk_open", "remediation_sla", "security_automation_rate"],
            outcome_event="security_posture_reviewed",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:security-risk-analyst",
            task="Review security posture trends across connected systems, identify material deterioration, and prioritize the next controls or remediation work.",
        ),
    ]

    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": "Security teams lose time to noisy alerts, fragmented evidence, slow prioritization, inconsistent containment, and remediation that is difficult to verify.",
            "target_outcome": "Reduce detection, containment, and remediation time while improving prioritization quality, SLA adherence, and verified security outcomes.",
            "baseline_metric": "mttr_security",
            "success_criteria": [
                "All eight Security Operations Plays install into the canonical Gravitre Play/workflow runtime.",
                "Consequential containment or remediation writes require approval and source-of-record verification.",
                "Every declared KPI is represented in the installed security dashboard.",
                "At least one verified security outcome event is required before Outcome Verified certification.",
            ],
            "outcome_events": [play["outcome_events"][0] for play in plays],
            "kpis": kpis,
            "verification_required": True,
        },
        "agents": [
            {
                "seed_label": "agent:security-operations-coordinator",
                "name": "Security Operations Coordinator",
                "purpose": "Coordinate alert triage, containment planning, and verified incident execution.",
                "role": "Security Operations",
                "department": "Security Operations",
                "capabilities": ["alert-triage", "containment-planning", "incident-coordination"],
                "systems": ["huntress", "sentinelone", "crowdstrike", "connectsecure"],
            },
            {
                "seed_label": "agent:security-incident-investigator",
                "name": "Security Incident Investigator",
                "purpose": "Correlate identity and endpoint evidence into defensible incident assessments and timelines.",
                "role": "Incident Investigation",
                "department": "Security Operations",
                "capabilities": ["incident-investigation", "identity-risk", "timeline-analysis"],
                "systems": ["okta", "duo", "jumpcloud", "microsoft_intune", "sentinelone", "crowdstrike"],
            },
            {
                "seed_label": "agent:security-risk-analyst",
                "name": "Security Risk Analyst",
                "purpose": "Prioritize vulnerabilities, monitor remediation, and identify recurring control gaps.",
                "role": "Security Risk",
                "department": "Security Operations",
                "capabilities": ["vulnerability-prioritization", "risk-analysis", "post-incident-review"],
                "systems": ["connectsecure", "huntress", "sentinelone", "crowdstrike"],
            },
        ],
        "plays": plays,
        "knowledge": [
            {"seed_label": "incident-response-policy", "title": "Incident Response Policy", "type": "manual", "metadata": {"purpose": "Incident severity, escalation, and response policy."}},
            {"seed_label": "containment-runbooks", "title": "Containment Runbooks", "type": "manual", "metadata": {"purpose": "Approved containment procedures and rollback guidance."}},
            {"seed_label": "security-exception-policy", "title": "Security Exception Policy", "type": "manual", "metadata": {"purpose": "Exception ownership, expiry, and approval rules."}},
        ],
        "dataset": {
            "entities": [
                {"name": "security_alerts", "source": "security_connectors", "primary_key": "id", "fields": ["id", "provider", "severity", "status", "asset_id", "identity_id", "created_at", "resolved_at"]},
                {"name": "security_findings", "source": "security_connectors", "primary_key": "id", "fields": ["id", "provider", "severity", "exploitability", "asset_id", "status", "due_at", "remediated_at"]},
                {"name": "security_incidents", "source": "play_outcomes", "primary_key": "id", "fields": ["id", "opened_at", "detected_at", "contained_at", "resolved_at", "severity", "verified"]},
                {"name": "identity_findings", "source": "identity_connectors", "primary_key": "id", "fields": ["id", "provider", "identity_id", "risk_level", "status", "created_at"]},
            ],
            "metrics": [
                {"key": "mttd", "label": "Mean time to detect", "formula": "avg(detected_at-opened_at)", "unit": "minutes"},
                {"key": "mttr_security", "label": "Mean time to remediate", "formula": "avg(resolved_at-detected_at)", "unit": "minutes"},
                {"key": "critical_exposure_count", "label": "Critical exposures", "formula": "count(security_findings where severity=critical and status!=remediated)", "unit": "count"},
                {"key": "remediation_sla", "label": "Remediation SLA compliance", "formula": "remediated_within_sla/closed_findings", "unit": "percent"},
                {"key": "security_automation_rate", "label": "Security automation rate", "formula": "automated_verified_actions/all_verified_actions", "unit": "percent"},
            ],
        },
        "dashboard": {
            "title": "Security Operations Outcomes",
            "metrics": [
                {"kpi_key": kpi["key"], "label": kpi["label"], "visualization": "trend" if kpi["unit"] != "count" else "metric"}
                for kpi in kpis
            ],
            "refresh_mode": "event",
        },
        "skills": [],
        "skill_requirements": [
            "security-alert-correlation",
            "vulnerability-risk-prioritization",
            "identity-compromise-analysis",
            "incident-response-reasoning",
        ],
        "skill_bindings": {},
        "runtime_profiles": [],
        "connector_alternatives": [
            ["huntress", "sentinelone", "crowdstrike"],
            ["connectsecure"],
            ["okta", "duo", "jumpcloud"],
            ["microsoft_intune", "jamf_pro"],
        ],
    }
