"""Sales Outcome Pack.

Reuses the canonical pipeline metrics the Growth pack declares
(opportunities_created, deals_won, won_revenue, qualified_pipeline_value) and
adds sales-execution metrics. It also contributes Salesforce verification
recipes, so any pack's Play that writes to Salesforce is verified the same way
HubSpot writes are.
"""
from __future__ import annotations

from typing import Any

from app.outcome_packs.builders import approval_step, dashboard, play, runtime_profile_actions, tool_step

PACK_ID = "sales-pipeline"
DEPARTMENT = "sales"

KPIS: list[dict[str, Any]] = [
    {
        "key": "opportunities_created",
        "label": "Opportunities created",
        "description": "Deals that exist in the CRM and are open or won after the Play created or advanced them.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "sales",
        "source_system": "salesforce",
        "source_record_type": "opportunity",
        "verification_recipe": "salesforce-opportunity-progress",
    },
    {
        "key": "deals_won",
        "label": "Deals won",
        "description": "Deals whose CRM stage resolves to closed won.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "sales",
        "source_system": "salesforce",
        "source_record_type": "opportunity",
        "verification_recipe": "salesforce-opportunity-progress",
    },
    {
        "key": "won_revenue",
        "label": "Won revenue",
        "description": "Amount on closed-won deals the Play influenced, read from the CRM.",
        "unit": "currency",
        "direction": "increase",
        "kind": "business",
        "aggregation": "sum",
        "department": "sales",
        "source_system": "salesforce",
        "source_record_type": "opportunity",
        "verification_recipe": "salesforce-opportunity-progress",
    },
    {
        "key": "qualified_pipeline_value",
        "label": "Qualified pipeline value",
        "description": "Amount on open or won deals the Play created or advanced, read from the CRM.",
        "unit": "currency",
        "direction": "increase",
        "kind": "business",
        "aggregation": "sum",
        "department": "sales",
        "source_system": "salesforce",
        "source_record_type": "opportunity",
        "verification_recipe": "salesforce-opportunity-progress",
    },
    {
        "key": "sales_cycle_days",
        "label": "Sales cycle length",
        "description": "Days from deal creation to close on won deals the Play influenced.",
        "unit": "days",
        "direction": "decrease",
        "kind": "business",
        "aggregation": "avg",
        "department": "sales",
        "departments": ["sales", "executive"],
        "source_system": "hubspot",
        "source_record_type": "deal",
        "verification_recipe": "crm-deal-close-timing",
        "evidence_strategy": "Duration between the CRM deal create date and close date on won deals.",
        "synonyms": ["sales cycle", "time to close", "deal velocity", "cycle time"],
    },
    {
        "key": "average_deal_size",
        "label": "Average deal size",
        "description": "Average CRM amount on won deals the Play influenced.",
        "unit": "currency",
        "direction": "increase",
        "kind": "business",
        "aggregation": "avg",
        "department": "sales",
        "source_system": "hubspot",
        "source_record_type": "deal",
        "verification_recipe": "crm-deal-close-timing",
        "evidence_strategy": "Average CRM amount on deals whose stage resolves to closed won.",
        "synonyms": ["deal size", "acv", "average contract value"],
    },
    {
        "key": "win_rate",
        "label": "Win rate",
        "description": "Verified deals won divided by verified opportunities created.",
        "unit": "ratio",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "ratio",
        "numerator": "deals_won",
        "denominator": "opportunities_created",
        "department": "sales",
        "synonyms": [
            "win rate", "close rate", "conversion to won", "conversion to closed-won", "to closed-won",
            "to closed won", "opportunity to close", "opportunity-to-close", "win percentage",
        ],
    },
]

_SF_WON = {"field": "current.opportunity.IsWon", "op": "eq", "value": True}
_SF_LOST = {
    "all": [
        {"field": "current.opportunity.IsClosed", "op": "eq", "value": True},
        {"field": "current.opportunity.IsWon", "op": "eq", "value": False},
    ]
}
_SF_OPEN_OR_WON = {"any": [{"field": "current.opportunity.IsClosed", "op": "eq", "value": False}, _SF_WON]}

