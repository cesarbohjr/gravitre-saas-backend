"""Marketplace intelligence packs — installable domain knowledge assignments."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
            description="Brand, campaign, HubSpot, GA4, and creative knowledge assignments.",
            marketplace_tags=["marketing", "starter", "intelligence-pack"],
            assignments=[
                IntelligencePackAssignment("google_drive_folder", "brand-guidelines", "Brand Guidelines", "marketing", "brand_marketing", reference_summary="Brand voice, visual standards, and messaging guardrails."),
                IntelligencePackAssignment("google_drive_folder", "campaign-playbooks", "Campaign Playbooks", "marketing", "content_marketing", reference_summary="Approved campaign templates and launch checklists."),
                IntelligencePackAssignment("hubspot_view", "marketing-campaigns", "HubSpot Campaigns", "marketing", "demand_generation"),
                IntelligencePackAssignment("google_analytics", "ga4-property", "GA4 Property", "marketing", "analytics"),
                IntelligencePackAssignment("canva", "brand-assets", "Canva Brand Assets", "marketing", "brand_marketing"),
            ],
        ),
        IntelligencePackSpec(
            pack_id="sales-intelligence-pack",
            name="Sales Intelligence Pack",
            department="sales",
            default_subdomain="pipeline_management",
            description=(
                "Customer CRM pipeline intelligence: HubSpot read-only snapshot workflow, "
                "Sales Pipeline Analyst agent, HubSpot/Apollo stubs. "
                "Crunchbase/PDL → Memory/KG gated; BYO ZoomInfo/LI Sales Nav fail-closed; CIS/hiring deferred."
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
                    "account-research-notes",
                    "Account Research Notes",
                    "sales",
                    "enterprise_sales",
                    reference_summary=(
                        "Account research placeholders. Crunchbase/PDL enrichment not enabled "
                        "(governance stop-line)."
                    ),
                ),
            ],
            demo_agent_name="Sales Pipeline Analyst",
            demo_systems=["hubspot"],
            connector_template_id="sales-intelligence-sources",
            workflow_name="Sales HubSpot Pipeline Snapshot",
            workflow_description="Read-only: list HubSpot deal pipelines via invoke_tool (customer-owned CRM).",
            workflow_steps=[
                {
                    "id": "hubspot-pipelines",
                    "name": "List HubSpot Pipelines",
                    "type": "invoke_tool",
                    "config": {"action": "hubspot.pipelines.list", "params": {}},
                },
            ],
        ),
        IntelligencePackSpec(
            pack_id="prospecting-intelligence-pack",
            name="Prospecting & Lead Scouting Pack",
            department="sales",
            default_subdomain="outbound_prospecting",
            description=(
                "Outbound lead gen: Apollo find-companies/contacts + list create, optional HubSpot "
                "list sync, Lead Scouting Analyst. ≠ Sales pipeline pack. "
                "Crunchbase/PDL → Memory/KG gated (STA-312); BYO ZoomInfo/LI Sales Nav stubs only."
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
                    reference_summary="Find companies via apollo.organizations.search (existing action).",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "apollo-contact-discovery",
                    "Apollo Contact Discovery",
                    "sales",
                    "outbound_prospecting",
                    reference_summary=(
                        "Find contacts via apollo.people.search. Plan-limited on free Apollo; "
                        "contact-level Memory/KG writes remain STA-312 gated."
                    ),
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "list-building",
                    "List Building",
                    "sales",
                    "outbound_prospecting",
                    reference_summary="Create Apollo/HubSpot lists via existing lists.create actions.",
                ),
                IntelligencePackAssignment(
                    "knowledge_pack",
                    "account-enrichment-gated",
                    "Account Enrichment (gated)",
                    "sales",
                    "outbound_prospecting",
                    reference_summary=(
                        "Crunchbase/PDL enrichment placeholders. Not enabled — STA-312 "
                        "governance stop-line (no Memory/KG path)."
                    ),
                ),
            ],
            demo_agent_name="Lead Scouting Analyst",
            demo_systems=["apollo", "hubspot"],
            connector_template_id="prospecting-intelligence-sources",
            workflow_name="Prospecting Apollo Lead Scout",
            workflow_description=(
                "Outbound: Apollo org search → people search → Apollo list create → HubSpot list create. "
                "No Crunchbase/PDL/KG writes."
            ),
            workflow_steps=[
                {
                    "id": "apollo-orgs",
                    "name": "Find Companies",
                    "type": "invoke_tool",
                    "config": {
                        "action": "apollo.organizations.search",
                        "params": {"q_organization_name": "Microsoft", "per_page": 5},
                    },
                },
                {
                    "id": "apollo-people",
                    "name": "Find Contacts",
                    "type": "invoke_tool",
                    "config": {
                        "action": "apollo.people.search",
                        "params": {"q_keywords": "VP Sales", "per_page": 5},
                    },
                },
                {
                    "id": "apollo-list",
                    "name": "Create Apollo List",
                    "type": "invoke_tool",
                    "config": {
                        "action": "apollo.lists.create",
                        "params": {"name": "Prospecting Pack Scout List", "modality": "contacts"},
                    },
                },
                {
                    "id": "hubspot-list",
                    "name": "Create HubSpot List",
                    "type": "invoke_tool",
                    "config": {
                        "action": "hubspot.lists.create",
                        "params": {"name": "Prospecting Pack Sync List"},
                    },
                },
            ],
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
                "Read-only: HubSpot pipelines + Zendesk ticket list for retention health briefings."
            ),
            workflow_steps=[
                {
                    "id": "hubspot-pipelines",
                    "name": "List HubSpot Pipelines",
                    "type": "invoke_tool",
                    "config": {"action": "hubspot.pipelines.list", "params": {}},
                },
                {
                    "id": "hubspot-deals",
                    "name": "List HubSpot Deals",
                    "type": "invoke_tool",
                    "config": {"action": "hubspot.deals.list", "params": {"limit": 10}},
                },
                {
                    "id": "zendesk-tickets",
                    "name": "List Zendesk Tickets",
                    "type": "invoke_tool",
                    "config": {"action": "zendesk.tickets.list", "params": {"limit": 10}},
                },
            ],
        ),
        IntelligencePackSpec(
            pack_id="msp-intelligence-pack",
            name="MSP Intelligence Pack",
            department="msp",
            default_subdomain="vulnerability_intelligence",
            description=(
                "Gravitree-managed vulnerability intelligence: NVD CVE lookup, CISA KEV staging, "
                "MSP analyst agent, and a read-only NVD CVE workflow. CIS Controls deferred."
            ),
            marketplace_tags=["msp", "starter", "intelligence-pack", "gravitree"],
            assignments=[
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
            demo_agent_name="MSP Vulnerability Analyst",
            demo_systems=["nvd", "cisa_kev"],
            connector_template_id="msp-intelligence-sources",
            workflow_name="MSP NVD CVE Lookup",
            workflow_description="Read-only: fetch a CVE via invoke_tool (Gravitree-managed NVD).",
            workflow_steps=[
                {
                    "id": "nvd-cve",
                    "name": "Fetch NVD CVE",
                    "type": "invoke_tool",
                    "config": {"action": "nvd.cve.get", "params": {"cve_id": "CVE-2024-3094"}},
                },
                {
                    "id": "cisa-kev",
                    "name": "Fetch CISA KEV sample",
                    "type": "invoke_tool",
                    "config": {"action": "cisa_kev.feed.get", "params": {}},
                },
            ],
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
            workflow_description="Read-only: fetch latest FRED GDP series via invoke_tool (Gravitree-managed).",
            workflow_steps=[
                {
                    "id": "fred-gdp",
                    "name": "Fetch FRED GDP",
                    "type": "invoke_tool",
                    "config": {"action": "fred.series.get", "params": {"series_id": "GDP"}},
                },
                {
                    "id": "sec-filings",
                    "name": "Search SEC EDGAR filings",
                    "type": "invoke_tool",
                    "config": {"action": "sec_edgar.filings.search", "params": {"query": "Microsoft"}},
                },
            ],
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
