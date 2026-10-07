"""Finance Collections Outcome Pack.

Collections are verified from the accounting system of record: an invoice
counts as collected only when a re-read shows its open balance at zero after
Gravitre's reminder. Declarative only — no runtime code was added for this
department; it runs on the same objective planner, capability resolver, Play
runtime, measurement engine and evidence model as every other pack.
"""
from __future__ import annotations

from typing import Any

from app.outcome_packs.builders import approval_step, dashboard, play, runtime_profile_actions, tool_step

PACK_ID = "finance-collections"
DEPARTMENT = "finance"

KPIS: list[dict[str, Any]] = [
    {
        "key": "invoices_collected",
        "label": "Overdue invoices collected",
        "description": "Overdue invoices a Play followed up on whose open balance is zero when re-read in accounting.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "finance",
        "departments": ["finance", "executive"],
        "source_system": "quickbooks",
        "source_record_type": "invoice",
        "verification_recipe": "accounting-invoice-collection",
        "evidence_strategy": "Re-read the invoice in accounting and require a zero open balance.",
        "synonyms": [
            "collections", "improve collections", "collect invoices", "overdue invoices", "overdue receivables",
            "accounts receivable", "receivables", "late payments", "unpaid invoices", "past due invoices",
        ],
        "definition_prompt": "I'll count an invoice as collected when your accounting system shows a zero open balance after we followed up.",
    },
    {
        "key": "cash_collected",
        "label": "Overdue cash collected",
        "description": "Invoice value collected on overdue invoices a Play followed up on, from accounting.",
        "unit": "currency",
        "direction": "increase",
        "kind": "business",
        "aggregation": "sum",
        "department": "finance",
        "departments": ["finance", "executive"],
        "source_system": "quickbooks",
        "source_record_type": "invoice",
        "verification_recipe": "accounting-invoice-collection",
        "evidence_strategy": "Sum the invoice total once accounting shows a zero open balance.",
        "synonyms": ["cash collected", "collected revenue", "receivables collected", "reduce dso", "dso"],
    },
]

RECIPES: list[dict[str, Any]] = [
    {
        "key": "accounting-invoice-collection",
        "source_system": "quickbooks",
        "record_type": "invoice",
        "match_actions": ["gmail.messages.send", "intercom.conversations.reply", "manual.collections_followup"],
        "read_action": "quickbooks.invoices.get",
        "record_id_param": "invoice_id",
        "record_id_fields": ["record_ids.invoice", "invoice_id", "entity_id"],
        "verification_method": "accounting_invoice_reread",
        "measure_after_hours": 24 * 7,
        "measure_window_days": 45,
        "contributions": [
            {
                "metric_key": "invoices_collected",
                "when": {"field": "current.invoice.Balance", "op": "eq", "value": 0},
            },
            {
                "metric_key": "cash_collected",
                "when": {
                    "all": [
                        {"field": "current.invoice.Balance", "op": "eq", "value": 0},
                        {"field": "current.invoice.TotalAmt", "op": "exists"},
                    ]
                },
                "value": {"field": "current.invoice.TotalAmt"},
                "currency_field": "current.invoice.CurrencyRef.value",
            },
        ],
    },
]

_SEED_AR = "agent:ar-specialist"

