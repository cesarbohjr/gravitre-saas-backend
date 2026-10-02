"""Marketplace 3.0 department portfolio.

Each pack is outcome-first, measurable, and constrained to registered Gravitre
connector actions. Long-tail connectors may be listed as optional context, but
they are not represented as executable until a governed action contract exists.
"""
from __future__ import annotations

from typing import Any

from app.workflows.constants import SCHEMA_VERSION

SKILL_COMMIT = "fad068304bdff00b6807b36f249c6db36fff04e1"

SKILL_PACKS: dict[str, dict[str, Any]] = {
    "security-operations-skills": {
        "name": "Security Operations Skills",
        "skills": ["security-alert-triage","incident-assessment","identity-risk-analysis","vulnerability-prioritization","containment-planning","incident-communications","post-incident-review"],
        "content_digest": "sha256:af2b5da4b4956ca5b88df9c4ee1580f4da83c39bef4139c50ec9f56dc0828e84",
        "snapshot_digest": "sha256:1ef5b186214da3e1dc330d49d13ab7cd704cdae2e55b411e848f35f7cb0a9131",
    },
    "revenue-operations-skills": {
        "name": "Revenue Operations Skills",
        "skills": ["lead-qualification","account-research","meeting-prep","pipeline-risk-analysis","deal-recovery","forecast-integrity","renewal-expansion-analysis"],
        "content_digest": "sha256:12f545b2fc84f8f402ee198edb8c29a6856692b2a843807676c7a130b10e509a",
        "snapshot_digest": "sha256:97a23c99066956eb5f9821f168b6b2c9c7ba8eb745b6c1964774c91a669847ce",
    },
    "customer-success-skills": {
        "name": "Customer Success Skills",
        "skills": ["customer-health-analysis","churn-risk-analysis","escalation-recovery","qbr-preparation","renewal-readiness","expansion-signal-analysis","service-gap-analysis"],
        "content_digest": "sha256:1997e01cf259f764ce7652817bead78e468243d9a82d91bca794c488893ab0e1",
        "snapshot_digest": "sha256:064ad64981141d56baea40175bfffc6a36f27828a57a9401df42bf44b15b72d7",
    },
    "finance-operations-skills": {
        "name": "Finance Operations Skills",
        "skills": ["ar-prioritization","collections-analysis","cash-risk-analysis","invoice-exception-analysis","expense-anomaly-analysis","renewal-audit","month-end-readiness"],
        "content_digest": "sha256:ddc75c2e832612a2f03e77618bb781e8cf7f9e5fcc2282ffaab3d8ab2bb231a5",
        "snapshot_digest": "sha256:a1776e2e032e61eeb820144ea78807bfd41ee927d2c2fa3da83a7882ce681236",
    },
    "marketing-operations-skills": {
        "name": "Marketing Operations Skills",
        "skills": ["campaign-performance-analysis","attribution-analysis","lead-handoff-qa","paid-spend-anomaly-analysis","seo-opportunity-analysis","content-performance-analysis","pipeline-contribution-analysis"],
        "content_digest": "sha256:0fa09c70626d922233ddf7f6c5862f3737c4aae7b95d6dbfcdc00a0fcb36dc51",
        "snapshot_digest": "sha256:00cd20d3774fab53145d6eec118aa57040065bcc1052ba8d709335e646550dc0",
    },
    "people-it-operations-skills": {
        "name": "People and IT Operations Skills",
        "skills": ["onboarding-readiness","offboarding-readiness","policy-analysis","employee-request-triage","access-review","device-compliance-analysis","license-utilization-analysis"],
        "content_digest": "sha256:79015937faea99c684038e0e13cc8644dc498fb387d925446740b55a268f3f8d",
        "snapshot_digest": "sha256:30008e0167e13f189db21d769f7375614fdbba8835e24f0465e4ef7338737f00",
    },
    "executive-command-skills": {
        "name": "Executive Command Center Skills",
        "skills": ["executive-briefing","revenue-risk-analysis","cash-risk-analysis","customer-risk-analysis","service-risk-analysis","operational-anomaly-analysis","cross-functional-prioritization"],
        "content_digest": "sha256:58b5523aa3251877e57be11797c2f0f8aa18c316fcbd026d8c67d224510063a6",
        "snapshot_digest": "sha256:9a3e2d6c539b8049390f4d4d21d161208e0417427df6b4b1157a3bb24c4118e6",
    },
}


