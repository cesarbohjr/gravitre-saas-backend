"""Department-specific evidence contracts for the Marketplace 3.0 portfolio.

These enrich existing packs; they grant neither live verification nor authority
to write. Optional providers are not interchangeable runtime implementations.
"""
from __future__ import annotations

from typing import Any


# Each action here already belongs to the pack's registered runtime profile.
# Canonical Play readiness and installed workflows consume the same evidence map.
PLAY_EVIDENCE: dict[str, tuple[str, ...]] = {
    "inbound-lead-qualifier": ("hubspot.contacts.search", "hubspot.companies.search", "hubspot.owners.list"),
    "account-research-brief": ("hubspot.companies.search", "hubspot.deals.search"),
    "meeting-prep-brief": ("hubspot.deals.get", "hubspot.companies.search", "hubspot.owners.list"),
    "stale-deal-recovery": ("hubspot.deals.list", "hubspot.pipelines.list", "hubspot.owners.list"),
    "pipeline-risk-review": ("hubspot.deals.search", "hubspot.pipelines.list", "hubspot.owners.list"),
    "forecast-integrity-check": ("hubspot.pipelines.list", "hubspot.deals.list"),
    "renewal-expansion-watch": ("hubspot.companies.search", "hubspot.deals.search"),
    "post-meeting-follow-up-review": ("hubspot.deals.get", "hubspot.companies.search"),
    "customer-health-watch": ("hubspot.companies.search", "zendesk.tickets.list"),
    "churn-risk-detector": ("zendesk.tickets.list", "hubspot.companies.search", "hubspot.deals.list"),
    "escalation-recovery-review": ("zendesk.tickets.get", "hubspot.companies.search"),
    "qbr-preparation": ("hubspot.companies.search", "hubspot.deals.list", "zendesk.tickets.list"),
    "renewal-readiness-review": ("hubspot.deals.list", "zendesk.tickets.list"),
    "expansion-signal-watch": ("hubspot.companies.search", "hubspot.deals.list", "zendesk.tickets.list"),
    "service-gap-detector": ("zendesk.tickets.list", "hubspot.companies.search"),
    "voice-of-customer-watch": ("zendesk.tickets.list", "hubspot.companies.search"),
    "ar-priority-review": ("quickbooks.invoices.list", "quickbooks.customers.list", "quickbooks.payments.list"),
    "collections-strategy-brief": ("quickbooks.invoices.get", "quickbooks.customers.list", "quickbooks.payments.list"),
    "cash-risk-watch": ("quickbooks.payments.list", "quickbooks.invoices.list"),
    "invoice-exception-review": ("quickbooks.invoices.list", "quickbooks.customers.list", "quickbooks.payments.list"),
    "vendor-exception-review": ("quickbooks.vendors.list", "quickbooks.accounts.list"),
    "renewal-exposure-watch": ("stripe.subscriptions.get", "stripe.invoices.list"),
    "month-end-readiness": ("quickbooks.accounts.list", "quickbooks.payments.list", "quickbooks.invoices.list"),
    "revenue-leak-hunter": ("quickbooks.invoices.list", "quickbooks.payments.list", "stripe.invoices.list"),
    "campaign-performance-review": ("hubspot.campaigns.list", "hubspot.contacts.list"),
    "attribution-integrity-check": ("hubspot.deals.list", "hubspot.campaigns.list", "hubspot.contacts.list"),
    "lead-handoff-qa": ("hubspot.contacts.list", "hubspot.deals.list"),
    "campaign-anomaly-watch": ("hubspot.campaigns.list", "hubspot.contacts.list"),
    "audience-opportunity-review": ("hubspot.contacts.list", "hubspot.campaigns.list"),
    "content-performance-review": ("hubspot.campaigns.list", "hubspot.contacts.list"),
    "pipeline-contribution-review": ("hubspot.deals.list", "hubspot.campaigns.list", "hubspot.contacts.list"),
    "lifecycle-conversion-review": ("hubspot.pipelines.list", "hubspot.contacts.list", "hubspot.deals.list"),
    "onboarding-readiness-review": ("bamboohr.employees.list", "freshservice.tickets.list"),
    "offboarding-readiness-review": ("bamboohr.employees.list", "freshservice.tickets.list"),
    "policy-request-triage": ("freshservice.tickets.list", "bamboohr.employees.list"),
    "employee-request-triage": ("freshservice.tickets.get", "bamboohr.employees.list"),
    "access-review-watch": ("bamboohr.employees.get", "freshservice.tickets.list"),
    "device-service-risk-review": ("freshservice.tickets.list", "bamboohr.employees.list"),
    "license-utilization-review": ("bamboohr.employees.list", "freshservice.tickets.list"),
    "service-request-bottleneck-review": ("freshservice.tickets.list", "bamboohr.employees.list"),
    "executive-morning-brief": ("hubspot.deals.list", "quickbooks.invoices.list", "zendesk.tickets.list"),
    "revenue-risk-watch": ("hubspot.companies.search", "hubspot.deals.list"),
    "cash-risk-watch-executive": ("quickbooks.invoices.list", "quickbooks.payments.list"),
    "customer-risk-watch-executive": ("zendesk.tickets.list", "hubspot.companies.search"),
    "service-risk-watch": ("zendesk.tickets.list", "hubspot.companies.search"),
    "marketing-signal-watch": ("hubspot.campaigns.list", "hubspot.deals.list"),
    "cross-functional-priority-review": ("quickbooks.payments.list", "hubspot.deals.list", "zendesk.tickets.list"),
    "operational-anomaly-watch": ("zendesk.tickets.list", "quickbooks.invoices.list", "hubspot.deals.list"),
}