PLAYS: list[dict[str, Any]] = [
    play(
        "overdue-invoice-followup",
        "Overdue Invoice Follow-up",
        "Find overdue invoices and send an approved, courteous reminder with the payment link.",
        objective="Collect overdue invoices.",
        kpis=["invoices_collected", "cash_collected"],
        outcome_event="collections_reminder_sent",
        trigger={"type": "scheduled", "cadence": "daily"},
        agent_seed=_SEED_AR,
        task="List overdue invoices, rank by amount and age, and draft one reminder per customer for approval.",
        evidence_steps=[
            tool_step("read-invoices", "Read open invoices", "capability.finance.invoices.read",
                      param_sources={"max_results": 200}),
        ],
        action_steps_after=[
            approval_step("approve-reminder", "Approve payment reminder", "Emails the customer"),
            tool_step("send-reminder", "Send the approved reminder", "capability.cs.customer.message",
                      param_sources={"to": "$CUSTOMER_EMAIL", "body": "$MESSAGE"}),
        ],
        capability_groups=[["finance.invoices.read"], ["cs.customer.message"]],
        required_connector_groups=[["quickbooks", "xero", "stripe", "netsuite"]],
        optional_connectors=["gmail", "intercom"],
        write_actions=[{"capability": "cs.customer.message", "approval": "always"}],
    ),
    play(
        "disputed-invoice-triage",
        "Disputed Invoice Triage",
        "Spot overdue invoices that are stuck on a dispute and give the owner the context to resolve them.",
        objective="Unblock disputed invoices so they can be collected.",
        kpis=["invoices_collected"],
        outcome_event="dispute_task_created",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_AR,
        task="Find long-overdue invoices with dispute signals and create a task for the account owner with the evidence.",
        evidence_steps=[
            tool_step("read-overdue", "Read overdue invoices", "capability.finance.invoices.read",
                      param_sources={"max_results": 200}),
        ],
        action_steps_after=[
            tool_step("dispute-task", "Create the owner's task", "capability.crm.task.create",
                      param_sources={"company_id": "$COMPANY_ID", "body": "$DISPUTE_NOTE"}),
        ],
        approvals=[{"when": "capability.crm.task.create", "required": True}],
        capability_groups=[["finance.invoices.read"], ["crm.task.create"]],
        required_connector_groups=[["quickbooks", "xero", "stripe", "netsuite"], ["hubspot", "salesforce"]],
        write_actions=[{"capability": "crm.task.create", "approval": "policy"}],
    ),
    play(
        "pre-due-reminder",
        "Pre-Due Payment Reminder",
        "Remind customers a few days before an invoice is due so fewer invoices become overdue.",
        objective="Reduce invoices that become overdue.",
        kpis=["invoices_collected"],
        outcome_event="collections_reminder_sent",
        trigger={"type": "scheduled", "cadence": "daily"},
        agent_seed=_SEED_AR,
        task="List invoices due in the next five days and draft one friendly reminder per customer for approval.",
        evidence_steps=[
            tool_step("read-upcoming", "Read invoices coming due", "capability.finance.invoices.read",
                      param_sources={"max_results": 200}),
        ],
        action_steps_after=[
            approval_step("approve-pre-due", "Approve pre-due reminder", "Emails the customer"),
            tool_step("send-pre-due", "Send the approved reminder", "capability.cs.customer.message",
                      param_sources={"to": "$CUSTOMER_EMAIL", "body": "$MESSAGE"}),
        ],
        capability_groups=[["finance.invoices.read"], ["cs.customer.message"]],
        required_connector_groups=[["quickbooks", "xero", "stripe", "netsuite"]],
        optional_connectors=["gmail", "intercom"],
        write_actions=[{"capability": "cs.customer.message", "approval": "always"}],
    ),
    play(
        "high-value-escalation",
        "High-Value Invoice Escalation",
        "Escalate large overdue invoices to the account owner with the payment history attached.",
        objective="Collect the largest overdue balances first.",
        kpis=["cash_collected", "invoices_collected"],
        outcome_event="collections_escalation_created",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_AR,
        task="Find overdue invoices above the escalation threshold and create a task for the account owner.",
        evidence_steps=[
            tool_step("read-large", "Read large overdue invoices", "capability.finance.invoices.read",
                      param_sources={"max_results": 200}),
        ],
        action_steps_after=[
            tool_step("escalation-task", "Create the escalation task", "capability.crm.task.create",
                      param_sources={"company_id": "$COMPANY_ID", "body": "$ESCALATION_NOTE"}),
        ],
        approvals=[{"when": "capability.crm.task.create", "required": True}],
        capability_groups=[["finance.invoices.read"], ["crm.task.create"]],
        required_connector_groups=[["quickbooks", "xero", "stripe", "netsuite"], ["hubspot", "salesforce"]],
        write_actions=[{"capability": "crm.task.create", "approval": "policy"}],
    ),
    play(
        "promise-to-pay-check",
        "Promise-to-Pay Check",
        "Check invoices where the customer promised a payment date and follow up when the date passes unpaid.",
        objective="Turn payment promises into collected invoices.",
        kpis=["invoices_collected", "cash_collected"],
        outcome_event="collections_reminder_sent",
        trigger={"type": "scheduled", "cadence": "daily"},
        agent_seed=_SEED_AR,
        task="Find invoices whose promised payment date has passed with a balance still open and draft a follow-up.",
        evidence_steps=[
            tool_step("read-promised", "Read invoices with payment promises", "capability.finance.invoices.read",
                      param_sources={"max_results": 200}),
        ],
        action_steps_after=[
            approval_step("approve-promise-followup", "Approve the follow-up", "Emails the customer"),
            tool_step("send-promise-followup", "Send the approved follow-up", "capability.cs.customer.message",
                      param_sources={"to": "$CUSTOMER_EMAIL", "body": "$MESSAGE"}),
        ],
        capability_groups=[["finance.invoices.read"], ["cs.customer.message"]],
        required_connector_groups=[["quickbooks", "xero", "stripe", "netsuite"]],
        optional_connectors=["gmail", "intercom"],
        write_actions=[{"capability": "cs.customer.message", "approval": "always"}],
    ),
    play(
        "payment-plan-followup",
        "Payment Plan Follow-up",
        "Offer an approved payment plan to customers with long-overdue balances and track each instalment.",
        objective="Recover long-overdue balances through payment plans.",
        kpis=["cash_collected"],
        outcome_event="payment_plan_offered",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_AR,
        task="Find invoices more than 60 days overdue and draft a payment-plan offer for approval.",
        evidence_steps=[
            tool_step("read-aged", "Read long-overdue invoices", "capability.finance.invoices.read",
                      param_sources={"max_results": 200}),
        ],
        action_steps_after=[
            approval_step("approve-plan-offer", "Approve payment-plan offer", "Emails the customer a payment plan"),
            tool_step("send-plan-offer", "Send the approved offer", "capability.cs.customer.message",
                      param_sources={"to": "$CUSTOMER_EMAIL", "body": "$MESSAGE"}),
        ],
        capability_groups=[["finance.invoices.read"], ["cs.customer.message"]],
        required_connector_groups=[["quickbooks", "xero", "stripe", "netsuite"]],
        optional_connectors=["gmail", "intercom"],
        write_actions=[{"capability": "cs.customer.message", "approval": "always"}],
    ),
]