RECIPES: list[dict[str, Any]] = [
    {
        "key": "crm-deal-close-timing",
        "source_system": "hubspot",
        "record_type": "deal",
        "match_actions": ["hubspot.deals.create", "hubspot.deals.update", "hubspot.deals.update_stage"],
        "read_action": "hubspot.deals.get",
        "record_id_param": "deal_id",
        "record_id_fields": ["record_ids.deal", "deal_id", "entity_id", "id"],
        "read_params": {"include_evidence": True},
        "verification_method": "crm_deal_stage_reread",
        "measure_after_hours": 24,
        "measure_window_days": 120,
        "contributions": [
            {
                "metric_key": "sales_cycle_days",
                "when": {"field": "current.evidence.stage_outcome", "op": "eq", "value": "won"},
                "value": {"duration_from": "current.evidence.createdate", "duration_to": "current.evidence.closedate", "duration_unit": "days"},
                "baseline": {"const": 0},
            },
            {
                "metric_key": "average_deal_size",
                "when": {
                    "all": [
                        {"field": "current.evidence.stage_outcome", "op": "eq", "value": "won"},
                        {"field": "current.evidence.amount", "op": "exists"},
                    ]
                },
                "value": {"field": "current.evidence.amount"},
                "currency_field": "current.evidence.currency",
            },
        ],
    },
    {
        "key": "salesforce-opportunity-progress",
        "source_system": "salesforce",
        "record_type": "opportunity",
        "match_actions": [
            "salesforce.opportunities.create",
            "salesforce.opportunities.update",
            "salesforce.opportunities.update_stage",
        ],
        "read_action": "salesforce.opportunities.get",
        "record_id_param": "opportunity_id",
        "record_id_fields": ["record_ids.opportunity", "opportunity_id", "entity_id", "id"],
        "verification_method": "crm_opportunity_reread",
        "measure_after_hours": 24,
        "measure_window_days": 120,
        "contributions": [
            {"metric_key": "opportunities_created", "when": _SF_OPEN_OR_WON, "fail_when": _SF_LOST},
            {
                "metric_key": "qualified_pipeline_value",
                "when": {"all": [_SF_OPEN_OR_WON, {"field": "current.opportunity.Amount", "op": "exists"}]},
                "value": {"field": "current.opportunity.Amount"},
                "currency_field": "current.opportunity.CurrencyIsoCode",
            },
            {"metric_key": "deals_won", "when": _SF_WON, "fail_when": _SF_LOST},
            {
                "metric_key": "won_revenue",
                "when": {"all": [_SF_WON, {"field": "current.opportunity.Amount", "op": "exists"}]},
                "value": {"field": "current.opportunity.Amount"},
                "currency_field": "current.opportunity.CurrencyIsoCode",
            },
            {
                "metric_key": "sales_cycle_days",
                "when": _SF_WON,
                "value": {"duration_from": "current.opportunity.CreatedDate", "duration_to": "current.opportunity.CloseDate", "duration_unit": "days"},
            },
        ],
    },
]

_SEED_AE = "agent:sales-deal-coach"
_SEED_OPS = "agent:sales-ops-analyst"

