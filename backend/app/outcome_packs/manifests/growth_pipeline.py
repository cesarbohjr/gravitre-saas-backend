"""Growth Pipeline Operator: the reference Outcome Pack.

Everything Growth-specific lives here as declarations: canonical metrics,
source-of-record verification recipes, Plays with provider-alternative
capability groups, attribution, dashboard, governance and certification
fixtures. The runtime that executes, verifies, measures and reports this pack
is the same one every other pack uses.
"""
from __future__ import annotations

from typing import Any

from app.outcome_packs.builders import (
    approval_step,
    dashboard,
    play,
    runtime_profile_actions,
    tool_step,
)

PACK_ID = "growth-pipeline"
DEPARTMENT = "growth"

_SQL_STAGES = ["salesqualifiedlead", "opportunity", "customer"]
_MQL_STAGES = ["marketingqualifiedlead", *_SQL_STAGES]

KPIS: list[dict[str, Any]] = [
    {
        "key": "accounts_qualified",
        "label": "ICP accounts qualified",
        "description": "Target accounts whose CRM record shows an ICP fit score of at least 0.7.",
        "unit": "count",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "count",
        "department": "growth",
        "departments": ["marketing", "sales"],
        "source_system": "hubspot",
        "source_record_type": "company",
        "verification_recipe": "crm-company-qualification",
        "evidence_strategy": "Re-read the company in the CRM and check the persisted ICP fit score.",
        "synonyms": ["qualified accounts", "icp accounts", "target accounts"],
        "definition_prompt": "An account counts once the CRM shows an ICP fit score of 0.7 or higher.",
    },
    {
        "key": "mql",
        "label": "Marketing qualified leads",
        "description": "Contacts whose CRM lifecycle stage reached Marketing Qualified Lead or later.",
        "unit": "count",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "count",
        "department": "marketing",
        "departments": ["marketing", "growth"],
        "source_system": "hubspot",
        "source_record_type": "contact",
        "verification_recipe": "crm-contact-lifecycle",
        "formula": "count(contacts where lifecyclestage >= marketingqualifiedlead)",
        "evidence_strategy": "Re-read the contact's lifecycle stage in the CRM after the Play acted.",
        "synonyms": ["mqls", "marketing qualified leads", "marketing leads"],
        "definition_prompt": "A lead counts as marketing qualified when the CRM lifecycle stage is MQL or later.",
    },
    {
        "key": "qualified_leads",
        "label": "Qualified leads",
        "description": "Contacts whose CRM lifecycle stage reached Sales Qualified Lead or later.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "growth",
        "departments": ["marketing", "sales"],
        "source_system": "hubspot",
        "source_record_type": "contact",
        "verification_recipe": "crm-contact-lifecycle",
        "formula": "count(contacts where lifecyclestage in (salesqualifiedlead, opportunity, customer))",
        "evidence_strategy": (
            "Re-read each contact the Play touched; it counts only when the CRM lifecycle "
            "stage is Sales Qualified Lead or later inside the measurement window."
        ),
        "synonyms": [
            "qualified leads", "sales qualified leads", "sqls", "sql", "leads",
            "qualified prospects", "new qualified leads", "pipeline leads",
        ],
        "definition_prompt": (
            "I'll count a lead as qualified when HubSpot shows its lifecycle stage as Sales "
            "Qualified Lead or later. Tell me if your team uses a different definition."
        ),
        "learning": {"improved_event": "business_metric_improved", "declined_event": "business_metric_declined"},
    },
    {
        "key": "outreach_delivered",
        "label": "Prospects reached",
        "description": "Prospects with at least one delivered outreach email recorded in the CRM.",
        "unit": "count",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "count",
        "department": "growth",
        "departments": ["marketing", "sales"],
        "source_system": "hubspot",
        "source_record_type": "contact_outreach",
        "verification_recipe": "crm-contact-outreach",
        "evidence_strategy": "Count delivered email engagements on the contact after enrollment.",
        "synonyms": ["emails delivered", "prospects contacted", "outreach sent"],
    },
    {
        "key": "replies",
        "label": "Prospect replies",
        "description": "Prospects who replied by email after outreach, as recorded in the CRM.",
        "unit": "count",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "count",
        "department": "growth",
        "departments": ["marketing", "sales"],
        "source_system": "hubspot",
        "source_record_type": "contact_outreach",
        "verification_recipe": "crm-contact-outreach",
        "evidence_strategy": "Count inbound email engagements on the contact after enrollment.",
        "synonyms": ["replies", "responses", "email replies"],
    },
    {
        "key": "reply_rate",
        "label": "Reply rate",
        "description": "Verified replies divided by verified prospects reached.",
        "unit": "ratio",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "ratio",
        "numerator": "replies",
        "denominator": "outreach_delivered",
        "department": "growth",
        "departments": ["marketing", "sales"],
        "synonyms": ["reply rate", "response rate"],
    },
    {
        "key": "meetings_booked",
        "label": "Meetings booked",
        "description": "Prospects with a meeting booked in the CRM after the Play engaged them.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "growth",
        "departments": ["marketing", "sales"],
        "source_system": "hubspot",
        "source_record_type": "contact_meetings",
        "verification_recipe": "crm-contact-meetings",
        "evidence_strategy": "Search CRM meetings associated with the contact that start after the Play acted.",
        "synonyms": ["meetings", "meetings booked", "demos booked", "sales meetings", "appointments"],
        "definition_prompt": "A meeting counts when the CRM shows a meeting with the prospect after outreach.",
    },
    {
        "key": "lead_to_meeting_conversion",
        "label": "Lead to meeting conversion",
        "description": "Verified meetings booked divided by verified qualified leads.",
        "unit": "ratio",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "ratio",
        "numerator": "meetings_booked",
        "denominator": "qualified_leads",
        "department": "growth",
        "departments": ["marketing", "sales"],
        "synonyms": ["lead to meeting rate"],
    },
    {
        "key": "opportunities_created",
        "label": "Opportunities created",
        "description": "Deals that exist in the CRM and are open or won after the Play created or advanced them.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "sales",
        "departments": ["sales", "growth"],
        "source_system": "hubspot",
        "source_record_type": "deal",
        "verification_recipe": "crm-deal-progress",
        "evidence_strategy": "Re-read the deal and resolve its stage outcome from pipeline metadata.",
        "synonyms": ["opportunities", "deals created", "new deals", "opps"],
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
        "departments": ["sales", "growth"],
        "source_system": "hubspot",
        "source_record_type": "deal",
        "verification_recipe": "crm-deal-progress",
        "evidence_strategy": "Sum the CRM deal amount; deals without an amount are reported, never counted as zero.",
        "synonyms": ["pipeline", "pipeline value", "qualified pipeline", "pipeline generated"],
    },
    {
        "key": "meeting_to_opportunity_conversion",
        "label": "Meeting to opportunity conversion",
        "description": "Verified opportunities created divided by verified meetings booked.",
        "unit": "ratio",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "ratio",
        "numerator": "opportunities_created",
        "denominator": "meetings_booked",
        "department": "growth",
        "departments": ["sales"],
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
        "departments": ["sales", "growth"],
        "source_system": "hubspot",
        "source_record_type": "deal",
        "verification_recipe": "crm-deal-progress",
        "evidence_strategy": "Closed won is resolved from pipeline stage metadata, not stage names.",
        "synonyms": ["deals won", "wins", "closed won", "new customers"],
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
        "departments": ["sales", "growth", "executive"],
        "source_system": "hubspot",
        "source_record_type": "deal",
        "verification_recipe": "crm-deal-progress",
        "evidence_strategy": "Sum CRM amount on deals whose stage resolves to closed won.",
        "synonyms": ["revenue", "won revenue", "closed revenue", "bookings", "new revenue"],
    },
    {
        "key": "opportunity_to_won_conversion",
        "label": "Opportunity to won conversion",
        "description": "Verified deals won divided by verified opportunities created.",
        "unit": "ratio",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "ratio",
        "numerator": "deals_won",
        "denominator": "opportunities_created",
        "department": "sales",
        "departments": ["sales", "growth"],
        "synonyms": ["win rate", "close rate"],
    },
]