def build() -> dict[str, Any]:
    config: dict[str, Any] = {
        "marketplace_version": "3.0",
        "pack_id": PACK_ID,
        "department": DEPARTMENT,
        "outcome_contract": {
            "problem": "Overdue invoices are chased by hand, late, and without a record of what worked.",
            "target_outcome": "Collect more overdue invoices, verified in the accounting system.",
            "baseline_metric": "invoices_collected",
            "success_criteria": [
                "An invoice counts only when accounting shows a zero open balance after follow-up.",
                "A sent reminder is an action, never a collected result.",
            ],
            "outcome_events": sorted({p["outcome_events"][0] for p in PLAYS}),
            "kpis": KPIS,
            "verification_required": True,
        },
        "objectives": [
            {"key": "improve-collections", "statement": "Improve collections and reduce overdue receivables",
             "kpi_keys": ["invoices_collected", "cash_collected"]},
        ],
        "agents": [
            {"seed_label": _SEED_AR, "name": "Accounts Receivable Specialist",
             "purpose": "Follow up on overdue invoices and unblock disputes.",
             "role": "Accounts Receivable", "department": "Finance",
             "capabilities": ["collections", "disputes"], "systems": ["quickbooks", "xero", "gmail"]},
        ],
        "plays": PLAYS,
        "knowledge": [
            {"seed_label": "collections-policy", "title": "Collections Policy", "type": "manual",
             "metadata": {"purpose": "Reminder cadence, tone, escalation and write-off rules."}},
        ],
        "dataset": {
            "entities": [
                {"name": "invoices", "source": "accounting_connector", "primary_key": "invoice_id",
                 "fields": ["invoice_id", "customer", "due_date", "balance", "total", "currency"]},
            ],
            "metrics": [
                {"key": row["key"], "label": row["label"], "formula": row["description"], "unit": row["unit"]}
                for row in KPIS
            ],
        },
        "dashboard": dashboard(
            title="Collections",
            template_id="finance-collections",
            department=DEPARTMENT,
            kpis=KPIS,
            sections=[{"title": "Collections", "kpi_keys": ["invoices_collected", "cash_collected"]}],
            system_health_kpis=["connector-health"],
        ),
        "runtime_profiles": [
            {"provider": "capability-resolved", "status": "tested", "actions": runtime_profile_actions(PLAYS)}
        ],
        "connector_alternatives": [["quickbooks", "xero", "stripe", "netsuite"], ["gmail", "intercom"], ["hubspot", "salesforce"]],
        "verification_recipes": RECIPES,
        "governance": {
            "always_approve_actions": ["gmail.messages.send", "intercom.conversations.reply"],
            "max_autonomy": "act_with_approval",
        },
        "certification": {
            "minimum_plays": 6,
            "fixtures": {
                "accounting-invoice-collection": {
                    "record_id": "inv-1042",
                    "current": {"invoice": {"Balance": 0, "TotalAmt": 1250.0, "CurrencyRef": {"value": "USD"}}},
                },
            },
            "degraded_scenarios": [
                {"capability": "finance.invoices.read", "unavailable_vendor": "quickbooks", "reason": "auth_expired"},
            ],
        },
    }
    return {
        "marketplace": {
            "slug": "finance-collections-operator",
            "title": "Collections Operator",
            "description": "Collect more overdue invoices with Plays verified in your accounting system.",
            "department_label": "Finance",
            "tags": ["finance", "collections", "receivables", "outcome-pack"],
            "price_cents": 0,
            "pricing_type": "free",
            "required_connectors": [
                {"connectorType": "quickbooks", "label": "QuickBooks", "required": True,
                 "connectPath": "/connectors?type=quickbooks",
                 "requirementNote": "Source of record for invoice balances."},
            ],
            "business_outcome": "Collect more overdue invoices.",
            "use_case": "Accounts receivable collections",
            "estimated_hours_saved": 10.0,
        },
        "config": config,
    }
