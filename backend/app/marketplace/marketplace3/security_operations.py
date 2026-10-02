"""Marketplace 3.0 flagship: Security Operations.

Security Operations remains internal/draft until evidence-linked live certification
is earned. Freshservice is the tested/governed v1 runtime profile. Security
platform connectors are optional context until their governed action contracts
reach equivalent runtime coverage.
"""
from __future__ import annotations

from typing import Any

from app.marketplace.marketplace3.department_portfolio import (
    PACK_SPECS,
    build_department_outcome_pack_config,
    build_department_skill_package_config,
)


SECURITY_OPERATIONS_PLAY_KEYS = (
    "security-alert-triage",
    "incident-context-builder",
    "identity-risk-review",
    "vulnerability-work-queue",
    "containment-readiness-review",
    "remediation-follow-up",
    "incident-communications-brief",
    "post-incident-review",
    "security-posture-watch",
)


_AGENT_PURPOSES = {
    "agent:security-operations-coordinator": (
        "Coordinate security workload, escalation, remediation follow-up, and the "
        "overall governed SecOps operating loop."
    ),
    "agent:security-investigation-analyst": (
        "Assemble and analyze source evidence for incidents without overstating "
        "confidence or treating provider acceptance as terminal truth."
    ),
    "agent:identity-risk-analyst": (
        "Review identity-related risk signals and service evidence while keeping "
        "containment and access changes approval-governed."
    ),
    "agent:vulnerability-analyst": (
        "Prioritize vulnerability and remediation work using verified business and "
        "service context."
    ),
    "agent:incident-commander": (
        "Coordinate incident readiness, communications, post-incident review, and "
        "cross-functional escalation from verified source records."
    ),
}


_PLAY_OVERRIDES: dict[str, dict[str, Any]] = {
    "security-alert-triage": {
        "trigger": {"type": "scheduled", "cadence": "hourly"},
        "outcome_events": ["security_alert_prioritized"],
    },
    "incident-context-builder": {
        "trigger": {"type": "event", "event": "security.incident_opened"},
        "outcome_events": ["incident_context_prepared"],
    },
    "identity-risk-review": {
        "trigger": {"type": "scheduled", "cadence": "hourly"},
        "outcome_events": ["identity_risk_reviewed"],
    },
    "vulnerability-work-queue": {
        "trigger": {"type": "scheduled", "cadence": "daily"},
        "outcome_events": ["vulnerability_queue_prioritized"],
    },
    "containment-readiness-review": {
        "trigger": {"type": "manual"},
        "outcome_events": ["containment_readiness_reviewed"],
        "approvals": [
            {
                "when": "containment_execution",
                "required": True,
                "verification": "source_of_record_field_assert",
            }
        ],
    },
    "remediation-follow-up": {
        "trigger": {"type": "scheduled", "cadence": "hourly"},
        "outcome_events": ["remediation_follow_up_completed"],
    },
    "incident-communications-brief": {
        "trigger": {"type": "event", "event": "security.incident_status_changed"},
        "outcome_events": ["incident_communications_brief_prepared"],
        "approvals": [{"when": "send_external_message", "required": True}],
    },
    "post-incident-review": {
        "trigger": {"type": "event", "event": "security.incident_closed"},
        "outcome_events": ["post_incident_review_completed"],
    },
    "security-posture-watch": {
        "trigger": {"type": "scheduled", "cadence": "daily"},
        "outcome_events": ["security_posture_reviewed"],
    },
}