RECIPES: list[dict[str, Any]] = [
    {
        "key": "crm-company-qualification",
        "source_system": "hubspot",
        "record_type": "company",
        "match_actions": ["hubspot.companies.update", "hubspot.companies.create"],
        "read_action": "hubspot.companies.get",
        "record_id_param": "company_id",
        "record_id_fields": ["record_ids.company", "entity_id", "company_id", "id"],
        "read_params": {"include_evidence": True},
        "verification_method": "crm_company_reread",
        "measure_after_hours": 0,
        "measure_window_days": 14,
        "contributions": [
            {
                "metric_key": "accounts_qualified",
                "when": {"field": "current.evidence.icp_fit", "op": "gte", "value": 0.7},
                "fail_when": {"field": "current.evidence.icp_fit", "op": "lt", "value": 0.7},
            }
        ],
    },
    {
        "key": "crm-contact-lifecycle",
        "source_system": "hubspot",
        "record_type": "contact",
        "match_actions": [
            "hubspot.contacts.create",
            "hubspot.contacts.update",
            "hubspot.sequences.enroll",
            "hubspot.lists.add_contact",
        ],
        "read_action": "hubspot.contacts.get",
        "record_id_param": "contact_id",
        "record_id_fields": ["record_ids.contact", "contact_id", "entity_id", "id"],
        "read_params": {"include_evidence": True},
        "verification_method": "crm_lifecycle_reread",
        "measure_after_hours": 24,
        "measure_window_days": 45,
        "contributions": [
            {
                "metric_key": "mql",
                "when": {"field": "current.evidence.lifecyclestage", "op": "in", "value": _MQL_STAGES},
            },
            {
                "metric_key": "qualified_leads",
                "when": {"field": "current.evidence.lifecyclestage", "op": "in", "value": _SQL_STAGES},
            },
        ],
    },
    {
        "key": "crm-contact-outreach",
        "source_system": "hubspot",
        "record_type": "contact_outreach",
        "match_actions": ["hubspot.sequences.enroll"],
        "read_action": "hubspot.contacts.outreach",
        "record_id_param": "contact_id",
        "record_id_fields": ["record_ids.contact", "contact_id", "entity_id", "id"],
        "read_params": {"since": "{window_start}"},
        "verification_method": "crm_email_engagement_reread",
        "measure_after_hours": 24,
        "measure_window_days": 21,
        "contributions": [
            {
                "metric_key": "outreach_delivered",
                "when": {"field": "current.evidence.delivered_count", "op": "gte", "value": 1},
            },
            {
                "metric_key": "replies",
                "when": {"field": "current.evidence.reply_count", "op": "gte", "value": 1},
            },
        ],
    },
    {
        "key": "crm-contact-meetings",
        "source_system": "hubspot",
        "record_type": "contact_meetings",
        "match_actions": ["hubspot.sequences.enroll", "hubspot.notes.create", "hubspot.contacts.update"],
        "read_action": "hubspot.meetings.search",
        "record_id_param": "contact_id",
        "record_id_fields": ["record_ids.contact", "contact_id", "entity_id"],
        "read_params": {"since_ms": "{window_start_ms}", "max_records": 20},
        "verification_method": "crm_meeting_search",
        "measure_after_hours": 24,
        "measure_window_days": 30,
        "contributions": [
            {
                "metric_key": "meetings_booked",
                "when": {"field": "current.meetings.0.id", "op": "exists"},
            }
        ],
    },
    {
        "key": "crm-deal-progress",
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
                "metric_key": "opportunities_created",
                "when": {"field": "current.evidence.stage_outcome", "op": "in", "value": ["open", "won"]},
                "fail_when": {"field": "current.evidence.stage_outcome", "op": "eq", "value": "lost"},
            },
            {
                "metric_key": "qualified_pipeline_value",
                "when": {
                    "all": [
                        {"field": "current.evidence.stage_outcome", "op": "in", "value": ["open", "won"]},
                        {"field": "current.evidence.amount", "op": "exists"},
                    ]
                },
                "value": {"field": "current.evidence.amount"},
                "currency_field": "current.evidence.currency",
            },
            {
                "metric_key": "deals_won",
                "when": {"field": "current.evidence.stage_outcome", "op": "eq", "value": "won"},
                "fail_when": {"field": "current.evidence.stage_outcome", "op": "eq", "value": "lost"},
            },
            {
                "metric_key": "won_revenue",
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
]

_SEED_STRATEGIST = "agent:growth-strategist"
_SEED_RESEARCHER = "agent:growth-researcher"
_SEED_SDR = "agent:growth-sdr"

PLAYS: list[dict[str, Any]] = [
    play(
        "icp-account-discovery",
        "ICP Account Discovery",
        "Find accounts that match the ideal customer profile and record a fit score on the CRM account.",
        objective="Grow the number of verified ICP accounts in the CRM.",
        kpis=["accounts_qualified"],
        outcome_event="accounts_qualified",
        trigger={"type": "objective", "metric": "accounts_qualified"},
        agent_seed=_SEED_RESEARCHER,
        task=(
            "Score each discovered account against the ICP using only sourced evidence. Prepare a fit "
            "score and reasons for approval; never invent firmographics."
        ),
        evidence_steps=[
            tool_step(
                "discover-accounts",
                "Discover ICP accounts",
                "capability.company.discovery",
                param_sources={"query": "$ICP_QUERY"},
            ),
        ],
        action_steps_after=[
            approval_step("approve-account-scores", "Approve account fit scores", "Writes ICP fit to CRM accounts"),
            tool_step(
                "write-account-fit",
                "Record ICP fit on the CRM account",
                "capability.crm.company.update",
                param_sources={"company_id": "$COMPANY_ID", "properties": "$FIT_PROPERTIES"},
            ),
        ],
        capability_groups=[["company.discovery"], ["crm.company.update"]],
        required_connector_groups=[["hubspot", "salesforce"]],
        optional_connectors=["apollo", "pdl", "clay"],
        write_actions=[{"capability": "crm.company.update", "approval": "always"}],
    ),
    play(
        "decision-maker-discovery",
        "Decision Maker Discovery",
        "Find and verify the buying committee at qualified accounts and add them to the CRM.",
        objective="Turn qualified accounts into verified, reachable prospects in the CRM.",
        kpis=["mql", "qualified_leads"],
        outcome_event="prospects_added",
        trigger={"type": "objective", "metric": "qualified_leads"},
        agent_seed=_SEED_RESEARCHER,
        task=(
            "Identify decision makers for the target persona, verify role and company from the sourced "
            "record, and drop anyone without verifiable evidence."
        ),
        evidence_steps=[
            tool_step(
                "discover-people",
                "Discover decision makers",
                "capability.prospect.discovery",
                param_sources={"query": "$PERSONA_QUERY", "organization_domains": "$TARGET_DOMAINS"},
            ),
            tool_step(
                "enrich-people",
                "Verify and enrich prospects",
                "capability.prospect.enrichment",
                param_sources={"people": "$PROSPECTS"},
            ),
        ],
        action_steps_after=[
            approval_step("approve-prospects", "Approve prospects for the CRM", "Creates CRM contacts"),
            tool_step(
                "create-crm-prospects",
                "Add verified prospects to the CRM",
                "capability.crm.contact.create",
                param_sources={"properties": "$CONTACT_PROPERTIES"},
            ),
        ],
        capability_groups=[["prospect.discovery"], ["prospect.enrichment"], ["crm.contact.create"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        optional_connectors=["apollo", "pdl", "clay", "linkedin"],
        write_actions=[{"capability": "crm.contact.create", "approval": "always"}],
    ),
    play(
        "inbound-lead-qualification",
        "Inbound Lead Qualification",
        "Qualify new inbound contacts against the ICP and advance qualified ones in the CRM lifecycle.",
        objective="Convert inbound demand into sales qualified leads quickly and consistently.",
        kpis=["mql", "qualified_leads"],
        outcome_event="lead_qualified",
        trigger={"type": "event", "event": "crm.contact.created"},
        agent_seed=_SEED_SDR,
        task=(
            "Qualify the contact from CRM and enrichment evidence. Recommend a lifecycle change only "
            "when the evidence meets the org's qualification definition."
        ),
        evidence_steps=[
            tool_step(
                "read-lead",
                "Read the inbound lead",
                "capability.crm.contact.read",
                param_sources={"contact_id": "$CONTACT_ID"},
            ),
            tool_step(
                "enrich-lead",
                "Enrich the inbound lead",
                "capability.prospect.enrichment",
                param_sources={"email": "$CONTACT_EMAIL"},
            ),
        ],
        action_steps_after=[
            tool_step(
                "advance-lifecycle",
                "Advance the lead's lifecycle stage",
                "capability.crm.contact.update",
                param_sources={"contact_id": "$CONTACT_ID", "properties": "$LIFECYCLE_PROPERTIES"},
            ),
        ],
        approvals=[{"when": "capability.crm.contact.update", "required": True}],
        capability_groups=[["crm.contact.read"], ["prospect.enrichment"], ["crm.contact.update"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        optional_connectors=["apollo", "pdl", "clay"],
        write_actions=[{"capability": "crm.contact.update", "approval": "policy"}],
    ),
    play(
        "outbound-sequence-launch",
        "Outbound Sequence Launch",
        "Enroll approved prospects in a personalized outreach sequence and track delivery and replies.",
        objective="Reach verified prospects and start conversations.",
        kpis=["outreach_delivered", "replies", "reply_rate", "meetings_booked", "qualified_leads"],
        outcome_event="outreach_enrolled",
        trigger={"type": "objective", "metric": "meetings_booked"},
        agent_seed=_SEED_SDR,
        task=(
            "Draft concise, evidence-based personalization for each prospect. Every enrollment sends real "
            "email and needs approval."
        ),
        evidence_steps=[
            tool_step(
                "read-prospect",
                "Read prospect context",
                "capability.crm.contact.read",
                param_sources={"contact_id": "$CONTACT_ID"},
            ),
        ],
        action_steps_after=[
            approval_step("approve-outreach", "Approve outreach", "Sends email to prospects"),
            tool_step(
                "enroll-sequence",
                "Enroll in outreach sequence",
                "capability.outreach.sequence.enroll",
                param_sources={"contact_id": "$CONTACT_ID", "sequence_id": "$SEQUENCE_ID", "sender_email": "$SENDER_EMAIL"},
            ),
        ],
        capability_groups=[["crm.contact.read"], ["outreach.sequence.enroll"]],
        required_connector_groups=[["hubspot", "apollo"]],
        write_actions=[{"capability": "outreach.sequence.enroll", "approval": "always"}],
    ),
    play(
        "reply-to-meeting",
        "Reply to Meeting",
        "Turn positive replies into booked meetings with fast, context-aware seller follow-up.",
        objective="Convert replies into booked meetings.",
        kpis=["meetings_booked", "lead_to_meeting_conversion"],
        outcome_event="meeting_follow_up_prepared",
        trigger={"type": "event", "event": "crm.email.reply"},
        agent_seed=_SEED_SDR,
        task=(
            "Classify each reply, draft the follow-up and create a seller task. Count a meeting only when "
            "the CRM shows it."
        ),
        evidence_steps=[
            tool_step(
                "read-replies",
                "Read outreach replies",
                "capability.outreach.activity.read",
                param_sources={"contact_id": "$CONTACT_ID"},
            ),
            tool_step(
                "read-meetings",
                "Read booked meetings",
                "capability.crm.meeting.read",
                param_sources={"contact_id": "$CONTACT_ID"},
            ),
        ],
        action_steps_after=[
            tool_step(
                "create-follow-up",
                "Create seller follow-up",
                "capability.crm.task.create",
                param_sources={"contact_id": "$CONTACT_ID", "body": "$FOLLOW_UP_NOTE"},
            ),
        ],
        approvals=[{"when": "capability.crm.task.create", "required": True}],
        capability_groups=[["outreach.activity.read"], ["crm.meeting.read"], ["crm.task.create"]],
        required_connector_groups=[["hubspot"]],
        write_actions=[{"capability": "crm.task.create", "approval": "policy"}],
    ),
    play(
        "meeting-to-opportunity",
        "Meeting to Opportunity",
        "Create a qualified opportunity in the CRM after a held meeting with a qualified buyer.",
        objective="Convert meetings into qualified pipeline.",
        kpis=["opportunities_created", "qualified_pipeline_value", "meeting_to_opportunity_conversion"],
        outcome_event="opportunity_created",
        trigger={"type": "event", "event": "crm.meeting.completed"},
        agent_seed=_SEED_STRATEGIST,
        task=(
            "Summarize the meeting evidence, propose deal name, amount and stage with reasons, and flag "
            "missing qualification data."
        ),
        evidence_steps=[
            tool_step(
                "read-meeting-context",
                "Read meeting context",
                "capability.crm.meeting.read",
                param_sources={"contact_id": "$CONTACT_ID"},
            ),
        ],
        action_steps_after=[
            approval_step("approve-opportunity", "Approve opportunity", "Creates a CRM deal"),
            tool_step(
                "create-opportunity",
                "Create the opportunity",
                "capability.crm.deal.create",
                param_sources={"properties": "$DEAL_PROPERTIES"},
            ),
        ],
        capability_groups=[["crm.meeting.read"], ["crm.deal.create"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        write_actions=[{"capability": "crm.deal.create", "approval": "always"}],
    ),
    play(
        "pipeline-progression",
        "Pipeline Progression",
        "Find stalled opportunities and coordinate the next best action to move them to closed won.",
        objective="Convert open pipeline into won revenue.",
        kpis=["deals_won", "won_revenue", "opportunity_to_won_conversion", "qualified_pipeline_value"],
        outcome_event="pipeline_progressed",
        trigger={"type": "scheduled", "cadence": "daily"},
        agent_seed=_SEED_STRATEGIST,
        task=(
            "Rank stalled deals by value and risk, recommend the next action with evidence, and propose a "
            "stage update only when the CRM evidence supports it."
        ),
        evidence_steps=[
            tool_step(
                "read-pipeline",
                "Read open pipeline",
                "capability.crm.pipeline.read",
                param_sources={"max_records": 2000},
            ),
        ],
        action_steps_after=[
            approval_step("approve-stage-change", "Approve stage change", "Updates a CRM deal"),
            tool_step(
                "advance-deal",
                "Advance the deal",
                "capability.crm.deal.update",
                param_sources={"deal_id": "$DEAL_ID", "properties": "$DEAL_PROPERTIES"},
            ),
        ],
        capability_groups=[["crm.pipeline.read"], ["crm.deal.update"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        write_actions=[{"capability": "crm.deal.update", "approval": "always"}],
    ),
]


def _fixtures() -> dict[str, Any]:
    return {
        "crm-company-qualification": {
            "record_id": "company-1",
            "current": {"evidence": {"record_id": "company-1", "icp_fit": 0.82}},
        },
        "crm-contact-lifecycle": {
            "record_id": "contact-1",
            "current": {"evidence": {"record_id": "contact-1", "lifecyclestage": "salesqualifiedlead"}},
        },
        "crm-contact-outreach": {
            "record_id": "contact-1",
            "current": {"evidence": {"delivered_count": 2, "reply_count": 1}},
        },
        "crm-contact-meetings": {
            "record_id": "contact-1",
            "current": {"meetings": [{"id": "meeting-1"}], "total": 1},
        },
        "crm-deal-progress": {
            "record_id": "deal-1",
            "current": {"evidence": {"stage_outcome": "won", "amount": 24000.0, "currency": "USD"}},
        },
    }


def build() -> dict[str, Any]:
    config: dict[str, Any] = {
        "marketplace_version": "3.0",
        "pack_id": PACK_ID,
        "department": DEPARTMENT,
        "outcome_contract": {
            "problem": (
                "Growth teams spend capacity on prospecting, outreach and follow-up without knowing which "
                "work produces qualified leads, meetings, pipeline and revenue."
            ),
            "target_outcome": (
                "Grow verified qualified leads, meetings, pipeline and won revenue, measured from the CRM."
            ),
            "baseline_metric": "qualified_leads",
            "success_criteria": [
                "Every Play resolves its capabilities across alternative providers.",
                "Every business KPI is verified by re-reading the CRM, never from provider acceptance.",
                "The dashboard shows unknown, not zero, when verified evidence is missing.",
            ],
            "outcome_events": sorted({p["outcome_events"][0] for p in PLAYS}),
            "kpis": KPIS,
            "verification_required": True,
        },
        "objectives": [
            {
                "key": "grow-qualified-leads",
                "statement": "Generate more qualified leads",
                "kpi_keys": ["qualified_leads", "mql"],
            },
            {
                "key": "book-more-meetings",
                "statement": "Book more sales meetings",
                "kpi_keys": ["meetings_booked"],
            },
            {
                "key": "grow-pipeline",
                "statement": "Create more qualified pipeline",
                "kpi_keys": ["opportunities_created", "qualified_pipeline_value"],
            },
            {
                "key": "grow-revenue",
                "statement": "Win more revenue",
                "kpi_keys": ["won_revenue", "deals_won"],
            },
        ],
        "agents": [
            {
                "seed_label": _SEED_STRATEGIST,
                "name": "Growth Strategist",
                "purpose": "Plan growth motions toward the objective and manage pipeline progression.",
                "role": "Growth Strategy",
                "department": "Growth",
                "capabilities": ["planning", "pipeline-analysis", "forecasting"],
                "systems": ["hubspot", "salesforce", "pipedrive"],
            },
            {
                "seed_label": _SEED_RESEARCHER,
                "name": "Growth Researcher",
                "purpose": "Find and verify ICP accounts and decision makers from sourced evidence.",
                "role": "Prospect Research",
                "department": "Growth",
                "capabilities": ["account-research", "prospect-research", "enrichment"],
                "systems": ["apollo", "pdl", "clay", "linkedin", "hubspot"],
            },
            {
                "seed_label": _SEED_SDR,
                "name": "Growth SDR",
                "purpose": "Qualify leads, run approved outreach and convert replies into meetings.",
                "role": "Sales Development",
                "department": "Growth",
                "capabilities": ["qualification", "outreach", "follow-up"],
                "systems": ["hubspot", "apollo"],
            },
        ],
        "plays": PLAYS,
        "knowledge": [
            {
                "seed_label": "growth-icp",
                "title": "Ideal Customer Profile",
                "type": "manual",
                "metadata": {"purpose": "ICP, personas and qualification definition."},
            },
            {
                "seed_label": "growth-messaging",
                "title": "Messaging and Outreach Guidelines",
                "type": "manual",
                "metadata": {"purpose": "Approved positioning, tone and outreach rules."},
            },
        ],
        "dataset": {
            "entities": [
                {
                    "name": "crm_contacts",
                    "source": "crm_connector",
                    "primary_key": "contact_id",
                    "fields": ["contact_id", "lifecyclestage", "hs_lead_status", "createdate"],
                },
                {
                    "name": "crm_deals",
                    "source": "crm_connector",
                    "primary_key": "deal_id",
                    "fields": ["deal_id", "dealstage", "pipeline", "amount", "currency", "closedate"],
                },
                {
                    "name": "play_outcomes",
                    "source": "gravitre_verified_outcomes",
                    "primary_key": "outcome_id",
                    "fields": ["outcome_id", "play_key", "metric_key", "status", "verified_at", "value"],
                },
            ],
            "metrics": [
                {"key": row["key"], "label": row["label"], "formula": row.get("formula") or row["description"], "unit": row["unit"]}
                for row in KPIS
            ],
        },
        "dashboard": dashboard(
            title="Growth Command Center",
            template_id="growth-command-center",
            department=DEPARTMENT,
            kpis=KPIS,
            sections=[
                {"title": "Objective progress", "kpi_keys": ["qualified_leads", "meetings_booked", "won_revenue"]},
                {
                    "title": "Funnel",
                    "kpi_keys": [
                        "accounts_qualified", "mql", "qualified_leads", "outreach_delivered", "replies",
                        "meetings_booked", "opportunities_created", "deals_won",
                    ],
                },
                {
                    "title": "Conversion",
                    "kpi_keys": [
                        "reply_rate", "lead_to_meeting_conversion", "meeting_to_opportunity_conversion",
                        "opportunity_to_won_conversion",
                    ],
                },
                {"title": "Revenue", "kpi_keys": ["qualified_pipeline_value", "won_revenue"]},
            ],
            system_health_kpis=["active-runs", "connector-health", "pending-approvals"],
        ),
        "skills": [],
        "skill_requirements": [],
        "skill_bindings": {},
        "runtime_profiles": [
            {
                "provider": "capability-resolved",
                "status": "tested",
                "actions": runtime_profile_actions(PLAYS),
            }
        ],
        "connector_alternatives": [
            ["hubspot", "salesforce", "pipedrive"],
            ["apollo", "pdl", "clay", "linkedin"],
        ],
        "verification_recipes": RECIPES,
        "attribution": {
            "claim_key": ["metric_key", "system", "record_type", "record_id"],
            "primary": "first_verified",
            "assisted_counted_in_total": False,
        },
        "governance": {
            "always_approve_actions": [
                "hubspot.sequences.enroll",
                "apollo.sequences.add",
                "hubspot.contacts.create",
                "hubspot.deals.create",
                "clay.crm.sync",
            ],
            "max_autonomy": "act_with_approval",
        },
        "certification": {
            "minimum_plays": 6,
            "fixtures": _fixtures(),
            "degraded_scenarios": [
                {"capability": "prospect.discovery", "unavailable_vendor": "apollo", "reason": "plan_limit"},
            ],
        },
    }
    return {
        "marketplace": {
            "slug": "growth-pipeline-operator",
            "title": "Growth Pipeline Operator",
            "description": (
                "Work toward a qualified-lead, meeting, pipeline or revenue objective with seven Plays, "
                "provider fallbacks, approval-governed outreach and CRM-verified results."
            ),
            "department_label": "Growth",
            "tags": ["growth", "sales", "marketing", "outcome-pack", "pipeline"],
            "price_cents": 0,
            "pricing_type": "free",
            "required_connectors": [
                {
                    "connectorType": "hubspot",
                    "label": "HubSpot",
                    "required": True,
                    "connectPath": "/connectors?type=hubspot",
                    "requirementNote": "System of record for leads, meetings, deals and revenue.",
                }
            ],
            "business_outcome": "Grow verified qualified leads, meetings, pipeline and won revenue.",
            "use_case": "Growth pipeline generation",
            "estimated_hours_saved": 30.0,
        },
        "config": config,
    }
