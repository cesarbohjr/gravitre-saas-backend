"""Customer Success Outcome Pack.

Retention is verified from the systems of record: subscription status and value
in billing, and the customer's lifecycle stage in the CRM, re-read after a
retention window. Expansion reuses the canonical pipeline metrics.
"""
from __future__ import annotations

from typing import Any

from app.outcome_packs.builders import approval_step, dashboard, play, runtime_profile_actions, tool_step

PACK_ID = "customer-success"
DEPARTMENT = "customer_success"

_ACTIVE = ["active", "trialing"]
_ENDED = ["canceled", "unpaid", "incomplete_expired"]  # verified failure

KPIS: list[dict[str, Any]] = [
    {
        "key": "customers_retained",
        "label": "At-risk customers retained",
        "description": "At-risk customers a Play engaged whose subscription is still active after the retention window.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "customer_success",
        "departments": ["customer_success", "executive"],
        "source_system": "stripe",
        "source_record_type": "subscription",
        "verification_recipe": "billing-subscription-retention",
        "evidence_strategy": "Re-read the subscription in billing after the retention window.",
        "synonyms": ["retained customers", "saved customers", "customer retention", "reduce churn", "churn"],
        "definition_prompt": "A customer counts as retained when their subscription is still active 30 days after we engaged them.",
    },
    {
        "key": "revenue_retained",
        "label": "Revenue retained",
        "description": "Monthly subscription value still active on at-risk customers a Play engaged.",
        "unit": "currency",
        "direction": "increase",
        "kind": "business",
        "aggregation": "sum",
        "department": "customer_success",
        "departments": ["customer_success", "finance", "executive"],
        "source_system": "stripe",
        "source_record_type": "subscription",
        "verification_recipe": "billing-subscription-retention",
        "evidence_strategy": "Sum the active subscription's price from billing; amounts are converted from cents.",
        "synonyms": ["retained revenue", "saved revenue", "mrr retained", "revenue at risk saved"],
    },
    {
        "key": "accounts_still_customers",
        "label": "Accounts still customers",
        "description": "Engaged CRM accounts whose lifecycle stage is still Customer after the retention window.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "customer_success",
        "source_system": "hubspot",
        "source_record_type": "company",
        "verification_recipe": "crm-account-retention",
        "evidence_strategy": "Re-read the CRM company lifecycle stage after the retention window.",
        "synonyms": ["accounts retained", "logo retention"],
    },
    {
        "key": "opportunities_created",
        "label": "Expansion opportunities created",
        "description": "Expansion deals that exist in the CRM and are open or won.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "sales",
        "departments": ["customer_success"],
    },
    {
        "key": "customer_health",
        "label": "Customer health",
        "description": "Predicted account health. A model estimate, not a verified outcome.",
        "unit": "score",
        "direction": "increase",
        "kind": "operational",
        "aggregation": "avg",
        "department": "customer_success",
        "synonyms": ["customer health", "health score"],
    },
]

RECIPES: list[dict[str, Any]] = [
    {
        "key": "billing-subscription-retention",
        "source_system": "stripe",
        "record_type": "subscription",
        "match_actions": ["manual.retention_outreach", "intercom.conversations.reply", "gmail.messages.send", "stripe.subscriptions.update"],
        "read_action": "stripe.subscriptions.get",
        "record_id_param": "subscription_id",
        "record_id_fields": ["record_ids.subscription", "subscription_id", "entity_id"],
        "verification_method": "billing_subscription_reread",
        "measure_after_hours": 24 * 30,
        "measure_window_days": 60,
        "contributions": [
            {
                "metric_key": "customers_retained",
                "when": {"field": "current.subscription.status", "op": "in", "value": _ACTIVE},
                "fail_when": {"field": "current.subscription.status", "op": "in", "value": _ENDED},
            },
            {
                "metric_key": "revenue_retained",
                "when": {
                    "all": [
                        {"field": "current.subscription.status", "op": "in", "value": _ACTIVE},
                        {"field": "current.subscription.items.data.0.price.unit_amount", "op": "exists"},
                    ]
                },
                "value": {"field": "current.subscription.items.data.0.price.unit_amount", "scale": 0.01},
                "currency_field": "current.subscription.currency",
            },
        ],
    },
    {
        "key": "crm-account-retention",
        "source_system": "hubspot",
        "record_type": "company_retention",
        "match_actions": ["hubspot.companies.update", "hubspot.notes.create", "manual.retention_outreach"],
        "read_action": "hubspot.companies.get",
        "record_id_param": "company_id",
        "record_id_fields": ["record_ids.company", "company_id", "entity_id"],
        "read_params": {"include_evidence": True},
        "verification_method": "crm_company_reread",
        "measure_after_hours": 24 * 30,
        "measure_window_days": 60,
        "contributions": [
            {
                "metric_key": "accounts_still_customers",
                "when": {"field": "current.evidence.lifecyclestage", "op": "eq", "value": "customer"},
                "fail_when": {"field": "current.evidence.lifecyclestage", "op": "in", "value": ["other", "former_customer"]},
            }
        ],
    },
]