PACK_SPECS: dict[str, dict[str, Any]] = {
    "security-operations-3": {
        "title": "Security Operations 3.0", "department": "Security Operations",
        "skill_package": "security-operations-skills",
        "problem": "Security teams lose response time when alerts, service incidents, identity risk, vulnerability work, remediation, communications, and post-incident learning are fragmented.",
        "target": "Reduce detection, investigation, and coordination time while improving prioritized remediation, incident readiness, and measurable security operations.",
        "connectors": ["freshservice"],
        "optional": ["huntress","sentinelone","crowdstrike","connectsecure","okta","microsoft_intune"],
        "profiles": {"freshservice": ["freshservice.tickets.list","freshservice.tickets.get","freshservice.tickets.activities"]},
        "agents": [
            ("security-operations-coordinator","Security Operations Coordinator"),
            ("security-investigation-analyst","Security Investigation Analyst"),
            ("identity-risk-analyst","Identity Risk Analyst"),
            ("vulnerability-analyst","Vulnerability Analyst"),
            ("incident-commander","Incident Commander"),
        ],
        "kpis": [
            ("security_queue_age","Security queue age","minutes","decrease"),
            ("incident_context_time","Incident context time","minutes","decrease"),
            ("critical_workload","Critical security workload","count","decrease"),
            ("remediation_sla","Remediation SLA compliance","percent","increase"),
            ("escalation_rate","Security escalation rate","percent","decrease"),
            ("communication_latency","Incident communication latency","minutes","decrease"),
            ("post_incident_completion","Post-incident review completion","percent","increase"),
            ("remediation_follow_up_rate","Remediation follow-up completion","percent","increase"),
            ("security_posture_risk","Security posture risk","score","decrease"),
            ("security_mttr","Security mean time to resolution","minutes","decrease"),
            ("verified_security_outcomes","Verified security outcomes","count","increase"),
        ],
        "plays": [
            ("security-alert-triage","Security Alert Triage","Prioritize security-related service records by urgency, evidence quality, and business exposure.","freshservice.tickets.list","security_queue_age"),
            ("incident-context-builder","Incident Context Builder","Assemble verified service activity, affected assets, and incident history before investigation decisions.","freshservice.tickets.activities","incident_context_time"),
            ("identity-risk-review","Identity Risk Review","Surface identity-related service incidents requiring deeper security review and evidence collection.","freshservice.tickets.list","critical_workload"),
            ("vulnerability-work-queue","Vulnerability Work Queue","Prioritize vulnerability and remediation work represented in the governed service queue.","freshservice.tickets.list","remediation_sla"),
            ("containment-readiness-review","Containment Readiness Review","Prepare evidence, approvals, rollback considerations, and verification requirements before containment is attempted.","freshservice.tickets.get","escalation_rate"),
            ("remediation-follow-up","Remediation Follow-Up","Track open remediation commitments and identify items that require escalation or source-of-record re-verification.","freshservice.tickets.list","remediation_follow_up_rate"),
            ("incident-communications-brief","Incident Communications Brief","Prepare a verified internal incident status brief from current source records and known impact.","freshservice.tickets.get","communication_latency"),
            ("post-incident-review","Post-Incident Review","Produce a structured review of incident evidence, recurrence patterns, control gaps, and follow-up actions.","freshservice.tickets.activities","post_incident_completion"),
            ("security-posture-watch","Security Posture Watch","Review current security service workload and verified outcomes for deteriorating posture, recurring control gaps, and emerging operational risk.","freshservice.tickets.list","security_posture_risk"),
        ],
    },
    "revenue-operations-3": {
        "title": "Revenue Operations 3.0", "department": "Revenue Operations",
        "skill_package": "revenue-operations-skills",
        "problem": "Revenue teams lose pipeline when qualification, account context, deal risk, forecasting, and renewal signals are fragmented across CRM activity.",
        "target": "Increase qualified pipeline velocity and forecast integrity while reducing manual research and stale-deal administration.",
        "connectors": ["hubspot"], "optional": ["salesforce","gong","apollo","clay"],
        "profiles": {"hubspot": ["hubspot.contacts.search","hubspot.companies.search","hubspot.deals.get","hubspot.deals.search","hubspot.deals.list","hubspot.owners.list","hubspot.pipelines.list"]},
        "agents": [("revenue-intelligence-agent","Revenue Intelligence Agent"),("pipeline-analyst-agent","Pipeline Analyst Agent")],
        "kpis": [("speed_to_lead","Speed to lead","minutes","decrease"),("qualified_rate","Qualified lead rate","percent","increase"),("pipeline_coverage","Pipeline coverage","ratio","increase"),("stage_aging","Stage aging","days","decrease"),("deal_velocity","Deal velocity","days","decrease"),("forecast_integrity","Forecast integrity","percent","increase"),("renewal_risk","Renewal revenue at risk","currency","decrease")],
        "plays": [
            ("inbound-lead-qualifier","Inbound Lead Qualifier","Evaluate inbound CRM contacts against ICP and route the next recommended action.","hubspot.contacts.search","qualified_rate"),
            ("account-research-brief","Account Research Brief","Build a verified CRM-backed account briefing for active opportunities.","hubspot.companies.search","speed_to_lead"),
            ("meeting-prep-brief","Meeting Prep Brief","Prepare seller context using account and deal evidence before a customer meeting.","hubspot.deals.get","deal_velocity"),
            ("stale-deal-recovery","Stale Deal Recovery","Identify opportunities with weak momentum and explain the evidence behind recovery recommendations.","hubspot.deals.list","stage_aging"),
            ("pipeline-risk-review","Pipeline Risk Review","Detect pipeline risk using deal state, ownership, and stage evidence.","hubspot.deals.search","pipeline_coverage"),
            ("forecast-integrity-check","Forecast Integrity Check","Compare pipeline claims with current CRM evidence and stage distribution.","hubspot.pipelines.list","forecast_integrity"),
            ("renewal-expansion-watch","Renewal and Expansion Watch","Surface accounts that warrant renewal or expansion attention from CRM evidence.","hubspot.companies.search","renewal_risk"),
            ("post-meeting-follow-up-review","Post-Meeting Follow-Up Review","Review current deal evidence after customer meetings and prepare the highest-value next-step follow-up without sending it automatically.","hubspot.deals.get","deal_velocity"),
        ],
    },
    "customer-success-support-3": {
        "title": "Customer Success & Support 3.0", "department": "Customer Success",
        "skill_package": "customer-success-skills",
        "problem": "Customer teams react too late because CRM health, support friction, escalations, renewals, and expansion signals are reviewed separately.",
        "target": "Detect customer risk earlier, improve escalation recovery, and create a measurable renewal and service-health operating loop.",
        "connectors": ["hubspot","zendesk"], "optional": ["freshservice","front","intercom"],
        "profiles": {"hubspot": ["hubspot.companies.search","hubspot.deals.list"],"zendesk":["zendesk.tickets.list","zendesk.tickets.get","zendesk.users.get"]},
        "agents": [("customer-health-agent","Customer Health Agent"),("support-risk-analyst","Support Risk Analyst")],
        "kpis": [("account_health","Account health","score","increase"),("churn_risk","Churn risk","percent","decrease"),("escalation_age","Escalation age","hours","decrease"),("qbr_readiness","QBR readiness","percent","increase"),("renewal_readiness","Renewal readiness","percent","increase"),("expansion_signal_rate","Expansion signal rate","percent","increase"),("service_gap_rate","Service gap rate","percent","decrease")],
        "plays": [
            ("customer-health-watch","Customer Health Watch","Combine CRM and support evidence into a current customer-health view.","hubspot.companies.search","account_health"),
            ("churn-risk-detector","Churn Risk Detector","Identify accounts with credible retention risk using service and CRM evidence.","zendesk.tickets.list","churn_risk"),
            ("escalation-recovery-review","Escalation Recovery Review","Prioritize active support escalations and identify the next recovery step.","zendesk.tickets.get","escalation_age"),
            ("qbr-preparation","QBR Preparation","Assemble account, support, and commercial evidence for a customer business review.","hubspot.companies.search","qbr_readiness"),
            ("renewal-readiness-review","Renewal Readiness Review","Assess renewal readiness from account and deal evidence.","hubspot.deals.list","renewal_readiness"),
            ("expansion-signal-watch","Expansion Signal Watch","Find evidence-backed expansion signals without inventing intent.","hubspot.companies.search","expansion_signal_rate"),
            ("service-gap-detector","Service Gap Detector","Detect recurring customer-support gaps that should become process or knowledge improvements.","zendesk.tickets.list","service_gap_rate"),
            ("voice-of-customer-watch","Voice of Customer Watch","Aggregate verified support evidence into recurring customer themes, friction signals, and retention-relevant patterns.","zendesk.tickets.list","account_health"),
        ],
    },
    "finance-operations-3": {
        "title": "Finance Operations 3.0", "department": "Finance",
        "skill_package": "finance-operations-skills",
        "problem": "Finance teams spend excessive time manually reviewing receivables, cash exposure, invoice exceptions, vendor activity, renewals, and close readiness.",
        "target": "Improve cash visibility and collections prioritization while reducing manual finance review and month-end surprises.",
        "connectors": ["quickbooks","stripe"], "optional": ["xero","sage_intacct","ramp","brex","chargebee"],
        "profiles": {"quickbooks":["quickbooks.invoices.list","quickbooks.invoices.get","quickbooks.customers.list","quickbooks.vendors.list","quickbooks.accounts.list","quickbooks.payments.list"],"stripe":["stripe.invoices.list","stripe.subscriptions.get","stripe.customers.get"]},
        "agents": [("finance-operations-agent","Finance Operations Agent"),("cash-risk-analyst","Cash Risk Analyst")],
        "kpis": [("dso","Days sales outstanding","days","decrease"),("overdue_ar","Overdue receivables","currency","decrease"),("cash_risk","Cash risk","currency","decrease"),("invoice_exception_rate","Invoice exception rate","percent","decrease"),("vendor_exception_rate","Vendor exception rate","percent","decrease"),("renewal_exposure","Renewal exposure","currency","decrease"),("close_readiness","Month-end close readiness","percent","increase")],
        "plays": [
            ("ar-priority-review","AR Priority Review","Prioritize receivables using invoice and customer evidence.","quickbooks.invoices.list","dso"),
            ("collections-strategy-brief","Collections Strategy Brief","Prepare evidence-backed collections priorities without sending customer communications automatically.","quickbooks.invoices.get","overdue_ar"),
            ("cash-risk-watch","Cash Risk Watch","Monitor receivables and payments for near-term cash exposure.","quickbooks.payments.list","cash_risk"),
            ("invoice-exception-review","Invoice Exception Review","Identify invoice records requiring human reconciliation or correction.","quickbooks.invoices.list","invoice_exception_rate"),
            ("vendor-exception-review","Vendor Exception Review","Review vendor and account evidence for unusual or incomplete finance records.","quickbooks.vendors.list","vendor_exception_rate"),
            ("renewal-exposure-watch","Renewal Exposure Watch","Review subscription evidence for upcoming commercial exposure.","stripe.subscriptions.get","renewal_exposure"),
            ("month-end-readiness","Month-End Readiness","Assess close readiness from account, payment, and invoice evidence.","quickbooks.accounts.list","close_readiness"),
            ("revenue-leak-hunter","Revenue Leak Hunter","Identify recoverable revenue hidden in overdue invoices, billing exceptions, stalled collections, and subscription exposure using verified finance evidence.","quickbooks.invoices.list","overdue_ar"),
        ],
    },
    "marketing-operations-3": {
        "title": "Marketing Operations 3.0", "department": "Marketing",
        "skill_package": "marketing-operations-skills",
        "problem": "Marketing teams struggle to connect campaign activity, lead quality, funnel movement, content engagement, and downstream pipeline contribution.",
        "target": "Improve campaign and funnel performance using measurable CRM evidence while keeping paid-media and analytics connectors optional until their governed runtime actions are executable.",
        "connectors": ["hubspot"], "optional": ["google_analytics","google_ads","google_search_console","semrush","ahrefs"],
        "profiles": {"hubspot":["hubspot.contacts.list","hubspot.campaigns.list","hubspot.deals.list","hubspot.pipelines.list"]},
        "agents": [("marketing-performance-agent","Marketing Performance Agent"),("growth-operations-analyst","Growth Operations Analyst")],
        "kpis": [("campaign_engagement_signal","Campaign engagement signal","score","increase"),("lead_flow_health","Lead flow health","score","increase"),("mql_to_sql","MQL to SQL conversion","percent","increase"),("attribution_confidence","Attribution confidence","percent","increase"),("campaign_anomaly_rate","Campaign anomaly rate","percent","decrease"),("content_velocity","Content performance velocity","score","increase"),("pipeline_contribution","Marketing pipeline contribution","currency","increase")],
        "plays": [
            ("campaign-performance-review","Campaign Performance Review","Assess current campaign activity and engagement evidence from the connected marketing CRM.","hubspot.campaigns.list","campaign_engagement_signal"),
            ("attribution-integrity-check","Attribution Integrity Check","Compare campaign, contact, and pipeline evidence to identify attribution gaps without inventing unsupported channel data.","hubspot.deals.list","attribution_confidence"),
            ("lead-handoff-qa","Lead Handoff QA","Review recent CRM contacts for measurable marketing-to-sales handoff quality.","hubspot.contacts.list","mql_to_sql"),
            ("campaign-anomaly-watch","Campaign Anomaly Watch","Detect unusual campaign activity or engagement deterioration in the currently governed CRM evidence.","hubspot.campaigns.list","campaign_anomaly_rate"),
            ("audience-opportunity-review","Audience Opportunity Review","Analyze recent contact evidence for audience and segmentation opportunities.","hubspot.contacts.list","lead_flow_health"),
            ("content-performance-review","Content Performance Review","Use campaign evidence to identify content or messaging programs that are accelerating or decaying.","hubspot.campaigns.list","content_velocity"),
            ("pipeline-contribution-review","Pipeline Contribution Review","Connect current campaign and CRM evidence to downstream pipeline contribution.","hubspot.deals.list","pipeline_contribution"),
            ("lifecycle-conversion-review","Lifecycle Conversion Review","Analyze pipeline-stage and contact evidence to find conversion leakage between marketing qualification and sales progression.","hubspot.pipelines.list","mql_to_sql"),
        ],
    },
    "people-it-operations-3": {
        "title": "People & IT Operations 3.0", "department": "People & IT Operations",
        "skill_package": "people-it-operations-skills",
        "problem": "Employee lifecycle and IT service work become fragmented across HR records, onboarding, service requests, access checks, and device/support queues.",
        "target": "Improve employee onboarding and service readiness while reducing incomplete requests, access gaps, and manual coordination.",
        "connectors": ["bamboohr","freshservice"], "optional": ["rippling","hibob","okta","jumpcloud","microsoft_intune","jamf_pro"],
        "profiles": {"bamboohr":["bamboohr.employees.list","bamboohr.employees.get","bamboohr.timeoff.requests.list"],"freshservice":["freshservice.tickets.list","freshservice.tickets.get"]},
        "agents": [("employee-operations-agent","Employee Operations Agent"),("it-service-readiness-agent","IT Service Readiness Agent")],
        "kpis": [("onboarding_readiness","Onboarding readiness","percent","increase"),("offboarding_readiness","Offboarding readiness","percent","increase"),("policy_request_age","Policy request age","hours","decrease"),("employee_request_age","Employee request age","hours","decrease"),("access_review_gap","Access review gap","percent","decrease"),("device_service_risk","Device/service risk","count","decrease"),("license_review_gap","License review gap","percent","decrease")],
        "plays": [
            ("onboarding-readiness-review","Onboarding Readiness Review","Check employee and service evidence for onboarding blockers before start date.","bamboohr.employees.list","onboarding_readiness"),
            ("offboarding-readiness-review","Offboarding Readiness Review","Identify employee exits that require coordinated access and service follow-up.","bamboohr.employees.list","offboarding_readiness"),
            ("policy-request-triage","Policy Request Triage","Prioritize people-policy related service requests using verified ticket context.","freshservice.tickets.list","policy_request_age"),
            ("employee-request-triage","Employee Request Triage","Analyze employee service requests and route attention to the highest-impact blockers.","freshservice.tickets.get","employee_request_age"),
            ("access-review-watch","Access Review Watch","Surface workforce records and service requests that indicate access-review gaps.","bamboohr.employees.get","access_review_gap"),
            ("device-service-risk-review","Device & Service Risk Review","Identify service records that may block employee productivity or device readiness.","freshservice.tickets.list","device_service_risk"),
            ("license-utilization-review","License Utilization Review","Prepare a workforce-based review of likely license allocation and deprovisioning needs.","bamboohr.employees.list","license_review_gap"),
            ("service-request-bottleneck-review","Service Request Bottleneck Review","Identify recurring employee-service bottlenecks, aging requests, and coordination delays using verified service records.","freshservice.tickets.list","employee_request_age"),
        ],
    },
    "executive-command-center-3": {
        "title": "Executive Command Center 3.0", "department": "Executive",
        "skill_package": "executive-command-skills",
        "problem": "Executives receive fragmented dashboards after problems occur rather than one evidence-backed view of cross-functional risk, action, and opportunity.",
        "target": "Create a daily operating view of revenue, cash, customers, service, marketing, and cross-functional priorities tied to verified source evidence.",
        "connectors": ["hubspot","quickbooks","zendesk"], "optional": ["salesforce","stripe","freshservice","slack","google_analytics"],
        "profiles": {"hubspot":["hubspot.deals.list","hubspot.companies.search","hubspot.campaigns.list"],"quickbooks":["quickbooks.invoices.list","quickbooks.payments.list"],"zendesk":["zendesk.tickets.list"]},
        "agents": [("executive-intelligence-agent","Executive Intelligence Agent"),("cross-functional-risk-analyst","Cross-Functional Risk Analyst")],
        "kpis": [("revenue_risk","Revenue at risk","currency","decrease"),("cash_risk","Cash risk","currency","decrease"),("customer_risk","Customer risk","score","decrease"),("service_risk","Service risk","score","decrease"),("marketing_signal","Marketing performance signal","score","increase"),("operational_anomalies","Operational anomalies","count","decrease"),("priority_resolution","Priority resolution rate","percent","increase")],
        "plays": [
            ("executive-morning-brief","Executive Morning Brief","Summarize the material operating changes requiring executive attention.","hubspot.deals.list","revenue_risk"),
            ("revenue-risk-watch","Revenue Risk Watch","Surface current pipeline and account evidence that threatens revenue.","hubspot.companies.search","revenue_risk"),
            ("cash-risk-watch-executive","Cash Risk Watch","Surface receivables and payment evidence that may affect near-term cash.","quickbooks.invoices.list","cash_risk"),
            ("customer-risk-watch-executive","Customer Risk Watch","Summarize current customer-support risk from service evidence.","zendesk.tickets.list","customer_risk"),
            ("service-risk-watch","Service Risk Watch","Identify service workload signals that warrant leadership attention.","zendesk.tickets.list","service_risk"),
            ("marketing-signal-watch","Marketing Signal Watch","Summarize material demand and engagement changes from governed campaign evidence.","hubspot.campaigns.list","marketing_signal"),
            ("cross-functional-priority-review","Cross-Functional Priority Review","Rank the most material cross-functional issues and assign decision urgency.","quickbooks.payments.list","priority_resolution"),
            ("operational-anomaly-watch","Operational Anomaly Watch","Surface unusual cross-functional operating signals that deserve executive attention before they become larger business problems.","zendesk.tickets.list","operational_anomalies"),
        ],
    },
}