def build_security_operations_outcome_pack_config() -> dict[str, Any]:
    config = build_department_outcome_pack_config("security-operations-3")

    for agent in config["agents"]:
        purpose = _AGENT_PURPOSES.get(str(agent.get("seed_label") or ""))
        if purpose:
            agent["purpose"] = purpose

    for play in config["plays"]:
        override = _PLAY_OVERRIDES.get(str(play.get("key") or ""), {})
        for key, value in override.items():
            play[key] = value
        play["verification"] = {
            "mode": "source_of_record",
            "provider_acceptance_is_terminal": False,
        }

    config["outcome_contract"]["outcome_events"] = [
        str(event)
        for play in config["plays"]
        for event in (play.get("outcome_events") or [])
        if str(event).strip()
    ]

    config["knowledge"] = [
        {
            "seed_label": "security-operations-3:incident-response",
            "title": "Security Incident Response Policy",
            "type": "manual",
            "metadata": {
                "purpose": "Severity, escalation, evidence handling, approvals, and incident command policy."
            },
        },
        {
            "seed_label": "security-operations-3:containment",
            "title": "Containment & Recovery Runbook",
            "type": "manual",
            "metadata": {
                "purpose": "Approved containment patterns, rollback requirements, recovery checks, and verification rules."
            },
        },
        {
            "seed_label": "security-operations-3:vulnerability",
            "title": "Vulnerability Prioritization Standard",
            "type": "manual",
            "metadata": {
                "purpose": "Exploitability, asset criticality, exposure, compensating controls, and remediation SLA guidance."
            },
        },
        {
            "seed_label": "security-operations-3:communications",
            "title": "Incident Communications Standard",
            "type": "manual",
            "metadata": {
                "purpose": "Internal/external update standards, audience rules, approved language, and escalation thresholds."
            },
        },
        {
            "seed_label": "security-operations-3:pir",
            "title": "Post-Incident Review Standard",
            "type": "manual",
            "metadata": {
                "purpose": "Timeline reconstruction, root cause, control gap, follow-up ownership, and learning requirements."
            },
        },
    ]

    config["dataset"] = {
        "entities": [
            {
                "name": "security_cases",
                "source": "service_and_security_sources",
                "primary_key": "case_id",
                "fields": [
                    "case_id", "severity", "status", "owner", "account_id",
                    "created_at", "acknowledged_at", "resolved_at", "updated_at",
                ],
            },
            {
                "name": "security_assets",
                "source": "connected_security_sources",
                "primary_key": "asset_id",
                "fields": [
                    "asset_id", "account_id", "asset_type", "criticality",
                    "exposure", "last_seen_at",
                ],
            },
            {
                "name": "identity_risk",
                "source": "connected_identity_sources",
                "primary_key": "identity_id",
                "fields": [
                    "identity_id", "account_id", "risk_state", "signal_count",
                    "last_signal_at",
                ],
            },
            {
                "name": "vulnerabilities",
                "source": "connected_security_sources",
                "primary_key": "finding_id",
                "fields": [
                    "finding_id", "asset_id", "severity", "exploitability",
                    "remediation_status", "due_at", "verified_at",
                ],
            },
            {
                "name": "remediation_items",
                "source": "security_work_queue",
                "primary_key": "remediation_id",
                "fields": [
                    "remediation_id", "case_id", "owner", "status",
                    "due_at", "completed_at", "verified_at",
                ],
            },
            {
                "name": "incident_timeline",
                "source": "verified_incident_activity",
                "primary_key": "event_id",
                "fields": [
                    "event_id", "case_id", "event_type", "source",
                    "occurred_at", "verified_at",
                ],
            },
            {
                "name": "verified_outcomes",
                "source": "gravitre_verified_outcomes",
                "primary_key": "outcome_id",
                "fields": [
                    "outcome_id", "play_key", "status", "verified_at",
                    "metric_delta", "source_record",
                ],
            },
        ],
        "metrics": config["dataset"]["metrics"],
    }

    config["dashboard"]["title"] = "Security Operations Command Center"
    for metric in config["dashboard"]["metrics"]:
        metric["description"] = (
            f"Marketplace 3.0 verified SecOps KPI: {metric['label']}."
        )

    # Freshservice is the tested v1 runtime. Optional security platforms remain
    # discoverable context only and cannot satisfy the required runtime gate.
    config["connector_alternatives"] = [
        ["freshservice"],
        ["huntress", "sentinelone", "crowdstrike", "connectsecure"],
        ["okta", "microsoft_intune"],
    ]
    return config


def build_security_operations_skill_package_config() -> dict[str, Any]:
    return build_department_skill_package_config("security-operations-skills")