ACTION_INPUTS = {
    "hubspot.deals.get": "deal_id",
    "zendesk.tickets.get": "ticket_id",
    "quickbooks.invoices.get": "invoice_id",
    "stripe.subscriptions.get": "subscription_id",
    "bamboohr.employees.get": "employee_id",
    "freshservice.tickets.get": "ticket_id",
}

# name, source, primary key, business fields. Every entity also carries source
# identity and observation time; mixed-system joins must be explicitly supported.
DEPARTMENT_ENTITIES = {
    "revenue-operations-3": [
        ("contacts", "hubspot", "contact_id", ["company_id", "owner_id", "lifecycle_stage", "created_at", "first_response_at"]),
        ("accounts", "hubspot", "company_id", ["domain", "owner_id", "renewal_at"]),
        ("opportunities", "hubspot", "deal_id", ["company_id", "pipeline_id", "stage_id", "owner_id", "amount", "currency", "created_at", "stage_entered_at", "close_at", "last_activity_at"]),
        ("pipeline_stages", "hubspot", "stage_id", ["pipeline_id", "label", "probability", "is_closed"]),
        ("revenue_owners", "hubspot", "owner_id", ["team_id", "active"]),
    ],
    "customer-success-support-3": [
        ("customer_accounts", "hubspot", "company_id", ["domain", "owner_id", "renewal_at"]),
        ("commercial_opportunities", "hubspot", "deal_id", ["company_id", "amount", "currency", "close_at", "stage_id"]),
        ("support_cases", "zendesk", "ticket_id", ["organization_id", "requester_id", "status", "priority", "owner_id", "created_at", "updated_at", "resolved_at", "tags"]),
        ("account_identity_map", "tenant_verified_mapping", "mapping_id", ["company_id", "organization_id", "verified_at", "mapping_method"]),
        ("customer_themes", "verified_support_evidence", "theme_id", ["ticket_ids", "company_id", "theme", "confidence", "reviewed_at"]),
    ],
    "finance-operations-3": [
        ("receivables", "quickbooks", "invoice_id", ["customer_id", "currency", "amount", "balance", "issued_at", "due_at", "status"]),
        ("payments", "quickbooks", "payment_id", ["customer_id", "invoice_ids", "amount", "currency", "paid_at"]),
        ("vendors", "quickbooks", "vendor_id", ["active", "balance", "currency"]),
        ("ledger_accounts", "quickbooks", "account_id", ["account_type", "balance", "currency"]),
        ("subscriptions", "stripe", "subscription_id", ["customer_id", "status", "currency", "renewal_at"]),
        ("billing_invoices", "stripe", "invoice_id", ["customer_id", "subscription_id", "amount_due", "amount_paid", "currency", "due_at", "status"]),
    ],
    "marketing-operations-3": [
        ("campaigns", "hubspot", "campaign_id", ["name", "created_at", "updated_at", "engagement_count"]),
        ("marketing_contacts", "hubspot", "contact_id", ["lifecycle_stage", "created_at", "qualified_at", "source", "campaign_ids"]),
        ("marketing_opportunities", "hubspot", "deal_id", ["contact_ids", "campaign_ids", "pipeline_id", "stage_id", "amount", "currency", "created_at"]),
        ("funnel_stages", "hubspot", "stage_id", ["pipeline_id", "label", "probability", "is_closed"]),
        ("attribution_evidence", "verified_crm_associations", "evidence_id", ["campaign_id", "contact_id", "deal_id", "model", "confidence", "verified_at"]),
    ],
    "people-it-operations-3": [
        ("employees", "bamboohr", "employee_id", ["department", "employment_status", "start_at", "end_at"]),
        ("employee_service_requests", "freshservice", "ticket_id", ["requester_id", "owner_id", "status", "priority", "created_at", "due_at", "resolved_at"]),
        ("employee_identity_map", "tenant_verified_mapping", "mapping_id", ["employee_id", "requester_id", "verified_at", "mapping_method"]),
        ("lifecycle_checklists", "verified_service_evidence", "checklist_id", ["employee_id", "ticket_ids", "lifecycle_event", "blockers", "verified_at"]),
        ("access_review_evidence", "verified_service_evidence", "evidence_id", ["employee_id", "ticket_id", "review_status", "reviewed_at"]),
    ],
    "executive-command-center-3": [
        ("revenue_exposure", "hubspot", "deal_id", ["company_id", "amount", "currency", "stage_id", "close_at"]),
        ("cash_exposure", "quickbooks", "invoice_id", ["customer_id", "balance", "currency", "due_at"]),
        ("customer_service_exposure", "zendesk", "ticket_id", ["organization_id", "status", "priority", "created_at", "updated_at"]),
        ("marketing_signals", "hubspot", "campaign_id", ["engagement_count", "updated_at"]),
        ("executive_priorities", "verified_operating_evidence", "priority_id", ["source_record_ids", "owner", "severity", "due_at", "status", "verified_at"]),
        ("account_identity_map", "tenant_verified_mapping", "mapping_id", ["company_id", "customer_id", "organization_id", "verified_at"]),
    ],
}