def _tool_step(step_id: str, action: str, connector: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": action.replace(".", " ").replace("_", " ").title(),
        "type": "invoke_tool",
        "config": {
            "action": action,
            "tool_action": action,
            "vendor": connector,
            "connector": connector,
            "selectedAction": action.split(".", 1)[-1],
            "selected_action": action.split(".", 1)[-1],
        },
        "requires_connector": connector,
    }


def _agent_step(step_id: str, seed: str, task: str) -> dict[str, Any]:
    return {"id": step_id, "name": "Analyze evidence", "type": "agent", "metadata": {"agent_seed": seed, "task": task}}


def _connector_for_action(action: str) -> str:
    return action.split(".", 1)[0]


def build_department_outcome_pack_config(slug: str) -> dict[str, Any]:
    spec = PACK_SPECS[slug]
    skill_slug = spec["skill_package"]
    skill_requirements = list(SKILL_PACKS[skill_slug]["skills"])
    agent_seeds = [f"agent:{key}" for key, _ in spec["agents"]]
    kpis = [
        {"key": key, "label": label, "unit": unit, "direction": direction, "source": "verified_department_dataset"}
        for key, label, unit, direction in spec["kpis"]
    ]
    plays = []
    for index, (key, name, desc, action, kpi_key) in enumerate(spec["plays"]):
        agent_seed = agent_seeds[index % len(agent_seeds)]
        plays.append({
            "key": key,
            "name": name,
            "description": desc,
            "trigger": {"type": "scheduled", "cadence": "daily"} if index else {"type": "scheduled", "cadence": "hourly"},
            "workflow_steps": [
                _tool_step(f"{key}-evidence", action, _connector_for_action(action)),
                _agent_step(f"{key}-analysis", agent_seed, f"{desc} Use only connector evidence; distinguish facts, inference, and missing data."),
            ],
            "outcome_events": [f"{key.replace('-', '_')}_reviewed"],
            "kpi_keys": [kpi_key],
            "approvals": [],
            "verification": {"mode": "source_of_record", "provider_acceptance_is_terminal": False},
            "runtime_inputs": [],
        })

    profiles = [
        {"provider": provider, "status": "tested", "actions": actions}
        for provider, actions in spec["profiles"].items()
    ]
    agents = [
        {
            "seed_label": f"agent:{key}",
            "name": name,
            "purpose": f"Operate {spec['department']} evidence review and measurable decision support.",
            "role": name,
            "department": spec["department"],
            "capabilities": skill_requirements,
            "systems": list(spec["connectors"] + spec["optional"]),
        }
        for key, name in spec["agents"]
    ]
    knowledge = [
        {"seed_label": f"{slug}:policy", "title": f"{spec['title']} Policy & SOP", "type": "manual", "metadata": {"purpose": "Department policy, thresholds, approvals, and SOPs."}},
        {"seed_label": f"{slug}:playbook", "title": f"{spec['title']} Operating Playbook", "type": "manual", "metadata": {"purpose": "Operating definitions, escalation rules, and decision guidance."}},
    ]
    dataset = {
        "entities": [
            {"name": "department_records", "source": "connected_systems", "primary_key": "record_id", "fields": ["record_id","account_id","status","owner","created_at","updated_at"]},
            {"name": "verified_outcomes", "source": "gravitre_verified_outcomes", "primary_key": "outcome_id", "fields": ["outcome_id","play_key","status","verified_at","metric_delta"]},
        ],
        "metrics": [{"key": key, "label": label, "formula": f"verified_metric('{key}')", "unit": unit} for key, label, unit, _ in spec["kpis"]],
    }
    dashboard = {
        "title": f"{spec['title']} Command Center",
        "refresh_mode": "event",
        "metrics": [
            {"kpi_key": key, "label": label, "visualization": "trend" if unit not in {"count","currency"} else "metric", "description": f"Verified Marketplace 3.0 KPI: {label}."}
            for key, label, unit, _ in spec["kpis"]
        ],
    }
    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": spec["problem"],
            "target_outcome": spec["target"],
            "baseline_metric": spec["kpis"][0][0],
            "success_criteria": [
                "All included Plays install into Gravitre's canonical Play/workflow runtime.",
                "Every Play reads only registered source-of-record actions in the tested/governed v1 profile.",
                "Every declared KPI is represented in the installed dashboard and normalized dataset.",
                "At least one declared outcome event must be measured before Outcome Verified status is earned.",
            ],
            "outcome_events": [f"{key.replace('-', '_')}_reviewed" for key, *_ in spec["plays"]],
            "kpis": kpis,
            "verification_required": True,
        },
        "agents": agents,
        "plays": plays,
        "knowledge": knowledge,
        "dataset": dataset,
        "dashboard": dashboard,
        "skills": [skill_slug],
        "skill_requirements": skill_requirements,
        "skill_bindings": {skill: skill_slug for skill in skill_requirements},
        "runtime_profiles": profiles,
        "connector_alternatives": [[name] for name in spec["connectors"]] + [[name for name in spec["optional"]]],
    }