def security_operations_marketplace3_assets() -> list[Any]:
    from app.marketplace.seed_catalog import CatalogAsset

    spec = PACK_SPECS["security-operations-3"]
    config = build_security_operations_outcome_pack_config()
    freshservice = {
        "connectorType": "freshservice",
        "label": "Freshservice",
        "required": True,
        "connectPath": "/connectors?type=freshservice",
        "requirementNote": (
            "Tested/governed Security Operations 3.0 runtime for v1. "
            "Production verification requires evidence-linked live source-of-record proof."
        ),
    }

    agents = [
        CatalogAsset(
            slug=f"secops3-{str(agent['seed_label']).split(':')[-1]}",
            title=str(agent["name"]),
            description=str(agent["purpose"]),
            asset_type="ai_agent",
            category="ai_agent",
            department="Security Operations",
            visibility="internal",
            status="draft",
            tags=["security", "secops", "agent", "marketplace-3"],
            config=agent,
            required_connectors=[freshservice],
        )
        for agent in config["agents"]
    ]

    plays = [
        CatalogAsset(
            slug=f"security-operations-3-play-{play['key']}",
            title=str(play["name"]),
            description=str(play["description"]),
            asset_type="play",
            category="play",
            department="Security Operations",
            visibility="internal",
            status="draft",
            tags=["security", "secops", "play", "marketplace-3"],
            config=play,
            required_connectors=[freshservice],
            business_outcome=str(play["outcome_events"][0]),
            use_case=str(play["description"]),
        )
        for play in config["plays"]
    ]

    skill_package = CatalogAsset(
        slug="security-operations-skills",
        title="Security Operations Skills",
        description=(
            "Reviewed first-party guidance skills for triage, investigation, identity risk, "
            "vulnerability prioritization, containment planning, communications, and post-incident review."
        ),
        asset_type="capability_package",
        category="capability_package",
        department="Security Operations",
        visibility="internal",
        status="draft",
        tags=["security", "secops", "skills", "marketplace-3", "gravitre"],
        config=build_security_operations_skill_package_config(),
    )

    knowledge = CatalogAsset(
        slug="security-operations-3-knowledge",
        title="Security Operations 3.0 Knowledge",
        description=(
            "Incident response, containment, vulnerability, communications, and "
            "post-incident operating standards."
        ),
        asset_type="knowledge_pack",
        category="knowledge_pack",
        department="Security Operations",
        visibility="internal",
        status="draft",
        tags=["security", "secops", "knowledge", "marketplace-3"],
        config={"documents": config["knowledge"]},
    )

    dataset = CatalogAsset(
        slug="security-operations-3-dataset",
        title="Security Operations 3.0 Dataset",
        description=(
            "Normalized incidents, assets, identities, vulnerabilities, remediation, "
            "timelines, and verified outcome metrics."
        ),
        asset_type="dataset_pack",
        category="dataset_pack",
        department="Security Operations",
        visibility="internal",
        status="draft",
        tags=["security", "secops", "dataset", "marketplace-3"],
        config=config["dataset"],
        required_connectors=[freshservice],
    )

    dashboard = CatalogAsset(
        slug="security-operations-3-dashboard",
        title="Security Operations Command Center",
        description=(
            "KPI dashboard for workload, investigation speed, remediation, incident "
            "communications, post-incident completion, and verified security outcomes."
        ),
        asset_type="dashboard_pack",
        category="dashboard_pack",
        department="Security Operations",
        visibility="internal",
        status="draft",
        tags=["security", "secops", "dashboard", "kpi", "marketplace-3"],
        config=config["dashboard"],
    )

    child_slugs = (
        [asset.slug for asset in agents]
        + [asset.slug for asset in plays]
        + [skill_package.slug, knowledge.slug, dataset.slug, dashboard.slug]
    )

    outcome = CatalogAsset(
        slug="security-operations-3",
        title="Security Operations 3.0",
        description=spec["target"],
        asset_type="outcome_pack",
        category="outcome_pack",
        department="Security Operations",
        visibility="internal",
        status="draft",
        tags=["security", "secops", "outcome-pack", "marketplace-3"],
        pack_tier=3,
        config=config,
        required_connectors=[freshservice],
        pack_children=child_slugs,
        business_outcome=spec["target"],
        use_case="Security operations",
    )
    return agents + plays + [skill_package, knowledge, dataset, dashboard, outcome]