PLAYS: list[dict[str, Any]] = [
    play(
        "stalled-deal-recovery",
        "Stalled Deal Recovery",
        "Find deals with no activity past their stage norm and restart them with a concrete next step.",
        objective="Move stalled pipeline toward closed won.",
        kpis=["deals_won", "won_revenue", "sales_cycle_days"],
        outcome_event="stalled_deal_restarted",
        trigger={"type": "scheduled", "cadence": "daily"},
        agent_seed=_SEED_AE,
        task="Rank stalled deals by value and age. For each, recommend one next step tied to deal evidence.",
        evidence_steps=[
            tool_step("read-stalled", "Read open pipeline", "capability.crm.pipeline.read", param_sources={"max_records": 2000}),
        ],
        action_steps_after=[
            approval_step("approve-next-step", "Approve deal next step", "Updates the deal"),
            tool_step("update-deal", "Record the next step on the deal", "capability.crm.deal.update",
                      param_sources={"deal_id": "$DEAL_ID", "properties": "$DEAL_PROPERTIES"}),
        ],
        capability_groups=[["crm.pipeline.read"], ["crm.deal.update"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        write_actions=[{"capability": "crm.deal.update", "approval": "always"}],
    ),
    play(
        "deal-risk-review",
        "Deal Risk Review",
        "Flag late-stage deals with missing champions, dates or next steps before they slip.",
        objective="Protect committed pipeline from slipping.",
        kpis=["win_rate", "deals_won"],
        outcome_event="deal_risk_flagged",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_OPS,
        task="Score each late-stage deal for risk with evidence and create a seller task for the top risks.",
        evidence_steps=[
            tool_step("read-late-stage", "Read late-stage deals", "capability.crm.pipeline.read", param_sources={"max_records": 2000}),
        ],
        action_steps_after=[
            tool_step("risk-task", "Create risk follow-up task", "capability.crm.task.create",
                      param_sources={"deal_id": "$DEAL_ID", "body": "$RISK_NOTE"}),
        ],
        approvals=[{"when": "capability.crm.task.create", "required": True}],
        capability_groups=[["crm.pipeline.read"], ["crm.task.create"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        write_actions=[{"capability": "crm.task.create", "approval": "policy"}],
    ),
    play(
        "multi-thread-buying-committee",
        "Multi-thread the Buying Committee",
        "Add verified stakeholders to single-threaded deals.",
        objective="Raise win rate by engaging more of the buying committee.",
        kpis=["win_rate", "deals_won"],
        outcome_event="stakeholders_added",
        trigger={"type": "event", "event": "crm.deal.single_threaded"},
        agent_seed=_SEED_AE,
        task="Identify missing roles in the buying committee and verify each stakeholder from sourced data.",
        evidence_steps=[
            tool_step("read-deal", "Read the deal", "capability.crm.deal.read", param_sources={"deal_id": "$DEAL_ID"}),
            tool_step("find-stakeholders", "Find stakeholders", "capability.prospect.discovery",
                      param_sources={"organization_domains": "$ACCOUNT_DOMAIN", "query": "$ROLES"}),
        ],
        action_steps_after=[
            approval_step("approve-stakeholders", "Approve stakeholders", "Creates CRM contacts"),
            tool_step("add-stakeholders", "Add stakeholders to the CRM", "capability.crm.contact.create",
                      param_sources={"properties": "$CONTACT_PROPERTIES"}),
        ],
        capability_groups=[["crm.deal.read"], ["prospect.discovery"], ["crm.contact.create"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        optional_connectors=["apollo", "pdl", "clay"],
        write_actions=[{"capability": "crm.contact.create", "approval": "always"}],
    ),
    play(
        "forecast-hygiene",
        "Forecast Hygiene",
        "Fix deals with stale close dates, missing amounts or wrong stages so pipeline numbers are trustworthy.",
        objective="Keep pipeline value accurate.",
        kpis=["qualified_pipeline_value", "opportunities_created"],
        outcome_event="forecast_cleaned",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_OPS,
        task="List deals with data problems and propose exact field corrections with the evidence for each.",
        evidence_steps=[
            tool_step("read-forecast", "Read pipeline for hygiene", "capability.crm.pipeline.read", param_sources={"max_records": 2000}),
        ],
        action_steps_after=[
            approval_step("approve-corrections", "Approve field corrections", "Updates CRM deals"),
            tool_step("fix-deal", "Apply the approved correction", "capability.crm.deal.update",
                      param_sources={"deal_id": "$DEAL_ID", "properties": "$DEAL_PROPERTIES"}),
        ],
        capability_groups=[["crm.pipeline.read"], ["crm.deal.update"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        write_actions=[{"capability": "crm.deal.update", "approval": "always"}],
    ),
    play(
        "meeting-next-step-coach",
        "Meeting Next-Step Coach",
        "After each sales meeting, propose and log the agreed next step and mutual close plan.",
        objective="Shorten the sales cycle with consistent next steps.",
        kpis=["sales_cycle_days", "win_rate"],
        outcome_event="next_step_logged",
        trigger={"type": "event", "event": "crm.meeting.completed"},
        agent_seed=_SEED_AE,
        task="Summarize the meeting, propose the next step and owner, and draft the seller's follow-up note.",
        evidence_steps=[
            tool_step("read-meeting", "Read the meeting", "capability.crm.meeting.read", param_sources={"deal_id": "$DEAL_ID"}),
        ],
        action_steps_after=[
            tool_step("log-next-step", "Log the next step", "capability.crm.task.create",
                      param_sources={"deal_id": "$DEAL_ID", "body": "$NEXT_STEP_NOTE"}),
        ],
        approvals=[{"when": "capability.crm.task.create", "required": True}],
        capability_groups=[["crm.meeting.read"], ["crm.task.create"]],
        required_connector_groups=[["hubspot"]],
        write_actions=[{"capability": "crm.task.create", "approval": "policy"}],
    ),
    play(
        "win-loss-review",
        "Win/Loss Review",
        "Explain recent wins and losses from CRM evidence and recommend changes to the sales motion.",
        objective="Raise win rate and deal size by learning from closed deals.",
        kpis=["win_rate", "average_deal_size"],
        outcome_event="win_loss_reviewed",
        trigger={"type": "scheduled", "cadence": "monthly"},
        agent_seed=_SEED_OPS,
        task="Group closed deals by outcome and cause using CRM evidence only. Recommend at most three changes.",
        evidence_steps=[
            tool_step("read-closed", "Read closed deals", "capability.crm.pipeline.read", param_sources={"max_records": 2000}),
        ],
        capability_groups=[["crm.pipeline.read"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
    ),
]


def build() -> dict[str, Any]:
    config: dict[str, Any] = {
        "marketplace_version": "3.0",
        "pack_id": PACK_ID,
        "department": DEPARTMENT,
        "outcome_contract": {
            "problem": "Sellers lose deals to stalls, single-threading and stale data that nobody sees in time.",
            "target_outcome": "Win more verified revenue faster, measured from the CRM.",
            "baseline_metric": "won_revenue",
            "success_criteria": [
                "Deal outcomes are resolved from CRM pipeline metadata, not stage names.",
                "HubSpot and Salesforce writes are verified by the same generic engine.",
            ],
            "outcome_events": sorted({p["outcome_events"][0] for p in PLAYS}),
            "kpis": KPIS,
            "verification_required": True,
        },
        "objectives": [
            {"key": "win-more-revenue", "statement": "Close more revenue", "kpi_keys": ["won_revenue", "deals_won"]},
            {"key": "shorten-sales-cycle", "statement": "Shorten the sales cycle", "kpi_keys": ["sales_cycle_days"]},
        ],
        "agents": [
            {"seed_label": _SEED_AE, "name": "Deal Coach", "purpose": "Restart stalled deals and coach next steps.",
             "role": "Account Executive Support", "department": "Sales",
             "capabilities": ["deal-coaching", "next-steps"], "systems": ["hubspot", "salesforce", "pipedrive"]},
            {"seed_label": _SEED_OPS, "name": "Sales Ops Analyst", "purpose": "Keep pipeline accurate and learn from closed deals.",
             "role": "Sales Operations", "department": "Sales",
             "capabilities": ["forecasting", "pipeline-hygiene", "win-loss"], "systems": ["hubspot", "salesforce", "pipedrive"]},
        ],
        "plays": PLAYS,
        "knowledge": [
            {"seed_label": "sales-methodology", "title": "Sales Methodology and Stage Exit Criteria", "type": "manual",
             "metadata": {"purpose": "Stage definitions, exit criteria and qualification framework."}},
        ],
        "dataset": {
            "entities": [
                {"name": "crm_deals", "source": "crm_connector", "primary_key": "deal_id",
                 "fields": ["deal_id", "stage", "amount", "currency", "createdate", "closedate"]},
            ],
            "metrics": [
                {"key": row["key"], "label": row["label"], "formula": row["description"], "unit": row["unit"]}
                for row in KPIS
            ],
        },
        "dashboard": dashboard(
            title="Sales Results",
            template_id="sales-results",
            department=DEPARTMENT,
            kpis=KPIS,
            sections=[
                {"title": "Revenue", "kpi_keys": ["won_revenue", "deals_won", "average_deal_size"]},
                {"title": "Pipeline", "kpi_keys": ["opportunities_created", "qualified_pipeline_value", "win_rate"]},
                {"title": "Velocity", "kpi_keys": ["sales_cycle_days"]},
            ],
            system_health_kpis=["pending-approvals"],
        ),
        "runtime_profiles": [
            {"provider": "capability-resolved", "status": "tested", "actions": runtime_profile_actions(PLAYS)}
        ],
        "connector_alternatives": [["hubspot", "salesforce", "pipedrive"]],
        "verification_recipes": RECIPES,
        "governance": {
            "always_approve_actions": ["hubspot.contacts.create", "salesforce.leads.create"],
            "max_autonomy": "act_with_approval",
        },
        "certification": {
            "minimum_plays": 6,
            "fixtures": {
                "crm-deal-close-timing": {
                    "record_id": "deal-7",
                    "current": {"evidence": {"stage_outcome": "won", "amount": 18000.0, "currency": "USD",
                                             "createdate": "2026-08-01T00:00:00Z", "closedate": "2026-09-10T00:00:00Z"}},
                },
                "salesforce-opportunity-progress": {
                    "record_id": "006A",
                    "current": {"opportunity": {"IsWon": True, "IsClosed": True, "Amount": 32000, "CurrencyIsoCode": "USD",
                                                "CreatedDate": "2026-07-01T00:00:00Z", "CloseDate": "2026-09-01"}},
                },
            },
            "degraded_scenarios": [
                {"capability": "prospect.discovery", "unavailable_vendor": "apollo", "reason": "plan_limit"},
            ],
        },
    }
    return {
        "marketplace": {
            "slug": "sales-pipeline-operator",
            "title": "Sales Results Operator",
            "description": "Win more verified revenue faster with six deal-execution Plays verified in your CRM.",
            "department_label": "Sales",
            "tags": ["sales", "pipeline", "outcome-pack"],
            "price_cents": 0,
            "pricing_type": "free",
            "required_connectors": [
                {"connectorType": "hubspot", "label": "HubSpot or Salesforce", "required": True,
                 "connectPath": "/connectors?type=hubspot",
                 "requirementNote": "Any supported CRM is the source of record for deals."},
            ],
            "business_outcome": "Win more verified revenue with a shorter sales cycle.",
            "use_case": "Sales execution",
            "estimated_hours_saved": 20.0,
        },
        "config": config,
    }