DEPARTMENT_GUIDANCE = {
    "revenue-operations-3": (
        "ICP & Qualification Standard|Require tenant ICP criteria, territory rules, and lifecycle definitions; missing data is unknown, not disqualified.",
        "Pipeline & Forecast Standard|Require stage definitions, probability policy, forecast period, quota, and currency. Do not infer stage entry times or pipeline coverage from an unpaginated current snapshot.",
        "Meeting & Follow-Up Standard|Meeting preparation and follow-up require deal_id and tenant-provided meeting evidence; CRM deal reads alone do not prove attendance, transcript content, or a sent follow-up.",
        "Renewal & Expansion Standard|Require mapped renewal dates, contract value, and account associations. Expansion recommendations are hypotheses until confirmed.",
    ),
    "customer-success-support-3": (
        "Customer Health & Identity Standard|Join CRM and support records only through a verified account map; missing support evidence is unknown health, not healthy.",
        "Escalation & Recovery Standard|Define severity, escalation SLA, accountable owner, and recovery verification. A drafted recommendation does not close an escalation.",
        "QBR & Renewal Standard|Require contract and renewal data plus service evidence; distinguish QBR preparation from a delivered review and renewal readiness from a signed renewal.",
        "Voice of Customer Standard|Use source-linked ticket themes, deduplicate evidence, and label confidence; ticket volume is not customer prevalence without a denominator.",
    ),
    "finance-operations-3": (
        "Receivables & Collections Standard|Require as-of date, terms, credit notes, payment allocation, reporting period, and currency. Deduplicate invoice/payment records; do not add currencies without approved conversion.",
        "Cash & Close Standard|Separate realized payments, overdue balances, and projected exposure. DSO requires credit sales for the same period; missing ledger evidence means unavailable, not zero.",
        "Billing & Renewal Standard|Use subscription_id for subscription reviews. Reconcile Stripe and accounting invoices through verified mappings before identifying recoverable revenue or double counting.",
        "Finance Approval Standard|Collections briefs are drafts. Payments, refunds, ledger changes, and external customer communications require separate approved execution and source verification.",
    ),
    "marketing-operations-3": (
        "Lifecycle & Handoff Standard|Define MQL/SQL cohorts, lifecycle timestamps, owner SLA, and measurement window. A pipeline-stage definition is not a conversion observation.",
        "Attribution Model Standard|Require an explicit model, source-linked campaign/contact/deal associations, lookback window, and deduplication. Missing associations mean unknown contribution; CRM context cannot prove ad spend, ROAS, or causal lift.",
        "Campaign & Content Standard|Compare complete, aligned observation windows. Label engagement-based content proxies; missing paid-media or analytics evidence prevents unsupported channel conclusions.",
        "Audience & Activation Standard|Segment recommendations remain drafts; publishing campaigns, enrolling contacts, and changing budgets require approved execution.",
    ),
    "people-it-operations-3": (
        "Employee Lifecycle Standard|Require start/end dates and verified employee/requester mapping; distinguish readiness from completed onboarding or offboarding.",
        "Service & Access Standard|Use ticket evidence for review status; employee lists do not prove actual entitlements, device state, or license usage without corresponding authoritative systems.",
        "People Data Standard|Minimize employee information, respect tenant access scopes, and exclude sensitive HR fields from broad dashboards and briefs.",
        "Lifecycle Approval Standard|Account provisioning, revocation, license changes, and employee communications require approved execution and source-of-record verification.",
    ),
    "executive-command-center-3": (
        "Operating Brief Standard|Show source, observation time, reporting window, currency, materiality threshold, and missing coverage for every signal; do not sum unlike risk scores.",
        "Cross-Functional Identity Standard|Join revenue, accounting, and support accounts only through verified mappings; preserve department-level exposure when a join is unavailable.",
        "Priority & Escalation Standard|Rank evidence-backed impact and urgency, propose owner and due date, and distinguish recommendation from accepted ownership and verified resolution.",
        "Executive Measurement Standard|Use aligned historical windows for anomaly detection. A current snapshot does not prove trend, causal impact, resolved risk, or financial savings.",
    ),
}


