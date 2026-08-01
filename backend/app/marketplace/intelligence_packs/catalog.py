"""Marketplace intelligence packs — installable domain knowledge assignments."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.marketplace.workflows.pack_workflows import (
    build_ai_search_workflow_steps,
    build_cs_workflow_steps,
    build_executive_workflow_steps,
    build_finance_workflow_steps,
    build_hr_workflow_steps,
    build_marketing_workflow_steps,
    build_msp_workflow_steps,
    build_platform_health_workflow_steps,
    build_prospecting_workflow_steps,
    build_revops_workflow_steps,
    build_sales_workflow_steps,
    build_support_workflow_steps,
)


@dataclass(frozen=True)
class IntelligencePackAssignment:
    source_type: str
    source_id: str
    label: str
    department: str
    subdomain: str | None = None
    confidence_weight: float = 1.0
    reference_summary: str = ""
    external_url: str | None = None


@dataclass(frozen=True)
class IntelligencePackSpec:
    pack_id: str
    name: str
    department: str
    default_subdomain: str | None
    description: str
    marketplace_tags: list[str] = field(default_factory=list)
    tier: str = "starter"
    assignments: list[IntelligencePackAssignment] = field(default_factory=list)
    # Optional demo bundle (Executive pack): create agent + workflow + stage connectors
    demo_agent_name: str | None = None
    demo_systems: list[str] = field(default_factory=list)
    connector_template_id: str | None = None
    workflow_name: str | None = None
    workflow_description: str | None = None
    workflow_steps: list[dict[str, Any]] = field(default_factory=list)


def list_intelligence_pack_specs() -> list[IntelligencePackSpec]:
    return [
        IntelligencePackSpec(
            pack_id="marketing-intelligence-pack",
            name="Marketing Intelligence Pack",
            department="marketing",
            default_subdomain="content_marketing",
            description=(
                "Brand, campaign, HubSpot, GA4, Google Search Console, and creative knowledge. "
                "GSC page/URL aggregates may feed pack signals; raw search-query strings are "
                "gated from Memory/KG (STA-312 pattern). SEMrush/Ahrefs/People Data Labs are BYO "
                "API keys only (no shared Gravitree key)."
            ),
            marketplace_tags=["marketing", "starter", "intelligence-pack", "seo"],
            assignments=[
                IntelligencePackAssignment("google_drive_folder", "brand-guidelines", "Brand Guidelines", "marketing", "brand_marketing", reference_summary="Brand voice, visual standards, and messaging guardrails."),
                IntelligencePackAssignment("google_drive_folder", "campaign-playbooks", "Campaign Playbooks", "marketing", "content_marketing", reference_summary="Approved campaign templates and launch checklists."),
                IntelligencePackAssignment(
                    "hubspot_object",
                    "marketing-campaigns",
                    "HubSpot Campaigns",
                    "marketing",
                    "demand_generation",
                    reference_summary="HubSpot campaign/CRM objects for demand-gen briefings (read-only).",
                ),
                IntelligencePackAssignment(
                    "ga4_property",
                    "ga4-property",
                    "GA4 Property",
                    "marketing",
                    "analytics",
                    reference_summary="GA4 property analytics references.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "gsc-site",
                    "Google Search Console Site",
                    "marketing",
                    "analytics",
                    reference_summary=(
                        "Search performance page aggregates via searchconsole.searchAnalytics.query. "
                        "Raw query strings gated from Memory/KG."
                    ),
                ),
                IntelligencePackAssignment(
                    "canva_folder",
                    "brand-assets",
                    "Canva Brand Assets",
                    "marketing",
                    "brand_marketing",
                    reference_summary="Canva brand asset folder references.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "pdl-company-enrichment",
                    "People Data Labs Company Enrichment",
                    "marketing",
                    "analytics",
                    reference_summary=(
                        "BYO PDL company enrich via pdl.company.enrich "
                        "(https://dashboard.peopledatalabs.com/). "
                        "Contact-level Memory/KG writes remain STA-312 gated."
                    ),
                    external_url="https://dashboard.peopledatalabs.com/",
                ),
            ],
            demo_agent_name="SEO Marketing Analyst",
            demo_systems=["google_search_console", "google_analytics", "hubspot"],
            connector_template_id="marketing-intelligence-sources",
            workflow_name="Marketing GSC Site Snapshot",
            workflow_description=(
                "Agent brief → list Google Search Console sites → agent summary. "
                "Page aggregates may feed PackSignal; raw query strings stay Memory/KG gated."
            ),
            workflow_steps=build_marketing_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="revops-intelligence-pack",
            name="RevOps Intelligence Pack",
            department="sales",
            default_subdomain="revenue_operations",
            description=(
                "Revenue operations rollup across Sales + Marketing + CS CRM signals. "
                "Reuses HubSpot/Salesforce connectors; heuristic forecasting OK. "
                "Finance pack F3 unlocked (QB + Xero + NetSuite + Plaid if entitled) — "
                "install finance-intelligence-pack for Cash Flow Analyst; RevOps stays CRM-only."
            ),
            marketplace_tags=["revops", "starter", "intelligence-pack", "revenue"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "hubspot-pipeline",
                    "HubSpot Pipeline",
                    "sales",
                    "revenue_operations",
                    reference_summary="Customer HubSpot CRM pipelines for RevOps rollups (read-only).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "stage-definitions",
                    "Stage Definitions",
                    "sales",
                    "revenue_operations",
                    reference_summary="Shared funnel stage definitions across Sales/Marketing/CS.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "forecast-rollup",
                    "Forecast Rollup",
                    "sales",
                    "forecasting",
                    reference_summary="Heuristic revenue forecast rollup references (ML deferred).",
                ),
            ],
            demo_agent_name="Revenue Operations Analyst",
            demo_systems=["hubspot"],
            connector_template_id="revops-intelligence-sources",
            workflow_name="RevOps HubSpot Pipeline Snapshot",
            workflow_description="Agent brief → HubSpot pipelines.list → agent RevOps summary.",
            workflow_steps=build_revops_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="ai-search-intelligence-pack",
            name="AI Search Intelligence Pack",
            department="marketing",
            default_subdomain="ai_visibility",
            description=(
                "Answer-engine visibility (path C + S2): Ahrefs Brand Radar + Finseo dual BYO "
                "(use whichever is connected), plus ai_visibility_ui consumer-UI scrape v1–v3. "
                "Raw AI answer text Memory/KG gated; LinkedIn scrape forbidden."
            ),
            marketplace_tags=["ai-search", "starter", "intelligence-pack", "geo", "brand-radar"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "ahrefs-brand-radar",
                    "Ahrefs Brand Radar",
                    "marketing",
                    "ai_visibility",
                    reference_summary=(
                        "BYO Ahrefs Brand Radar overview via ahrefs.brand_radar.overview "
                        "(impressions/mentions/SoV across ChatGPT, Gemini, Perplexity, Copilot, Claude, Grok)."
                    ),
                    external_url="https://docs.ahrefs.com/api/reference/brand-radar",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "finseo-ai-metrics",
                    "Finseo AI Visibility",
                    "marketing",
                    "ai_visibility",
                    reference_summary=(
                        "BYO Finseo metrics/prompts via finseo.metrics.overview "
                        "(https://www.finseo.ai/developers/api)."
                    ),
                    external_url="https://www.finseo.ai/developers/api",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "ai-visibility-ui-scrape",
                    "AI Visibility UI Scrape",
                    "marketing",
                    "ai_visibility",
                    reference_summary=(
                        "S2 consumer-UI capture (ChatGPT/Perplexity/Gemini/Copilot/Claude) via "
                        "ai_visibility_ui.mentions.check — provenance required; raw answers Memory/KG blocked."
                    ),
                ),
            ],
            demo_agent_name="AI Visibility Analyst",
            demo_systems=["ahrefs", "finseo", "ai_visibility_ui"],
            connector_template_id="ai-search-intelligence-sources",
            workflow_name="AI Search Brand Radar Overview",
            workflow_description=(
                "Agent brief → Ahrefs Brand Radar overview → agent summary. "
                "Finseo / UI scrape available when those connectors are connected."
            ),
            workflow_steps=build_ai_search_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="finance-intelligence-pack",
            name="Finance Intelligence Pack",
            department="finance",
            default_subdomain="cash_flow",
            description=(
                "Finance pack F3: QuickBooks + Xero + NetSuite + Plaid (if entitled). "
                "Cash Flow Analyst demo agent; read-only accounting/banking tip. "
                "Raw payroll/banking → Memory/KG blocked; reuse existing connectors when active."
            ),
            marketplace_tags=["finance", "starter", "intelligence-pack", "cash-flow"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "quickbooks-company",
                    "QuickBooks Company",
                    "finance",
                    "cash_flow",
                    reference_summary="Customer QuickBooks company info / invoices (read-only).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "xero-ledger",
                    "Xero Ledger",
                    "finance",
                    "cash_flow",
                    reference_summary="Customer Xero contacts/invoices/accounts (read-only).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "netsuite-erp",
                    "NetSuite ERP",
                    "finance",
                    "cash_flow",
                    reference_summary="Customer NetSuite invoices/customers (read-only).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "plaid-balances",
                    "Plaid Balances",
                    "finance",
                    "cash_flow",
                    reference_summary=(
                        "Plaid accounts/balances/transactions if entitled — "
                        "requires public_token exchange; not generic OAuth."
                    ),
                ),
            ],
            demo_agent_name="Cash Flow Analyst",
            demo_systems=["quickbooks", "xero", "netsuite", "plaid"],
            connector_template_id="finance-intelligence-sources",
            workflow_name="Finance QuickBooks Company Snapshot",
            workflow_description=(
                "Agent brief → QuickBooks company info → agent cash-flow summary."
            ),
            workflow_steps=build_finance_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="hr-talent-intelligence-pack",
            name="HR & Talent Intelligence Pack",
            department="hr",
            default_subdomain="recruiting",
            description=(
                "HR pack H3: Workday + BambooHR + Greenhouse + Gusto. "
                "Recruiting Talent Analyst demo agent; Greenhouse jobs tip. "
                "Employee/compensation PII → Memory/KG blocked; no LinkedIn scrape; "
                "Gusto remains partner-OAuth gated until connected."
            ),
            marketplace_tags=["hr", "talent", "starter", "intelligence-pack", "recruiting"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "greenhouse-jobs",
                    "Greenhouse Jobs",
                    "hr",
                    "recruiting",
                    reference_summary="Open jobs via greenhouse.jobs.list (read-only ATS).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "workday-workers",
                    "Workday Workers",
                    "hr",
                    "workforce",
                    reference_summary="Workday workers/org units (read-only HRIS).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "bamboohr-employees",
                    "BambooHR Employees",
                    "hr",
                    "workforce",
                    reference_summary="BambooHR employee directory (read-only; PII Memory/KG gated).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "gusto-payroll",
                    "Gusto Payroll",
                    "hr",
                    "payroll",
                    reference_summary=(
                        "Gusto companies/employees/payrolls when partner OAuth connected; "
                        "compensation Memory/KG blocked."
                    ),
                ),
            ],
            demo_agent_name="Recruiting Talent Analyst",
            demo_systems=["workday", "bamboohr", "greenhouse", "gusto"],
            connector_template_id="hr-talent-intelligence-sources",
            workflow_name="HR Greenhouse Jobs Snapshot",
            workflow_description="Agent brief → Greenhouse jobs.list → agent recruiting summary.",
            workflow_steps=build_hr_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="sales-intelligence-pack",
            name="Sales Intelligence Pack",
            department="sales",
            default_subdomain="pipeline_management",
            description=(
                "Customer CRM pipeline intelligence: HubSpot read-only snapshot workflow, "
                "Sales Pipeline Analyst agent, HubSpot/Apollo stubs. "
                "Apollo company/contact discovery requires your own Apollo plan with search API access "
                "(BYO-tier — same transparency as ZoomInfo / LinkedIn Sales Navigator). "
                "HubSpot pipeline reads work without Apollo search. "
                "People Data Labs is BYO API key (dashboard.peopledatalabs.com); "
                "contact-level Memory/KG writes remain gated. CIS/hiring deferred."
            ),
            marketplace_tags=["sales", "starter", "intelligence-pack", "crm"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "hubspot-pipeline",
                    "HubSpot Pipeline",
                    "sales",
                    "pipeline_management",
                    reference_summary="Customer HubSpot CRM pipelines via hubspot.pipelines.list (read-only demo).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "sales-playbooks",
                    "Sales Playbooks",
                    "sales",
                    "enterprise_sales",
                    reference_summary="Curated sales playbook knowledge for pipeline reviews.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "forecast-reports",
                    "Forecast Reports",
                    "sales",
                    "forecasting",
                    reference_summary="Forecast report references for sales ops (customer docs).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "pdl-account-enrichment",
                    "People Data Labs Account Enrichment",
                    "sales",
                    "enterprise_sales",
                    reference_summary=(
                        "BYO People Data Labs person/company enrich "
                        "(https://dashboard.peopledatalabs.com/). "
                        "Live tools OK with tenant API key; contact-level Memory/KG writes remain STA-312 gated. "
                        "Crunchbase stays activation-gated."
                    ),
                    external_url="https://dashboard.peopledatalabs.com/",
                ),
            ],
            demo_agent_name="Sales Pipeline Analyst",
            demo_systems=["hubspot"],
            connector_template_id="sales-intelligence-sources",
            workflow_name="Sales HubSpot Pipeline Snapshot",
            workflow_description="Agent brief → HubSpot pipelines.list → agent pipeline summary.",
            workflow_steps=build_sales_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="prospecting-intelligence-pack",
            name="Prospecting & Lead Scouting Pack",
            department="sales",
            default_subdomain="outbound_prospecting",
            description=(
                "Outbound lead gen: Apollo find-companies/contacts + list create, optional HubSpot "
                "list sync, Lead Scouting Analyst. ≠ Sales pipeline pack. "
                "Build ICP and Create list work with any connected Apollo account; "
                "company/contact discovery specifically requires a paid Apollo plan with search API access "
                "(BYO-tier — same as ZoomInfo / LinkedIn Sales Navigator). "
                "People Data Labs is BYO API key (dashboard.peopledatalabs.com); "
                "contact-level Memory/KG writes remain STA-312 gated. Crunchbase stays activation-gated."
            ),
            marketplace_tags=["prospecting", "starter", "intelligence-pack", "outbound", "apollo"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "icp-criteria",
                    "ICP Criteria",
                    "sales",
                    "outbound_prospecting",
                    reference_summary="Ideal customer profile criteria for outbound scouting (RAG/playbook; no new connector).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "apollo-company-discovery",
                    "Apollo Company Discovery",
                    "sales",
                    "outbound_prospecting",
                    reference_summary=(
                        "Find companies via apollo.organizations.search. "
                        "Requires tenant Apollo plan with search API access (BYO-tier); "
                        "free-plan connections stay connected for list create but discovery is blocked."
                    ),
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "apollo-contact-discovery",
                    "Apollo Contact Discovery",
                    "sales",
                    "outbound_prospecting",
                    reference_summary=(
                        "Find contacts via apollo.people.search. "
                        "Requires paid Apollo plan with search API access (BYO-tier). "
                        "Contact-level Memory/KG writes remain STA-312 gated."
                    ),
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "list-building",
                    "List Building",
                    "sales",
                    "outbound_prospecting",
                    reference_summary=(
                        "Create Apollo/HubSpot lists via existing lists.create actions — "
                        "works with free or paid Apollo accounts."
                    ),
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "pdl-account-enrichment",
                    "People Data Labs Account Enrichment",
                    "sales",
                    "outbound_prospecting",
                    reference_summary=(
                        "BYO People Data Labs person/company enrich "
                        "(https://dashboard.peopledatalabs.com/). "
                        "Live tools OK with tenant API key; contact-level Memory/KG writes remain STA-312 gated. "
                        "Crunchbase stays activation-gated."
                    ),
                    external_url="https://dashboard.peopledatalabs.com/",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "clay-list-enrichment",
                    "Clay List Enrichment",
                    "sales",
                    "outbound_prospecting",
                    reference_summary=(
                        "Enrich existing Apollo contact lists via Clay (clay.leads.push → clay.workflows.output.get), "
                        "then sync to HubSpot static lists. Requires BYO Clay workspace API key or webhook."
                    ),
                ),
            ],
            demo_agent_name="Lead Scouting Analyst",
            demo_systems=["apollo", "hubspot", "clay"],
            connector_template_id="prospecting-intelligence-sources",
            workflow_name="Prospecting Apollo Lead Scout",
            workflow_description=(
                "Agent ICP brief → Apollo org/people search → Apollo + HubSpot list create → "
                "agent summary. PDL BYO enrich via Connectors; no Memory/KG contact writes."
            ),
            workflow_steps=build_prospecting_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="support-intelligence-pack",
            name="Support Intelligence Pack",
            department="support",
            default_subdomain="technical_support",
            description="Zendesk views, KB, product docs, and escalation playbooks.",
            marketplace_tags=["support", "starter", "intelligence-pack"],
            assignments=[
                IntelligencePackAssignment("zendesk_view", "support-queue", "Zendesk Views", "support", "technical_support"),
                IntelligencePackAssignment("knowledge_pack", "support-kb", "Knowledge Base", "support", "technical_support"),
                IntelligencePackAssignment("confluence_space", "product-docs", "Product Docs", "support", "customer_success"),
                IntelligencePackAssignment("google_drive_folder", "escalation-playbooks", "Escalation Playbooks", "support", "escalations"),
            ],
            demo_agent_name="Support Queue Analyst",
            demo_systems=["zendesk"],
            connector_template_id=None,
            workflow_name="Support Zendesk Queue Snapshot",
            workflow_description="Agent brief → Zendesk tickets.list → agent queue summary.",
            workflow_steps=build_support_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="customer-success-intelligence-pack",
            name="Customer Success Intelligence Pack",
            department="customer_success",
            default_subdomain="account_health",
            description=(
                "Internal retention / health signals: HubSpot CRM + Zendesk support reads, "
                "Customer Success Health Analyst, QBR-style workflow. "
                "No new external governance surface; reuses existing connectors only."
            ),
            marketplace_tags=["customer_success", "starter", "intelligence-pack", "retention"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "hubspot-account-health",
                    "HubSpot Account Health",
                    "customer_success",
                    "account_health",
                    reference_summary="CRM pipeline stages via hubspot.pipelines.list (read-only).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "zendesk-support-signals",
                    "Zendesk Support Signals",
                    "customer_success",
                    "support_health",
                    reference_summary="Open/recent tickets via zendesk.tickets.list (read-only).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "product-usage-signals",
                    "Product Usage Signals",
                    "customer_success",
                    "product_adoption",
                    reference_summary="Internal product-usage metadata references (no new connector).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "billing-health-metadata",
                    "Billing Health Metadata",
                    "customer_success",
                    "renewal_risk",
                    reference_summary="Billing metadata references for renewal risk (existing Stripe/CRM; no live finance gate).",
                ),
            ],
            demo_agent_name="Customer Success Health Analyst",
            demo_systems=["hubspot", "zendesk"],
            connector_template_id="customer-success-intelligence-sources",
            workflow_name="CS Account Health Snapshot",
            workflow_description=(
                "Agent brief → HubSpot pipelines/deals + Zendesk tickets → agent health briefing."
            ),
            workflow_steps=build_cs_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="msp-intelligence-pack",
            name="MSP Intelligence Pack",
            department="msp",
            default_subdomain="outbound_prospecting",
            description=(
                "MSP company prospecting + list building (Apollo/HubSpot agents & tasks), plus "
                "Gravitree-managed vulnerability knowledge assignments (NVD / CISA KEV) for the "
                "MSP Vulnerability Analyst. CIS Controls deferred."
            ),
            marketplace_tags=["msp", "starter", "intelligence-pack", "gravitree", "prospecting"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "msp-icp-criteria",
                    "MSP ICP Criteria",
                    "msp",
                    "outbound_prospecting",
                    reference_summary="Ideal MSP customer profile for outbound scouting and list building.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "list-building",
                    "List Building",
                    "msp",
                    "outbound_prospecting",
                    reference_summary="Apollo/HubSpot list create + membership for MSP Prospects / MSPs.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "nvd-cve-feed",
                    "NVD CVE Feed",
                    "msp",
                    "vulnerability_intelligence",
                    reference_summary="Platform-managed NVD CVE lookup via nvd.cve.get (Phase 1.5 shared path).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "cisa-kev-catalog",
                    "CISA KEV Catalog",
                    "msp",
                    "vulnerability_intelligence",
                    reference_summary="CISA Known Exploited Vulnerabilities via cisa_kev.feed.get (Phase 1.5 shared path).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "rmm-policies",
                    "RMM Policies",
                    "msp",
                    "rmm",
                    reference_summary="Curated RMM policy knowledge for MSP operations.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "vendor-security-advisories",
                    "Vendor Security Advisories",
                    "msp",
                    "security_operations",
                    reference_summary="Vendor advisory references for patch prioritization (CIS deferred).",
                ),
            ],
            demo_agent_name="MSP Prospecting Coordinator",
            demo_systems=["apollo", "hubspot", "nvd", "cisa_kev"],
            connector_template_id="msp-intelligence-sources",
            workflow_name="MSP Prospecting & List Builder",
            workflow_description=(
                "Prospect MSPs with agents + Apollo/HubSpot tools: ICP brief → company/contact "
                "discovery → qualify → create lists → membership → notify. "
                "NVD/CISA remain available as knowledge assignments."
            ),
            workflow_steps=build_msp_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="executive-intelligence-pack",
            name="Executive Intelligence Pack",
            department="executive",
            default_subdomain="macro_intelligence",
            description=(
                "Gravitree-managed macro intelligence: FRED/SEC/World Bank/OECD sources, "
                "executive analyst agent, and a read-only FRED signal workflow."
            ),
            marketplace_tags=["executive", "starter", "intelligence-pack", "gravitree"],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "fred-macro-series",
                    "FRED Macro Series",
                    "executive",
                    "macro_intelligence",
                    reference_summary="Platform-managed FRED series (GDP, UNRATE, CPI) via fred.series.get.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "sec-edgar-filings",
                    "SEC EDGAR Filings",
                    "executive",
                    "regulatory",
                    reference_summary="SEC company filings lookup (Gravitree-managed; activation may require SEC_USER_AGENT).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "world-bank-indicators",
                    "World Bank Indicators",
                    "executive",
                    "macro_intelligence",
                    reference_summary="World Bank country indicators via shared Phase 1.5 path.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "oecd-datasets",
                    "OECD Datasets",
                    "executive",
                    "macro_intelligence",
                    reference_summary="OECD SDMX dataset probes (capability scaffold).",
                ),
            ],
            demo_agent_name="Executive Macro Analyst",
            demo_systems=["fred", "sec_edgar"],
            connector_template_id="executive-intelligence-sources",
            workflow_name="Executive FRED Macro Signal",
            workflow_description="Agent brief → FRED GDP + SEC EDGAR search → agent macro summary.",
            workflow_steps=build_executive_workflow_steps(),
        ),
        IntelligencePackSpec(
            pack_id="platform-health-intelligence-pack",
            name="Platform Health / Workflow Intelligence Pack",
            department="platform",
            default_subdomain="workflow_reliability",
            description=(
                "Self-signal pack: approval latency, step failures, flaky connectors, and stalled "
                "workflows from org-local audit_events + run history. Zero new external connectors; "
                "reuses STA-124 integration health scoring."
            ),
            marketplace_tags=[
                "platform",
                "ops",
                "self-signal",
                "starter",
                "intelligence-pack",
                "workflow-health",
            ],
            assignments=[
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "audit-events-telemetry",
                    "Audit Events Telemetry",
                    "platform",
                    "workflow_reliability",
                    reference_summary="Org audit_events for tool.invoke / workflow.execute / connector.auth signals.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "workflow-run-history",
                    "Workflow Run History",
                    "platform",
                    "workflow_reliability",
                    reference_summary="workflow_runs status and age for stalled / pending_approval detection.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "approval-latency-rubric",
                    "Approval Latency Rubric",
                    "platform",
                    "governance",
                    reference_summary="STA-124 approval latency bands (p95 minutes → days) for recommendations.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "connector-ops-playbook",
                    "Connector Ops Playbook",
                    "platform",
                    "connector_ops",
                    reference_summary="Flaky connector and auth-churn playbook references (internal only).",
                ),
            ],
            demo_agent_name="Platform Reliability Analyst",
            demo_systems=["platform"],
            connector_template_id=None,
            workflow_name="Platform Health Snapshot",
            workflow_description=(
                "Agent brief → platform.health.snapshot → agent reliability recommendations."
            ),
            workflow_steps=build_platform_health_workflow_steps(),
        ),
    ]


def get_intelligence_pack_spec(pack_id: str) -> IntelligencePackSpec | None:
    for spec in list_intelligence_pack_specs():
        if spec.pack_id == pack_id:
            return spec
    return None


def intelligence_pack_to_marketplace_asset(spec: IntelligencePackSpec) -> dict[str, Any]:
    return {
        "slug": spec.pack_id,
        "title": spec.name,
        "description": spec.description,
        "asset_type": "intelligence_pack",
        "category": "intelligence_pack",
        "department": spec.department,
        "tier": spec.tier,
        "tags": spec.marketplace_tags,
        "config": {
            "department": spec.department,
            "default_subdomain": spec.default_subdomain,
            "demo_agent_name": spec.demo_agent_name,
            "demo_systems": list(spec.demo_systems),
            "connector_template_id": spec.connector_template_id,
            "workflow_name": spec.workflow_name,
            "workflow_description": spec.workflow_description,
            "workflow_steps": list(spec.workflow_steps),
            "assignments": [
                {
                    "source_type": row.source_type,
                    "source_id": row.source_id,
                    "label": row.label,
                    "department": row.department,
                    "subdomain": row.subdomain,
                    "confidence_weight": row.confidence_weight,
                    "reference_summary": row.reference_summary,
                    "external_url": row.external_url,
                }
                for row in spec.assignments
            ],
        },
    }
