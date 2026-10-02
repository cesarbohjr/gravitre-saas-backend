"""Marketplace 3.0 flagship: Revenue Operations.

The executable v1 profile is HubSpot read-first. Plays prepare recommendations,
briefs, and recovery plans from source evidence. CRM writes remain outside this
flagship until a Play explicitly declares the governed write and verification path.
"""
from __future__ import annotations

from typing import Any


REVENUE_OPERATIONS_PLAY_KEYS = (
    "inbound-lead-qualifier",
    "account-research-brief",
    "meeting-prep-brief",
    "post-meeting-follow-up",
    "stale-deal-recovery",
    "pipeline-risk-review",
    "forecast-integrity-check",
    "renewal-expansion-watch",
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
        "vendor": "hubspot",
        "connector": "hubspot",
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
        "requires_connector": "hubspot",
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
        "verification": {"mode": "source_of_record", "provider_acceptance_is_terminal": False},
        "runtime_inputs": runtime_inputs,
    }


def build_revenue_operations_outcome_pack_config() -> dict[str, Any]:
    kpis = [
        {"key": "speed_to_lead", "label": "Speed to lead", "unit": "minutes", "direction": "decrease", "source": "crm_activity"},
        {"key": "qualified_rate", "label": "Qualified lead rate", "unit": "percent", "direction": "increase", "source": "crm_contacts"},
        {"key": "pipeline_coverage", "label": "Pipeline coverage", "unit": "ratio", "direction": "increase", "source": "crm_deals"},
        {"key": "stage_aging", "label": "Stage aging", "unit": "days", "direction": "decrease", "source": "crm_deals"},
        {"key": "deal_velocity", "label": "Deal velocity", "unit": "days", "direction": "decrease", "source": "crm_deals"},
        {"key": "forecast_integrity", "label": "Forecast integrity", "unit": "percent", "direction": "increase", "source": "crm_deals"},
        {"key": "renewal_risk", "label": "Renewal revenue at risk", "unit": "currency", "direction": "decrease", "source": "crm_deals"},
        {"key": "follow_up_latency", "label": "Post-meeting follow-up latency", "unit": "minutes", "direction": "decrease", "source": "play_outcomes"},
        {"key": "stale_deal_rate", "label": "Stale deal rate", "unit": "percent", "direction": "decrease", "source": "crm_deals"},
        {"key": "recovery_opportunities", "label": "Recovery opportunities identified", "unit": "count", "direction": "increase", "source": "play_outcomes"},
        {"key": "revenue_automation_rate", "label": "Revenue operations automation rate", "unit": "percent", "direction": "increase", "source": "play_runs"},
        {"key": "hours_saved", "label": "Seller and RevOps hours saved", "unit": "hours", "direction": "increase", "source": "play_outcomes"},
    ]

    plays = [
        _play(
            "inbound-lead-qualifier", "Inbound Lead Qualifier",
            "Evaluate new CRM contacts against ICP, company fit, ownership, and available engagement evidence.",
            kpis=["speed_to_lead", "qualified_rate", "revenue_automation_rate"],
            outcome_event="inbound_lead_reviewed",
            trigger={"type": "event", "event": "crm.contact_created"},
            agent_seed="agent:revenue-lead-intelligence",
            evidence_steps=[
                _tool_step("lead-contact-search", "Search contact evidence", "hubspot.contacts.search", param_sources={"query": "$CONTACT_QUERY"}),
                _tool_step("lead-company-search", "Search company evidence", "hubspot.companies.search", param_sources={"query": "$COMPANY_QUERY"}),
            ],
            task="Score fit from available CRM evidence, explain the rationale, identify missing evidence, and recommend routing without inventing firmographic facts.",
        ),
        _play(
            "account-research-brief", "Account Research Brief",
            "Build a verified CRM-backed account brief covering company context, active deals, ownership, and known engagement.",
            kpis=["speed_to_lead", "deal_velocity", "hours_saved"],
            outcome_event="account_research_brief_prepared",
            trigger={"type": "manual"},
            agent_seed="agent:revenue-account-research",
            evidence_steps=[
                _tool_step("account-company", "Search company evidence", "hubspot.companies.search", param_sources={"query": "$COMPANY_QUERY"}),
                _tool_step("account-deals", "Search account deals", "hubspot.deals.search", param_sources={"query": "$DEAL_QUERY"}),
            ],
            task="Create an evidence-backed account brief and explicitly separate CRM facts from hypotheses or research gaps.",
        ),
        _play(
            "meeting-prep-brief", "Meeting Prep Brief",
            "Prepare a seller briefing from account, opportunity, owner, stage, and current CRM evidence before a customer meeting.",
            kpis=["deal_velocity", "hours_saved"],
            outcome_event="meeting_prep_completed",
            trigger={"type": "event", "event": "meeting.upcoming"},
            agent_seed="agent:revenue-meeting-intelligence",
            evidence_steps=[
                _tool_step("meeting-deal", "Fetch deal evidence", "hubspot.deals.get", param_sources={"deal_id": "$DEAL_ID"}),
                _tool_step("meeting-owner", "Load owner directory", "hubspot.owners.list"),
            ],
            task="Summarize the opportunity, current stage, known risks, unanswered questions, and desired meeting outcomes using only current CRM evidence.",
        ),
        _play(
            "post-meeting-follow-up", "Post-Meeting Follow-Up",
            "Prepare a concise follow-up package with decisions, open questions, CRM update recommendations, and next-step ownership.",
            kpis=["follow_up_latency", "deal_velocity", "hours_saved"],
            outcome_event="post_meeting_follow_up_prepared",
            trigger={"type": "event", "event": "meeting.completed"},
            agent_seed="agent:revenue-meeting-intelligence",
            evidence_steps=[
                _tool_step("follow-up-deal", "Fetch current deal evidence", "hubspot.deals.get", param_sources={"deal_id": "$DEAL_ID"}),
            ],
            approvals=[{"when": "send_external_message_or_crm_write", "required": True}],
            task="Prepare follow-up content and CRM change recommendations. Do not send messages or claim CRM fields changed; v1 is preparation-only.",
        ),
        _play(
            "stale-deal-recovery", "Stale Deal Recovery",
            "Identify opportunities with weak momentum, explain why they appear stalled, and prepare evidence-backed recovery options.",
            kpis=["stage_aging", "stale_deal_rate", "recovery_opportunities"],
            outcome_event="stale_deal_recovery_identified",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:revenue-pipeline-analyst",
            evidence_steps=[
                _tool_step("stale-deal-list", "Load active deals", "hubspot.deals.list"),
            ],
            task="Detect stage aging and weak momentum from CRM evidence, then propose the smallest credible recovery action.",
        ),
        _play(
            "pipeline-risk-review", "Pipeline Risk Review",
            "Detect pipeline concentration, weak stage progression, ownership gaps, and deals whose forecast posture is not supported by CRM evidence.",
            kpis=["pipeline_coverage", "stage_aging", "stale_deal_rate"],
            outcome_event="pipeline_risk_reviewed",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:revenue-pipeline-analyst",
            evidence_steps=[
                _tool_step("pipeline-deals", "Search pipeline deals", "hubspot.deals.search", param_sources={"query": "$PIPELINE_QUERY"}),
                _tool_step("pipeline-owners", "Load owner directory", "hubspot.owners.list"),
            ],
            task="Identify material pipeline risk and support every risk statement with CRM evidence or label it as an inference.",
        ),
        _play(
            "forecast-integrity-check", "Forecast Integrity Check",
            "Compare reported pipeline posture with stage distribution, deal state, and ownership evidence to find forecast integrity gaps.",
            kpis=["forecast_integrity", "pipeline_coverage", "deal_velocity"],
            outcome_event="forecast_integrity_reviewed",
            trigger={"type": "scheduled", "cadence": "weekly"},
            agent_seed="agent:revenue-forecast-analyst",
            evidence_steps=[
                _tool_step("forecast-pipelines", "Load pipeline definitions", "hubspot.pipelines.list"),
                _tool_step("forecast-deals", "Load deal evidence", "hubspot.deals.list"),
            ],
            task="Assess forecast integrity from current CRM evidence and surface unsupported assumptions, stale stages, and concentration risk.",
        ),
        _play(
            "renewal-expansion-watch", "Renewal & Expansion Watch",
            "Surface accounts that warrant renewal or expansion attention based on current company and opportunity evidence.",
            kpis=["renewal_risk", "recovery_opportunities", "hours_saved"],
            outcome_event="renewal_expansion_opportunity_reviewed",
            trigger={"type": "scheduled", "cadence": "daily"},
            agent_seed="agent:revenue-renewal-analyst",
            evidence_steps=[
                _tool_step("renewal-company", "Search account evidence", "hubspot.companies.search", param_sources={"query": "$COMPANY_QUERY"}),
                _tool_step("renewal-deals", "Load account deals", "hubspot.deals.list"),
            ],
            task="Identify renewal risk and expansion signals only when supported by CRM evidence. Never infer buying intent from absence of data.",
        ),
    ]

    skill_package = "revenue-operations-skills"
    skill_requirements = [
        "lead-qualification",
        "account-research",
        "meeting-prep",
        "pipeline-risk-analysis",
        "deal-recovery",
        "forecast-integrity",
        "renewal-expansion-analysis",
    ]

    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": "Revenue teams lose pipeline velocity when qualification, account context, meeting preparation, follow-up, deal recovery, forecasting, and renewal signals are fragmented.",
            "target_outcome": "Increase qualified pipeline velocity and forecast integrity while reducing manual seller and RevOps administration.",
            "baseline_metric": "deal_velocity",
            "success_criteria": [
                "All eight Plays install into Gravitre's canonical Play/workflow runtime.",
                "Every executable v1 action is a registered HubSpot source-of-record read.",
                "External messages and CRM mutations remain approval-gated preparation until a governed write path is explicitly declared.",
                "Every KPI resolves from the installed revenue dataset or verified Play outcomes.",
                "A measured declared outcome event is required before Outcome Verified status can be earned.",
            ],
            "outcome_events": [play["outcome_events"][0] for play in plays],
            "kpis": kpis,
            "verification_required": True,
        },
        "agents": [
            {"seed_label": "agent:revenue-lead-intelligence", "name": "Lead Intelligence Agent", "purpose": "Assess inbound lead fit, evidence quality, and routing readiness.", "role": "Lead Intelligence", "department": "Revenue Operations", "capabilities": ["lead-qualification"], "systems": ["hubspot", "salesforce", "apollo", "clay"]},
            {"seed_label": "agent:revenue-account-research", "name": "Account Research Agent", "purpose": "Assemble verified account and opportunity context for sellers.", "role": "Account Research", "department": "Revenue Operations", "capabilities": ["account-research"], "systems": ["hubspot", "salesforce", "gong"]},
            {"seed_label": "agent:revenue-meeting-intelligence", "name": "Meeting Intelligence Agent", "purpose": "Prepare meeting context and post-meeting follow-up recommendations.", "role": "Meeting Intelligence", "department": "Revenue Operations", "capabilities": ["meeting-prep"], "systems": ["hubspot", "gong", "microsoft_365"]},
            {"seed_label": "agent:revenue-pipeline-analyst", "name": "Pipeline Analyst", "purpose": "Find stale deals, concentration risk, and unsupported pipeline assumptions.", "role": "Pipeline Analysis", "department": "Revenue Operations", "capabilities": ["pipeline-risk-analysis", "deal-recovery"], "systems": ["hubspot", "salesforce"]},
            {"seed_label": "agent:revenue-forecast-analyst", "name": "Forecast Integrity Analyst", "purpose": "Assess whether forecast posture is supported by current CRM evidence.", "role": "Forecast Integrity", "department": "Revenue Operations", "capabilities": ["forecast-integrity"], "systems": ["hubspot", "salesforce"]},
            {"seed_label": "agent:revenue-renewal-analyst", "name": "Renewal & Expansion Analyst", "purpose": "Identify evidence-backed renewal risk and expansion opportunities.", "role": "Renewal & Expansion", "department": "Revenue Operations", "capabilities": ["renewal-expansion-analysis"], "systems": ["hubspot", "salesforce"]},
        ],
        "plays": plays,
        "knowledge": [
            {"seed_label": "revenue-icp", "title": "ICP & Qualification Standard", "type": "manual", "metadata": {"purpose": "Ideal customer profile, qualification, routing, and disqualification criteria."}},
            {"seed_label": "revenue-positioning", "title": "Positioning & Messaging", "type": "manual", "metadata": {"purpose": "Approved product positioning, differentiation, and messaging."}},
            {"seed_label": "revenue-sales-process", "title": "Sales Process & Stage Exit Criteria", "type": "manual", "metadata": {"purpose": "Pipeline stages, evidence requirements, and exit criteria."}},
            {"seed_label": "revenue-objections", "title": "Objection & Risk Library", "type": "manual", "metadata": {"purpose": "Known objections, deal-risk patterns, and response guidance."}},
            {"seed_label": "revenue-commercial", "title": "Pricing & Commercial Policy", "type": "manual", "metadata": {"purpose": "Approved pricing, discount, renewal, and escalation rules."}},
        ],
        "dataset": {
            "entities": [
                {"name": "crm_contacts", "source": "hubspot", "primary_key": "contact_id", "fields": ["contact_id", "company_id", "owner_id", "lifecycle_stage", "created_at", "updated_at"]},
                {"name": "crm_companies", "source": "hubspot", "primary_key": "company_id", "fields": ["company_id", "name", "owner_id", "industry", "created_at", "updated_at"]},
                {"name": "crm_deals", "source": "hubspot", "primary_key": "deal_id", "fields": ["deal_id", "company_id", "owner_id", "pipeline_id", "stage_id", "amount", "created_at", "stage_entered_at", "close_date", "updated_at"]},
                {"name": "crm_pipelines", "source": "hubspot", "primary_key": "pipeline_id", "fields": ["pipeline_id", "label", "stage_id", "stage_label", "probability"]},
                {"name": "crm_owners", "source": "hubspot", "primary_key": "owner_id", "fields": ["owner_id", "name", "team"]},
                {"name": "crm_activity", "source": "hubspot", "primary_key": "activity_id", "fields": ["activity_id", "record_id", "activity_type", "occurred_at"]},
                {"name": "play_outcomes", "source": "gravitre_verified_outcomes", "primary_key": "outcome_id", "fields": ["outcome_id", "play_key", "record_id", "status", "verified_at", "metric_delta"]},
            ],
            "metrics": [
                {"key": row["key"], "label": row["label"], "formula": f"verified_metric('{row['key']}')", "unit": row["unit"]}
                for row in kpis
            ],
        },
        "dashboard": {
            "title": "Revenue Operations Command Center",
            "refresh_mode": "event",
            "metrics": [
                {"kpi_key": row["key"], "label": row["label"], "visualization": "trend" if row["unit"] in {"minutes", "days", "percent", "ratio", "hours"} else "metric", "description": f"Marketplace 3.0 revenue KPI: {row['label']}."}
                for row in kpis
            ],
        },
        "skills": [skill_package],
        "skill_requirements": skill_requirements,
        "skill_bindings": {skill: skill_package for skill in skill_requirements},
        "runtime_profiles": [
            {
                "provider": "hubspot",
                "status": "tested",
                "actions": [
                    "hubspot.contacts.search",
                    "hubspot.companies.search",
                    "hubspot.deals.get",
                    "hubspot.deals.search",
                    "hubspot.deals.list",
                    "hubspot.owners.list",
                    "hubspot.pipelines.list",
                ],
            }
        ],
        "connector_alternatives": [
            ["hubspot"],
            ["salesforce"],
            ["gong"],
            ["apollo", "clay"],
        ],
    }