_SEED_CSM = "agent:cs-manager"
_SEED_ANALYST = "agent:cs-analyst"

PLAYS: list[dict[str, Any]] = [
    play(
        "churn-risk-intervention",
        "Churn Risk Intervention",
        "Find customers with credible churn risk and coordinate an approved save motion.",
        objective="Retain at-risk customers and their revenue.",
        kpis=["customers_retained", "revenue_retained"],
        outcome_event="churn_intervention_sent",
        trigger={"type": "scheduled", "cadence": "daily"},
        agent_seed=_SEED_CSM,
        task="Rank at-risk customers with evidence from billing and support. Draft a save message for approval.",
        evidence_steps=[
            tool_step("read-subscription", "Read subscription status", "capability.billing.subscription.read",
                      param_sources={"subscription_id": "$SUBSCRIPTION_ID"}),
            tool_step("read-conversations", "Read recent conversations", "capability.cs.conversation.read",
                      param_sources={"per_page": 50}),
        ],
        action_steps_after=[
            approval_step("approve-save", "Approve save outreach", "Messages the customer"),
            tool_step("send-save", "Send the approved message", "capability.cs.customer.message",
                      param_sources={"to": "$CUSTOMER_EMAIL", "body": "$MESSAGE"}),
        ],
        capability_groups=[["billing.subscription.read"], ["cs.conversation.read"], ["cs.customer.message"]],
        required_connector_groups=[["stripe"]],
        optional_connectors=["intercom", "zendesk", "freshdesk", "hubspot"],
        write_actions=[{"capability": "cs.customer.message", "approval": "always"}],
    ),
    play(
        "renewal-readiness",
        "Renewal Readiness",
        "Check upcoming renewals for risk and line up the owner, value story and next step early.",
        objective="Renew customers on time with no revenue loss.",
        kpis=["customers_retained", "revenue_retained"],
        outcome_event="renewal_prepared",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_CSM,
        task="List renewals in the next 90 days, score risk with evidence and create the CSM's next task.",
        evidence_steps=[
            tool_step("read-renewal", "Read the subscription", "capability.billing.subscription.read",
                      param_sources={"subscription_id": "$SUBSCRIPTION_ID"}),
        ],
        action_steps_after=[
            tool_step("renewal-task", "Create renewal task", "capability.crm.task.create",
                      param_sources={"company_id": "$COMPANY_ID", "body": "$RENEWAL_NOTE"}),
        ],
        approvals=[{"when": "capability.crm.task.create", "required": True}],
        capability_groups=[["billing.subscription.read"], ["crm.task.create"]],
        required_connector_groups=[["stripe"], ["hubspot", "salesforce"]],
        write_actions=[{"capability": "crm.task.create", "approval": "policy"}],
    ),
    play(
        "onboarding-acceleration",
        "Onboarding Acceleration",
        "Spot new customers stuck in onboarding and send the right help before they lose momentum.",
        objective="Retain new customers through onboarding.",
        kpis=["customers_retained", "accounts_still_customers"],
        outcome_event="onboarding_nudged",
        trigger={"type": "event", "event": "billing.subscription.created"},
        agent_seed=_SEED_CSM,
        task="Find onboarding blockers from support and CRM evidence. Draft one helpful message per customer.",
        evidence_steps=[
            tool_step("read-new-customer", "Read the new customer", "capability.crm.contact.read",
                      param_sources={"contact_id": "$CONTACT_ID"}),
        ],
        action_steps_after=[
            approval_step("approve-onboarding", "Approve onboarding message", "Messages the customer"),
            tool_step("send-onboarding", "Send the onboarding message", "capability.cs.customer.message",
                      param_sources={"to": "$CUSTOMER_EMAIL", "body": "$MESSAGE"}),
        ],
        capability_groups=[["crm.contact.read"], ["cs.customer.message"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        write_actions=[{"capability": "cs.customer.message", "approval": "always"}],
    ),
    play(
        "expansion-signal-finder",
        "Expansion Signal Finder",
        "Find healthy customers with expansion signals and open an expansion opportunity.",
        objective="Grow revenue from existing customers.",
        kpis=["opportunities_created"],
        outcome_event="expansion_opportunity_opened",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_ANALYST,
        task="Rank customers by expansion evidence and propose an expansion deal with the reason.",
        evidence_steps=[
            tool_step("read-accounts", "Read customer pipeline", "capability.crm.pipeline.read",
                      param_sources={"max_records": 2000}),
        ],
        action_steps_after=[
            approval_step("approve-expansion", "Approve expansion deal", "Creates a CRM deal"),
            tool_step("create-expansion", "Create the expansion deal", "capability.crm.deal.create",
                      param_sources={"properties": "$DEAL_PROPERTIES"}),
        ],
        capability_groups=[["crm.pipeline.read"], ["crm.deal.create"]],
        required_connector_groups=[["hubspot", "salesforce", "pipedrive"]],
        write_actions=[{"capability": "crm.deal.create", "approval": "always"}],
    ),
    play(
        "support-escalation-watch",
        "Support Escalation Watch",
        "Catch customers with repeated or escalated support issues and bring in the CSM before they churn.",
        objective="Prevent churn caused by support pain.",
        kpis=["customers_retained", "revenue_retained"],
        outcome_event="escalation_addressed",
        trigger={"type": "scheduled", "cadence": "daily"},
        agent_seed=_SEED_ANALYST,
        task="Group recent tickets by customer, flag repeated pain, and draft the CSM's outreach.",
        evidence_steps=[
            tool_step("read-tickets", "Read recent tickets", "capability.support.ticket.list",
                      param_sources={"per_page": 100}),
        ],
        action_steps_after=[
            approval_step("approve-escalation", "Approve customer outreach", "Messages the customer"),
            tool_step("send-escalation", "Send the approved outreach", "capability.cs.customer.message",
                      param_sources={"to": "$CUSTOMER_EMAIL", "body": "$MESSAGE"}),
        ],
        capability_groups=[["support.ticket.list"], ["cs.customer.message"]],
        required_connector_groups=[["zendesk", "freshdesk", "freshservice", "intercom"]],
        write_actions=[{"capability": "cs.customer.message", "approval": "always"}],
    ),
    play(
        "executive-sponsor-check",
        "Executive Sponsor Check",
        "Make sure key accounts have a verified, engaged executive sponsor in the CRM.",
        objective="Retain key accounts by keeping executive relationships current.",
        kpis=["accounts_still_customers", "customers_retained"],
        outcome_event="sponsor_confirmed",
        trigger={"type": "scheduled", "cadence": "monthly"},
        agent_seed=_SEED_ANALYST,
        task="Find key accounts without a current executive sponsor and verify candidates from sourced data.",
        evidence_steps=[
            tool_step("find-sponsor", "Find sponsor candidates", "capability.prospect.discovery",
                      param_sources={"organization_domains": "$ACCOUNT_DOMAIN", "query": "executive"}),
        ],
        action_steps_after=[
            approval_step("approve-sponsor", "Approve sponsor update", "Updates the CRM account"),
            tool_step("record-sponsor", "Record the sponsor on the account", "capability.crm.company.update",
                      param_sources={"company_id": "$COMPANY_ID", "properties": "$SPONSOR_PROPERTIES"}),
        ],
        capability_groups=[["prospect.discovery"], ["crm.company.update"]],
        required_connector_groups=[["hubspot", "salesforce"]],
        optional_connectors=["apollo", "pdl", "clay"],
        write_actions=[{"capability": "crm.company.update", "approval": "always"}],
    ),
]


def build() -> dict[str, Any]:
    config: dict[str, Any] = {
        "marketplace_version": "3.0",
        "pack_id": PACK_ID,
        "department": DEPARTMENT,
        "outcome_contract": {
            "problem": "Churn signals are spread across billing, support and CRM, so saves come too late.",
            "target_outcome": "Retain more customers and revenue, verified in billing and the CRM.",
            "baseline_metric": "customers_retained",
            "success_criteria": [
                "Retention is counted only from billing or CRM state after the retention window.",
                "Customer health stays an estimate and never counts as a verified result.",
            ],
            "outcome_events": sorted({p["outcome_events"][0] for p in PLAYS}),
            "kpis": KPIS,
            "verification_required": True,
        },
        "objectives": [
            {"key": "reduce-churn", "statement": "Reduce customer churn", "kpi_keys": ["customers_retained", "revenue_retained"]},
            {"key": "grow-expansion", "statement": "Grow expansion revenue", "kpi_keys": ["opportunities_created"]},
        ],
        "agents": [
            {"seed_label": _SEED_CSM, "name": "Customer Success Manager", "purpose": "Run save, renewal and onboarding motions.",
             "role": "Customer Success", "department": "Customer Success",
             "capabilities": ["retention", "renewals", "onboarding"], "systems": ["stripe", "hubspot", "intercom"]},
            {"seed_label": _SEED_ANALYST, "name": "Customer Success Analyst", "purpose": "Find risk and expansion signals.",
             "role": "CS Operations", "department": "Customer Success",
             "capabilities": ["risk-analysis", "expansion-signals"], "systems": ["stripe", "hubspot", "zendesk"]},
        ],
        "plays": PLAYS,
        "knowledge": [
            {"seed_label": "cs-playbook", "title": "Customer Success Playbook", "type": "manual",
             "metadata": {"purpose": "Save offers, renewal process and escalation paths."}},
        ],
        "dataset": {
            "entities": [
                {"name": "subscriptions", "source": "billing_connector", "primary_key": "subscription_id",
                 "fields": ["subscription_id", "status", "current_period_end", "unit_amount", "currency"]},
            ],
            "metrics": [
                {"key": row["key"], "label": row["label"], "formula": row["description"], "unit": row["unit"]}
                for row in KPIS
            ],
        },
        "dashboard": dashboard(
            title="Customer Retention",
            template_id="customer-retention",
            department=DEPARTMENT,
            kpis=KPIS,
            sections=[
                {"title": "Retention", "kpi_keys": ["customers_retained", "revenue_retained"]},
                {"title": "Accounts", "kpi_keys": ["accounts_still_customers", "opportunities_created"]},
                {"title": "Estimates", "kpi_keys": ["customer_health"]},
            ],
            system_health_kpis=["connector-health"],
        ),
        "runtime_profiles": [
            {"provider": "capability-resolved", "status": "tested", "actions": runtime_profile_actions(PLAYS)}
        ],
        "connector_alternatives": [["stripe"], ["hubspot", "salesforce", "pipedrive"], ["intercom", "zendesk", "freshdesk"]],
        "verification_recipes": RECIPES,
        "governance": {
            "always_approve_actions": ["intercom.conversations.reply", "gmail.messages.send"],
            "max_autonomy": "act_with_approval",
        },
        "certification": {
            "minimum_plays": 6,
            "fixtures": {
                "billing-subscription-retention": {
                    "record_id": "sub_1",
                    "current": {"subscription": {"status": "active", "currency": "usd",
                                                 "items": {"data": [{"price": {"unit_amount": 49900}}]}}},
                },
                "crm-account-retention": {
                    "record_id": "company-9",
                    "current": {"evidence": {"lifecyclestage": "customer"}},
                },
            },
            "degraded_scenarios": [
                {"capability": "cs.customer.message", "unavailable_vendor": "intercom", "reason": "auth_expired"},
            ],
        },
    }
    return {
        "marketplace": {
            "slug": "customer-success-operator",
            "title": "Customer Retention Operator",
            "description": "Retain more customers and revenue with six CS Plays verified in billing and the CRM.",
            "department_label": "Customer Success",
            "tags": ["customer-success", "retention", "outcome-pack"],
            "price_cents": 0,
            "pricing_type": "free",
            "required_connectors": [
                {"connectorType": "stripe", "label": "Stripe", "required": True, "connectPath": "/connectors?type=stripe",
                 "requirementNote": "Source of record for subscription status and value."},
            ],
            "business_outcome": "Retain more customers and revenue.",
            "use_case": "Customer retention",
            "estimated_hours_saved": 16.0,
        },
        "config": config,
    }