def deepen_department_config(slug: str, config: dict[str, Any]) -> dict[str, Any]:
    """Enrich a freshly built base config without changing catalog identities."""
    if slug not in DEPARTMENT_ENTITIES:
        return config
    guidance = DEPARTMENT_GUIDANCE[slug]
    policy = " ".join(item.split("|", 1)[1] for item in guidance)
    for play in config["plays"]:
        actions = PLAY_EVIDENCE[play["key"]]
        steps = []
        inputs = []
        for index, action in enumerate(actions):
            provider, selected = action.split(".", 1)
            step_config = {
                "action": action, "tool_action": action,
                "vendor": provider, "connector": provider,
                "selectedAction": selected, "selected_action": selected,
            }
            parameter = ACTION_INPUTS.get(action)
            if parameter:
                step_config["param_sources"] = {parameter: f"${parameter}"}
                inputs.append(parameter)
            steps.append({
                "id": f"{play['key']}-evidence-{index}",
                "name": action.replace(".", " ").title(),
                "type": "invoke_tool", "config": step_config,
                "requires_connector": provider,
            })
        analysis = play["workflow_steps"][-1]
        analysis["metadata"]["task"] += (
            " Reconcile all evidence steps by source record identity; cite records and observation times. "
            "Report sampled/incomplete coverage and missing prerequisites. Never turn a prepared review "
            "into a claim of executed work or measured KPI improvement. " + policy
        )
        play["workflow_steps"] = steps + [analysis]
        play["runtime_inputs"] = sorted(set(inputs))
        play["trigger"] = (
            {"type": "manual"} if inputs
            else {"type": "scheduled", "cadence": "hourly" if play["key"] == "inbound-lead-qualifier" else "daily"}
        )
        play["verification"].update({
            "require_source_record_ids": True,
            "require_observation_time": True,
            "missing_evidence_is_success": False,
        })
    config["knowledge"] = [
        {"seed_label": f"{slug}:standard-{index}", "title": item.split("|", 1)[0],
         "type": "manual", "metadata": {"purpose": item.split("|", 1)[1]}}
        for index, item in enumerate(guidance)
    ]
    config["dataset"]["entities"] = [
        {"name": name, "source": source, "primary_key": primary_key,
         "fields": list(dict.fromkeys([primary_key, *fields, "source_record", "observed_at"]))}
        for name, source, primary_key, fields in DEPARTMENT_ENTITIES[slug]
    ] + [{
        "name": "verified_outcomes", "source": "gravitre_verified_outcomes",
        "primary_key": "outcome_id",
        "fields": ["outcome_id", "play_key", "status", "verified_at", "metric_delta",
                   "source_record", "measurement_window", "baseline", "sample_size"],
    }]
    for kpi in config["outcome_contract"]["kpis"]:
        kpi["source"] = "gravitre_verified_outcomes"
    for metric in config["dashboard"]["metrics"]:
        metric["description"] = (
            f"{metric['label']}: show verified observations and aligned measurement windows; "
            "missing baseline or source coverage is unavailable, never zero or inferred improvement."
        )
    config["outcome_contract"]["success_criteria"].extend([
        "Every evidence action resolves through canonical Play readiness and the pack runtime profile.",
        "Record-specific reviews require explicit runtime IDs before execution.",
        "Cross-system joins require verified identity mappings and complete measurement coverage.",
        "Prepared reviews are activity evidence; outcome improvement requires a measured baseline and source-linked result.",
    ])
    for agent in config["agents"]:
        agent["purpose"] += " " + policy
    return config