def build_department_skill_package_config(slug: str) -> dict[str, Any]:
    spec = SKILL_PACKS[slug]
    manifest = {
        "schema": "gravitre.capability.v1",
        "format": "gravitre",
        "name": spec["name"],
        "version": "1.0.0",
        "description": f"First-party guidance skills for the Gravitre Marketplace 3.0 {spec['name'].replace(' Skills','')} pack.",
        "license": "MIT",
        "skills": [{"name": skill} for skill in spec["skills"]],
        "permissions": [],
    }
    skill_md = (
        f"---\nname: {spec['name']}\ndescription: First-party Gravitre guidance skills for Marketplace 3.0.\nlicense: MIT\n---\n\n"
        f"# {spec['name']}\n\nReviewed guidance-only capabilities:\n"
        + "\n".join(f"- {skill}" for skill in spec["skills"])
        + "\n\nThese skills do not own execution authority. Connector actions, approvals, source-of-record verification, Runs, and outcome truth remain owned by Gravitre's canonical runtime.\n"
    )
    return {
        "provenance_mode": "git_pinned",
        "repository_url": "https://github.com/cesarbohjr/gravitre-saas-backend",
        "commit_sha": SKILL_COMMIT,
        "package_path": f"capability_packages/{slug}",
        "content_digest": spec["content_digest"],
        "snapshot_digest": spec["snapshot_digest"],
        "manifest": manifest,
        "resources": [{"path": "SKILL.md", "kind": "reference", "content": skill_md, "executable": False}],
        "package_format": "gravitre",
        "license": "MIT",
        "license_policy": "allow",
        "risk_level": "low",
        "signature_status": "unsigned",
        "publisher_name": "Gravitre",
        "publisher_trust_scope": "none",
        "security_scan": {"risk": "low", "blocked": False, "findings": [], "executionPerformed": False},
    }


