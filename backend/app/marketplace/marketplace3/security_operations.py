"""Marketplace 3.0 blueprint: Security Operations.

The pack remains unpublished until its runtime profile and reviewed skill
dependencies are production verified. All execution stays on Gravitre's
canonical workflow / tool governance path.
"""
from __future__ import annotations

from typing import Any


SECURITY_OPERATIONS_PLAY_KEYS = (
    "security-alert-triage",
    "vulnerability-prioritizer",
    "identity-compromise-investigator",
    "containment-coordinator",
    "security-remediation-tracker",
    "security-incident-brief",
    "post-incident-review",
    "security-posture-watch",
)


def _okta_step(
    step_id: str,
    name: str,
    action: str,
    *,
    param_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "action": action,
        "tool_action": action,
        "vendor": "okta",
        "connector": "okta",
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
        "requires_connector": "okta",
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
    event: str,
    trigger: dict[str, Any],
    agent_seed: str,
    task: str,
    evidence_steps: list[dict[str, Any]] | None = None,
    approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    steps = list(evidence_steps or [])
    steps.append(_agent_step(f"{key}-analyze", f"{name} analysis", agent_seed, task))
    return {
        "key": key,
        "name": name,
        "description": description,
        "trigger": trigger,
        "workflow_steps": steps,
        "outcome_events": [event],
        "kpi_keys": kpis,
        "approvals": approvals or [],
        "verification": {
            "mode": "source_of_record",
            "provider_acceptance_is_terminal": False,
        },
    }


def build_security_operations_outcome_pack_config() -> dict[str, Any]:
    kpis = [
        {"key": "mttd", "label": "Mean time to detect", "unit": "minutes", "direction": "decrease", "source": "security_events"},
        {"key": "triage_time", "label": "Alert triage time", "unit": "minutes", "direction": "decrease", "source": "security_cases"},
        {"key": "false_positive_rate", "label": "False-positive rate", "unit": "percent", "direction": "decrease", "source": "security_cases"},
        {"key": "investigation_time", "label": "Investigation time", "unit": "minutes", "direction": "decrease", "source": "security_cases"},
        {"key": "identity_risk_cases", "label": "Open identity-risk cases", "unit": "count", "direction": "decrease", "source": "security_events"},
        {"key": "containment_time", "label": "Containment time", "unit": "minutes", "direction": "decrease", "source": "security_cases"},
        {"key": "approval_latency", "label": "Containment approval latency", "unit": "minutes", "direction": "decrease", "source": "play_runs"},
        {"key": "mttr", "label": "Security MTTR", "unit": "minutes", "direction": "decrease", "source": "security_cases"},
        {"key": "critical_vulnerability_backlog", "label": "Critical vulnerability backlog", "unit": "count", "direction": "decrease", "source": "security_findings"},
        {"key": "remediation_sla", "label": "Remediation SLA compliance", "unit": "percent", "direction": "increase", "source": "security_findings"},
        {"key": "risk_reduction", "label": "Verified risk reduction", "unit": "score", "direction": "increase", "source": "play_outcomes"},
        {"key": "open_security_actions", "label": "Open security actions", "unit": "count", "direction": "decrease", "source": "security_cases"},
        {"key": "verification_inconclusive_rate", "label": "Verification inconclusive rate", "unit": "percent", "direction": "decrease", "source": "play_runs"},
        {"key": "incident_update_latency", "label": "Incident update latency", "unit": "minutes", "direction": "decrease", "source": "security_cases"},
        {"key": "stakeholder_update_rate", "label": "Stakeholder update compliance", "unit": "percent", "direction": "increase", "source": "security_cases"},
        {"key": "repeat_incident_rate", "label": "Repeat incident rate", "unit": "percent", "direction": "decrease", "source": "security_cases"},
        {"key": "remediation_completion_rate", "label": "Remediation completion rate", "unit": "percent", "direction": "increase", "source": "security_findings"},
        {"key": "control_gap_count", "label": "Open control gaps", "unit": "count", "direction": "decrease", "source": "play_outcomes"},
        {"key": "risk_score", "label": "Security posture risk score", "unit": "score", "direction": "decrease", "source": "security_findings"},
    ]

    log_read = _okta_step(
        "okta-events",
        "Read Okta security events",
        "okta.system_logs.list",
        param_sources={"limit": 100, "sortOrder": "DESCENDING"},
    )

    plays = [
        _play(
            "security-alert-triage",
            "Security Alert Triage",
            "Prioritize identity/security events by severity, affected user, context, and business impact.",
            kpis=["mttd", "triage_time", "false_positive_rate"],
            event="security_alert_triaged",
            trigger={"type": "event", "event": "security.alert_created"},
            agent_seed="agent:security-triage-analyst",
            evidence_steps=[log_read],
            task="Triage recent security events using only source evidence. Separate confirmed facts, risk indicators, and assumptions.",
        ),
        _play(
            "vulnerability-prioritizer",
            "Vulnerability Prioritizer",
            "Rank vulnerabilities using exploitability, asset criticality, recurrence, identity exposure, and business impact.",
            kpis=["critical_vulnerability_backlog", "remediation_sla", "risk_reduction"],
            event="vulnerability_priority_reviewed",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:security-posture-analyst",
            task="Prioritize vulnerability findings from connected security sources and explain the evidence behind the ordering.",
        ),
        _play(
            "identity-compromise-investigator",
            "Identity Compromise Investigator",
            "Investigate suspicious identity activity and account-compromise indicators.",
            kpis=["investigation_time", "identity_risk_cases", "mttd"],
            event="identity_investigation_completed",
            trigger={"type": "event", "event": "identity.risk_detected"},
            agent_seed="agent:identity-investigator",
            evidence_steps=[log_read],
            task="Correlate suspicious sign-ins, user-risk events, authentication changes, and related evidence. Flag what is known versus inferred.",
        ),
        _play(
            "containment-coordinator",
            "Containment Coordinator",
            "Prepare containment options, affected identities/assets, approvals, and verification steps.",
            kpis=["containment_time", "approval_latency", "mttr"],
            event="containment_plan_ready",
            trigger={"type": "event", "event": "security.incident_confirmed"},
            agent_seed="agent:security-incident-coordinator",
            evidence_steps=[log_read],
            approvals=[{"when": "containment_write", "required": True}],
            task="Prepare the smallest safe containment plan. Never execute a consequential provider write without approval and independent verification.",
        ),
        _play(
            "security-remediation-tracker",
            "Security Remediation Tracker",
            "Track remediation tasks through source-of-record confirmation and escalate overdue or unverifiable work.",
            kpis=["remediation_sla", "open_security_actions", "verification_inconclusive_rate"],
            event="security_remediation_reviewed",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:security-incident-coordinator",
            task="Review open remediation commitments, due dates, source evidence, and verification state. Escalate unresolved or verification-inconclusive items.",
        ),
        _play(
            "security-incident-brief",
            "Security Incident Brief",
            "Maintain an evidence-backed incident timeline, impact summary, containment state, and decision log.",
            kpis=["incident_update_latency", "mttr", "stakeholder_update_rate"],
            event="security_incident_brief_updated",
            trigger={"type": "scheduled", "cadence": "hourly"},
            agent_seed="agent:security-incident-coordinator",
            evidence_steps=[log_read],
            task="Produce a concise incident brief grounded in current identity and incident evidence, including unknowns and approvals still required.",
        ),
        _play(
            "post-incident-review",
            "Post-Incident Review",
            "Create a root-cause and control-gap review with measurable prevention actions and owners.",
            kpis=["repeat_incident_rate", "remediation_completion_rate", "control_gap_count"],
            event="post_incident_review_completed",
            trigger={"type": "event", "event": "security.incident_closed"},
            agent_seed="agent:security-posture-analyst",
            evidence_steps=[log_read],
            task="Create a source-backed post-incident review. Identify root cause, contributing conditions, control gaps, owners, and prevention measures.",
        ),
        _play(
            "security-posture-watch",
            "Security Posture Watch",
            "Monitor posture trends and surface material deterioration or recurring identity risk.",
            kpis=["risk_score", "critical_vulnerability_backlog", "identity_risk_cases", "remediation_sla"],
            event="security_posture_reviewed",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:security-posture-analyst",
            evidence_steps=[log_read],
            task="Review current security posture indicators and identify meaningful deterioration, recurring patterns, and overdue remediation.",
        ),
    ]

    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": "Security teams lose time correlating identity and endpoint signals, tracking remediation, and proving that risk-reduction work actually completed.",
            "target_outcome": "Reduce detection, investigation, containment, and remediation time while increasing verified security posture improvement.",
            "baseline_metric": "mttr",
            "success_criteria": [
                "All eight Plays validate against the canonical Play/workflow runtime.",
                "Every recommendation distinguishes source evidence from inference.",
                "Consequential containment actions remain approval-governed and source-of-record verified.",
                "Outcome Verified requires at least one measured verified security outcome event.",
            ],
            "outcome_events": [p["outcome_events"][0] for p in plays],
            "kpis": kpis,
            "verification_required": True,
        },
        "agents": [
            {
                "seed_label": "agent:security-triage-analyst",
                "name": "Security Triage Analyst",
                "purpose": "Prioritize and explain security alerts using identity and security evidence.",
                "role": "Security Triage",
                "department": "Security Operations",
                "capabilities": ["alert-triage", "risk-classification", "evidence-correlation"],
                "systems": ["okta", "huntress", "sentinelone", "crowdstrike"],
            },
            {
                "seed_label": "agent:identity-investigator",
                "name": "Identity Compromise Investigator",
                "purpose": "Investigate suspicious identity activity and account-risk indicators.",
                "role": "Identity Investigation",
                "department": "Security Operations",
                "capabilities": ["identity-investigation", "authentication-analysis", "timeline-analysis"],
                "systems": ["okta", "duo", "microsoft_365"],
            },
            {
                "seed_label": "agent:security-incident-coordinator",
                "name": "Security Incident Coordinator",
                "purpose": "Coordinate incident evidence, containment planning, approvals, remediation, and communications.",
                "role": "Incident Coordination",
                "department": "Security Operations",
                "capabilities": ["incident-command", "containment-planning", "remediation-tracking"],
                "systems": ["okta", "sentinelone", "crowdstrike", "microsoft_intune"],
            },
            {
                "seed_label": "agent:security-posture-analyst",
                "name": "Security Posture Analyst",
                "purpose": "Analyze vulnerabilities, control gaps, recurring incidents, and posture trends.",
                "role": "Security Posture",
                "department": "Security Operations",
                "capabilities": ["vulnerability-prioritization", "post-incident-review", "posture-analysis"],
                "systems": ["connectsecure", "microsoft_intune", "huntress", "okta"],
            },
        ],
        "plays": plays,
        "knowledge": [
            {"seed_label": "incident-response-policy", "title": "Incident Response Policy", "type": "manual", "metadata": {"purpose": "Severity, ownership, escalation, and communications policy."}},
            {"seed_label": "containment-runbooks", "title": "Containment Runbooks", "type": "manual", "metadata": {"purpose": "Approved containment and recovery procedures."}},
            {"seed_label": "security-standards", "title": "Security Standards and Controls", "type": "manual", "metadata": {"purpose": "Control requirements, risk tolerance, and remediation expectations."}},
        ],
        "dataset": {
            "entities": [
                {"name": "security_events", "source": "identity_and_security_connectors", "primary_key": "event_id", "fields": ["event_id", "published_at", "actor_id", "target_id", "event_type", "result", "severity"]},
                {"name": "security_cases", "source": "gravitre_security_plays", "primary_key": "case_id", "fields": ["case_id", "play_key", "status", "detected_at", "contained_at", "resolved_at", "verification_status"]},
                {"name": "security_findings", "source": "security_connectors", "primary_key": "finding_id", "fields": ["finding_id", "asset_id", "severity", "status", "due_at", "verified_at"]},
            ],
            "metrics": [{"key": row["key"], "label": row["label"], "formula": f"derived:{row['key']}", "unit": row["unit"]} for row in kpis],
        },
        "dashboard": {
            "title": "Security Operations Command Center",
            "refresh_mode": "event",
            "metrics": [
                {"kpi_key": row["key"], "label": row["label"], "visualization": "trend" if row["unit"] in {"minutes", "percent", "score"} else "metric", "description": f"Marketplace 3.0 security KPI: {row['label']}."}
                for row in kpis
            ],
        },
        "skills": ["security-operations-skills"],
        "skill_requirements": [
            "security-alert-triage",
            "incident-assessment",
            "identity-risk-analysis",
            "vulnerability-prioritization",
            "containment-planning",
            "incident-communications",
            "post-incident-review",
        ],
        "skill_bindings": {
            "security-alert-triage": "security-operations-skills",
            "incident-assessment": "security-operations-skills",
            "identity-risk-analysis": "security-operations-skills",
            "vulnerability-prioritization": "security-operations-skills",
            "containment-planning": "security-operations-skills",
            "incident-communications": "security-operations-skills",
            "post-incident-review": "security-operations-skills",
        },
        "runtime_profiles": [
            {
                "provider": "okta",
                "status": "tested",
                "actions": ["okta.system_logs.list", "okta.users.get"],
            }
        ],
        "connector_alternatives": [
            ["okta"],
            ["huntress", "sentinelone", "crowdstrike"],
            ["connectsecure", "microsoft_intune"],
            ["slack", "microsoft_teams"],
        ],
    }