def department_portfolio_marketplace3_assets() -> list[Any]:
    from app.marketplace.seed_catalog import CatalogAsset

    assets: list[Any] = []
    for slug, spec in PACK_SPECS.items():
        if slug == "security-operations-3":
            from app.marketplace.marketplace3.security_operations import (
                security_operations_marketplace3_assets,
            )
            assets.extend(security_operations_marketplace3_assets())
            continue
        config = build_department_outcome_pack_config(slug)
        connector_defs = [
            {
                "connectorType": name,
                "label": name.replace("_", " ").title(),
                "required": True,
                "connectPath": f"/connectors?type={name}",
                "requirementNote": (
                    "Tested/governed Marketplace 3.0 runtime. Production verification "
                    "requires evidence-linked live source-of-record proof."
                ),
            }
            for name in spec["connectors"]
        ]
        agent_assets = [
            CatalogAsset(
                slug=f"{slug}-{str(agent['seed_label']).split(':')[-1]}",
                title=str(agent["name"]),
                description=str(agent["purpose"]),
                asset_type="ai_agent",
                category="ai_agent",
                department=spec["department"],
                visibility="internal",
                status="draft",
                tags=["marketplace-3","agent",slug],
                config=agent,
                required_connectors=connector_defs,
            )
            for agent in config["agents"]
        ]
        play_assets = [
            CatalogAsset(
                slug=f"{slug}-play-{play['key']}",
                title=str(play["name"]),
                description=str(play["description"]),
                asset_type="play",
                category="play",
                department=spec["department"],
                visibility="internal",
                status="draft",
                tags=["marketplace-3","play",slug],
                config=play,
                required_connectors=connector_defs,
                business_outcome=str(play["outcome_events"][0]),
                use_case=str(play["description"]),
            )
            for play in config["plays"]
        ]
        skill_slug = spec["skill_package"]
        skill_asset = CatalogAsset(
            slug=skill_slug,
            title=SKILL_PACKS[skill_slug]["name"],
            description=f"Reviewed first-party guidance skills for {spec['title']}.",
            asset_type="capability_package",
            category="capability_package",
            department=spec["department"],
            visibility="internal",
            status="draft",
            tags=["marketplace-3","skills",slug],
            config=build_department_skill_package_config(skill_slug),
        )
        knowledge = CatalogAsset(
            slug=f"{slug}-knowledge", title=f"{spec['title']} Knowledge",
            description=f"Policy, SOP, and operating knowledge for {spec['title']}.",
            asset_type="knowledge_pack", category="knowledge_pack", department=spec["department"],
            visibility="internal", status="draft",
            tags=["marketplace-3","knowledge",slug], config={"documents": config["knowledge"]},
        )
        dataset = CatalogAsset(
            slug=f"{slug}-dataset", title=f"{spec['title']} Dataset",
            description=f"Normalized records and KPI definitions for {spec['title']}.",
            asset_type="dataset_pack", category="dataset_pack", department=spec["department"],
            visibility="internal", status="draft",
            tags=["marketplace-3","dataset",slug], config=config["dataset"], required_connectors=connector_defs,
        )
        dashboard = CatalogAsset(
            slug=f"{slug}-dashboard", title=f"{spec['title']} Command Center",
            description=f"Outcome dashboard for {spec['title']}.",
            asset_type="dashboard_pack", category="dashboard_pack", department=spec["department"],
            visibility="internal", status="draft",
            tags=["marketplace-3","dashboard",slug], config=config["dashboard"],
        )
        child_slugs = [a.slug for a in agent_assets] + [p.slug for p in play_assets] + [skill_asset.slug, knowledge.slug, dataset.slug, dashboard.slug]
        outcome = CatalogAsset(
            slug=slug, title=spec["title"], description=spec["target"],
            asset_type="outcome_pack", category="outcome_pack", department=spec["department"],
            visibility="internal", status="draft",
            tags=["marketplace-3","outcome-pack",slug],
            config=config, required_connectors=connector_defs, pack_children=child_slugs,
            business_outcome=spec["target"], use_case=spec["department"], pricing_type="paid",
            price_cents=14900, pack_tier=3, estimated_hours_saved=24.0,
        )
        assets.extend(agent_assets + play_assets + [skill_asset, knowledge, dataset, dashboard, outcome])
    return assets
