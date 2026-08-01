"""Gravitre starter marketplace catalog (MKT-4.1 – MKT-4.4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.workflows.constants import SCHEMA_VERSION

HUBSPOT = {
    "connectorType": "hubspot",
    "label": "HubSpot CRM",
    "required": True,
    "connectPath": "/connectors?type=hubspot",
}
SALESFORCE = {
    "connectorType": "salesforce",
    "label": "Salesforce",
    "required": True,
    "connectPath": "/connectors?type=salesforce",
}
SLACK = {
    "connectorType": "slack",
    "label": "Slack",
    "required": False,
    "connectPath": "/connectors?type=slack",
}
GOOGLE_ANALYTICS = {
    "connectorType": "google_analytics",
    "label": "Google Analytics",
    "required": False,
    "connectPath": "/connectors?type=google_analytics",
}
GOOGLE_SEARCH_CONSOLE = {
    "connectorType": "google_search_console",
    "label": "Google Search Console",
    "required": False,
    "connectPath": "/connectors?type=google_search_console",
    "requirementNote": (
        "Page/URL search aggregates may feed Marketing pack signals. "
        "Raw Search Console query strings are gated from Organizational Memory / Knowledge Graph."
    ),
}
SEMRUSH = {
    "connectorType": "semrush",
    "label": "SEMrush",
    "required": False,
    "connectPath": "/connectors?type=semrush",
    "requirementNote": (
        "SEMrush requires your own SEMrush API subscription (BYO). "
        "Gravitre never uses a shared platform key. "
        "v1 reads: domain overview, organic keywords, backlinks."
    ),
}
AHREFS = {
    "connectorType": "ahrefs",
    "label": "Ahrefs",
    "required": False,
    "connectPath": "/connectors?type=ahrefs",
    "requirementNote": (
        "Ahrefs requires your own Ahrefs API subscription (BYO). "
        "Gravitre never uses a shared platform key. "
        "v1 reads: domain rating, organic keywords, backlinks; "
        "Brand Radar overview for AI Search pack."
    ),
}
FINSEO = {
    "connectorType": "finseo",
    "label": "Finseo",
    "required": False,
    "connectPath": "/connectors?type=finseo",
    "requirementNote": (
        "Finseo requires your own Finseo API subscription (BYO). "
        "Gravitre never uses a shared platform key. "
        "AI visibility metrics, prompts, and competitors."
    ),
}
AI_VISIBILITY_UI = {
    "connectorType": "ai_visibility_ui",
    "label": "AI Visibility UI",
    "required": False,
    "connectPath": "/connectors?type=ai_visibility_ui",
    "requirementNote": (
        "S2 consumer-UI scrape connector (ChatGPT / Perplexity / Gemini / Copilot / Claude). "
        "Action tiers v1–v3; provenance required; LinkedIn scrape forbidden; "
        "raw answer text Memory/KG gated."
    ),
}
PDL = {
    "connectorType": "pdl",
    "label": "People Data Labs",
    "required": False,
    "connectPath": "/connectors?type=pdl",
    "requirementNote": (
        "People Data Labs requires your own PDL API subscription (BYO). "
        "Gravitre never uses a shared platform key. "
        "Connect your API key from https://dashboard.peopledatalabs.com/ "
        "for person/company enrich. Contact-level Memory/KG writes remain gated."
    ),
}
APOLLO = {
    "connectorType": "apollo",
    "label": "Apollo.io",
    "required": False,
    "connectPath": "/connectors?type=apollo",
    "requirementNote": (
        "Company/contact discovery requires your own Apollo plan with search API access "
        "(BYO-tier, same pattern as ZoomInfo / LinkedIn Sales Navigator). "
        "Build ICP and Create list work with any connected Apollo account."
    ),
}
CLAY = {
    "connectorType": "clay",
    "label": "Clay",
    "required": False,
    "connectPath": "/connectors?type=clay",
    "requirementNote": (
        "Clay requires your own Clay workspace API key or webhook URL (BYO). "
        "Used for lead enrichment before CRM sync."
    ),
}
NOTION = {
    "connectorType": "notion",
    "label": "Notion",
    "required": False,
    "connectPath": "/connectors?type=notion",
}
GOOGLE_DRIVE = {
    "connectorType": "google_drive",
    "label": "Google Drive",
    "required": False,
    "connectPath": "/connectors?type=google_drive",
}
CANVA = {
    "connectorType": "canva",
    "label": "Canva",
    "required": False,
    "connectPath": "/connectors?type=canva",
}
ZENDESK = {
    "connectorType": "zendesk",
    "label": "Zendesk Support",
    "required": True,
    "connectPath": "/connectors?type=zendesk",
}


@dataclass(frozen=True)
class CatalogAsset:
    slug: str
    title: str
    description: str
    asset_type: str
    category: str
    department: str
    config: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    required_connectors: list[dict[str, Any]] = field(default_factory=list)
    install_variables: list[dict[str, Any]] = field(default_factory=list)
    pack_children: list[str] = field(default_factory=list)
    business_outcome: str | None = None
    use_case: str | None = None
    estimated_hours_saved: float | None = None
    pricing_type: str = "free"
    price_cents: int = 0
    pack_tier: int | None = None


def _agent_seed(slug: str) -> str:
    return f"agent:{slug}"


def _agent(
    slug: str,
    *,
    name: str,
    purpose: str,
    role: str,
    department: str,
    persona_key: str,
    systems: list[str],
    capabilities: list[str] | None = None,
    model: str = "gpt-4.1",
) -> dict[str, Any]:
    return {
        "seed_label": _agent_seed(slug),
        "name": name,
        "purpose": purpose,
        "role": role,
        "department": department,
        "model": model,
        "persona_key": persona_key,
        "capabilities": capabilities or [],
        "systems": systems,
        "guardrails": [],
        "config": {"marketplaceSlug": slug},
    }


def _rag_doc(seed: str, title: str, *, pack: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"description": f"Upload content for {title}."}
    if pack:
        metadata["departmentPack"] = pack
    return {"seed_label": seed, "title": title, "type": "manual", "metadata": metadata}


def _workflow(
    name: str,
    description: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "description": description,
        "steps": steps,
    }


def _invoke(step_id: str, name: str, action: str, *, connector: str | None = None) -> dict[str, Any]:
    step: dict[str, Any] = {
        "id": step_id,
        "name": name,
        "type": "invoke_tool",
        "config": {"action": action},
    }
    if connector:
        step["requires_connector"] = connector
    return step


def _agent_step(
    step_id: str,
    name: str,
    agent_slug: str,
    task: str,
    *,
    next_agent_slug: str | None = None,
    briefing_from_steps: bool = False,
    receiver_task: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "agent_seed": _agent_seed(agent_slug),
        "task": task,
    }
    if next_agent_slug:
        metadata["next_agent_seed"] = _agent_seed(next_agent_slug)
    if briefing_from_steps:
        metadata["briefing_from_steps"] = True
    if receiver_task:
        metadata["receiver_task"] = receiver_task
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": metadata,
    }


def _knowledge_pack(documents: list[dict[str, Any]]) -> dict[str, Any]:
    return {"documents": documents}


def _department_pack_config(
    *,
    workflow_name: str,
    workflow_description: str,
    agents: list[dict[str, Any]],
    rag_sources: list[dict[str, Any]],
    workflow_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "workflow_name": workflow_name,
        "workflow_description": workflow_description,
        "agents": agents,
        "rag_sources": rag_sources,
        "workflow_steps": workflow_steps,
    }


def _ai_agents() -> list[CatalogAsset]:
    specs = [
        ("marketing-analyst", "Marketing Analyst", "Marketing", "MARKETING", ["hubspot", "google_analytics"], ["campaign-analysis", "attribution"]),
        ("product-icp-strategist", "Product & ICP Strategist", "Marketing", "MARKETING", ["hubspot"], ["icp", "positioning"]),
        ("content-writer", "Content Writer", "Marketing", "MARKETING", ["hubspot"], ["copywriting"]),
        ("marketing-designer", "Marketing Designer", "Marketing", "MARKETING", ["canva"], ["creative-brief"]),
        ("marketing-ops-coordinator", "Marketing Ops Coordinator", "Marketing", "MARKETING", ["hubspot", "google_analytics"], ["campaign-ops"]),
        ("seo-analyst", "SEO Analyst", "Marketing", "MARKETING", ["google_analytics"], ["seo-audit", "keyword-research"]),
        ("competitor-research-agent", "Competitor Research Agent", "Marketing", "MARKETING", ["hubspot"], ["competitive-intel", "market-scan"]),
        ("revenue-operations-agent", "Revenue Operations Agent", "Revenue Operations", "REVENUE_OPS", ["hubspot", "salesforce"], ["pipeline-hygiene", "forecasting"]),
        ("sales-pipeline-agent", "Sales Pipeline Agent", "Sales", "SALES", ["hubspot", "salesforce"], ["pipeline-review", "deal-coaching"]),
        ("customer-success-agent", "Customer Success Agent", "Customer Success", "CS", ["hubspot"], ["health-scoring", "renewal-risk"]),
        ("ticket-triage", "Ticket Triage Agent", "Support", "SUPPORT", ["zendesk"], ["ticket-triage", "macro-suggestion"]),
        ("cfo-agent", "CFO Agent", "Finance", "FINANCE", ["quickbooks"], ["variance-analysis", "board-reporting"]),
        ("sdr-coach", "SDR Coach", "Sales", "SALES", ["hubspot"], ["call-coaching", "sequence-optimization"]),
        (
            "lead-enrichment-coordinator",
            "Lead Enrichment Coordinator",
            "Sales",
            "SALES",
            ["apollo", "clay", "hubspot"],
            ["enrichment", "list_sync", "apollo_lists", "hubspot_lists"],
        ),
    ]
    assets: list[CatalogAsset] = []
    for slug, name, department, persona, systems, capabilities in specs:
        assets.append(
            CatalogAsset(
                slug=slug,
                title=name,
                description=f"{name} — Gravitre starter agent for {department.lower()} teams.",
                asset_type="ai_agent",
                category="ai_agent",
                department=department,
                tags=[department.lower().replace(" ", "-"), "starter", "agent"],
                config=_agent(
                    slug,
                    name=name,
                    purpose=f"Supports {department.lower()} workflows with governed AI assistance.",
                    role=name,
                    department=department,
                    persona_key=persona,
                    systems=systems,
                    capabilities=capabilities,
                ),
                required_connectors=(
                    [HUBSPOT]
                    if "hubspot" in systems
                    else [ZENDESK]
                    if "zendesk" in systems
                    else []
                ),
            )
        )
    return assets


def _workflows() -> list[CatalogAsset]:
    from app.marketplace.workflows.msp_enrichment_workflow import (
        INSTALL_VARIABLES as MSP_ENRICHMENT_INSTALL_VARS,
        WORKFLOW_DESCRIPTION as MSP_ENRICHMENT_DESCRIPTION,
        build_msp_enrichment_workflow_steps,
    )

    definitions: list[tuple[str, str, str, list[dict], list[dict]]] = [
        (
            "hubspot-lead-qualification",
            "HubSpot Lead Qualification",
            "Sales",
            [HUBSPOT],
            [
                _invoke("lookup", "HubSpot contact lookup", "hubspot.search_contacts", connector="hubspot"),
                _agent_step("qualify", "Qualify lead", "sales-pipeline-agent", "Score fit and recommend next step."),
            ],
        ),
        (
            "monthly-executive-reporting",
            "Monthly Executive Reporting",
            "Finance",
            [],
            [
                _agent_step("summarize", "Executive summary", "cfo-agent", "Draft monthly executive KPI narrative."),
                _invoke("notify", "Notify leadership", "slack.post_message", connector="slack"),
            ],
        ),
        (
            "customer-health-monitoring",
            "Customer Health Monitoring",
            "Customer Success",
            [HUBSPOT],
            [
                _invoke("accounts", "Pull account signals", "hubspot.search_contacts", connector="hubspot"),
                _agent_step("health", "Health score review", "customer-success-agent", "Flag at-risk accounts."),
            ],
        ),
        (
            "marketing-campaign-production",
            "Marketing Campaign Production",
            "Marketing",
            [HUBSPOT, GOOGLE_ANALYTICS],
            [
                _invoke("traffic", "Analytics snapshot", "analytics.reports.run", connector="google_analytics"),
                _agent_step(
                    "icp_content",
                    "ICP strategy and content draft",
                    "product-icp-strategist",
                    "Define ICP focus and campaign thesis for this run.",
                    next_agent_slug="content-writer",
                    receiver_task="Draft campaign copy using the ICP briefing and brand voice guide.",
                ),
                _agent_step(
                    "design_ops",
                    "Design brief and ops handoff",
                    "marketing-designer",
                    "Produce a creative brief from prior campaign context.",
                    next_agent_slug="marketing-ops-coordinator",
                    briefing_from_steps=True,
                    receiver_task="Build publish checklist and coordinate next marketing actions.",
                ),
            ],
        ),
        (
            "marketing-attribution-analysis",
            "Marketing Attribution Analysis",
            "Marketing",
            [HUBSPOT, GOOGLE_ANALYTICS],
            [
                _invoke("traffic", "Pull analytics snapshot", "analytics.reports.run", connector="google_analytics"),
                _agent_step("attribute", "Attribution review", "marketing-analyst", "Summarize channel contribution."),
            ],
        ),
        (
            "competitive-intelligence-monitoring",
            "Competitive Intelligence Monitoring",
            "Marketing",
            [],
            [
                _agent_step("scan", "Competitive scan", "competitor-research-agent", "Summarize competitor moves."),
                _agent_step("brief", "Marketing brief", "marketing-analyst", "Translate intel into campaign actions."),
            ],
        ),
        (
            "salesforce-pipeline-review",
            "Salesforce Pipeline Review",
            "Sales",
            [SALESFORCE],
            [
                _invoke("pipeline", "Pipeline snapshot", "salesforce.query", connector="salesforce"),
                _agent_step("review", "Pipeline review", "sales-pipeline-agent", "Highlight stalled deals."),
            ],
        ),
        (
            "executive-summary-generation",
            "Executive Summary Generation",
            "Revenue Operations",
            [],
            [
                _agent_step("revops", "RevOps rollup", "revenue-operations-agent", "Summarize cross-functional KPIs."),
                _agent_step("exec", "Executive narrative", "cfo-agent", "Produce board-ready summary."),
            ],
        ),
        (
            "weekly-team-status-report",
            "Weekly Team Status Report",
            "Revenue Operations",
            [SLACK],
            [
                _agent_step("collect", "Collect status themes", "revenue-operations-agent", "Draft weekly status bullets."),
                _invoke("publish", "Post to Slack", "slack.post_message", connector="slack"),
            ],
        ),
        (
            "zendesk-ticket-triage",
            "Zendesk Ticket Triage",
            "Support",
            [ZENDESK],
            [
                {
                    "id": "ticket_lookup",
                    "name": "Fetch ticket context",
                    "type": "invoke_tool",
                    "config": {
                        "action": "zendesk.tickets.get",
                        "param_sources": {"ticket_id": "$ticket_id"},
                    },
                    "requires_connector": "zendesk",
                },
                _agent_step(
                    "triage",
                    "AI ticket triage",
                    "ticket-triage",
                    "Classify urgency, suggest response macro, and flag escalation if needed.",
                ),
            ],
        ),
        (
            "msp-prospects-clay-hubspot-enrichment",
            "MSP Prospects Clay Enrichment → HubSpot Sync",
            "Sales",
            [APOLLO, CLAY, HUBSPOT],
            build_msp_enrichment_workflow_steps(),
        ),
    ]
    assets: list[CatalogAsset] = []
    for slug, title, department, connectors, steps in definitions:
        is_msp_enrichment = slug == "msp-prospects-clay-hubspot-enrichment"
        assets.append(
            CatalogAsset(
                slug=slug,
                title=title,
                description=MSP_ENRICHMENT_DESCRIPTION if is_msp_enrichment else f"{title} — starter workflow template.",
                asset_type="workflow",
                category="workflow",
                department=department,
                tags=["workflow", "starter", department.lower().replace(" ", "-")],
                config=_workflow(title, MSP_ENRICHMENT_DESCRIPTION if is_msp_enrichment else f"Automated {title.lower()} playbook.", steps),
                required_connectors=connectors,
                install_variables=MSP_ENRICHMENT_INSTALL_VARS if is_msp_enrichment else [],
            )
        )
    return assets


def _knowledge_packs() -> list[CatalogAsset]:
    packs = [
        (
            "marketing-operations-knowledge",
            "Marketing Operations Knowledge Pack",
            "Marketing",
            [
                _rag_doc("rag:brand-voice", "Brand Voice Guide"),
                _rag_doc("rag:campaign-library", "Campaign Playbooks"),
            ],
        ),
        (
            "saas-sales-knowledge",
            "SaaS Sales Knowledge Pack",
            "Sales",
            [
                _rag_doc("rag:icp", "Ideal Customer Profile"),
                _rag_doc("rag:objections", "Objection Handling"),
            ],
        ),
        (
            "customer-success-knowledge",
            "Customer Success Knowledge Pack",
            "Customer Success",
            [
                _rag_doc("rag:health-rubric", "Customer Health Rubric"),
                _rag_doc("rag:renewal-playbook", "Renewal Playbook"),
            ],
        ),
        (
            "msp-operations-knowledge",
            "MSP Operations Knowledge Pack",
            "Operations",
            [
                _rag_doc("rag:sla-matrix", "SLA Matrix"),
                _rag_doc("rag:runbooks", "Service Runbooks"),
            ],
        ),
        (
            "hr-operations-knowledge",
            "HR Operations Knowledge Pack",
            "HR",
            [
                _rag_doc("rag:policy-handbook", "Policy Handbook"),
                _rag_doc("rag:onboarding", "Onboarding Checklists"),
            ],
        ),
        (
            "revenue-operations-knowledge",
            "Revenue Operations Knowledge Pack",
            "Revenue Operations",
            [
                _rag_doc("rag:forecast-model", "Forecast Model"),
                _rag_doc("rag:pipeline-definitions", "Pipeline Stage Definitions"),
            ],
        ),
    ]
    return [
        CatalogAsset(
            slug=slug,
            title=title,
            description=f"{title} — upload your org documents after install.",
            asset_type="knowledge_pack",
            category="knowledge_pack",
            department=department,
            tags=["knowledge", "rag", department.lower().replace(" ", "-")],
            config=_knowledge_pack(documents),
        )
        for slug, title, department, documents in packs
    ]


def _department_packs() -> list[CatalogAsset]:
    marketing_agents = [
        _agent(
            "product-icp-strategist",
            name="Product & ICP Strategist",
            purpose="Define ICP positioning and campaign thesis.",
            role="Product Marketing",
            department="Marketing",
            persona_key="MARKETING",
            systems=["hubspot"],
            capabilities=["icp", "positioning"],
        ),
        _agent(
            "content-writer",
            name="Content Writer",
            purpose="Draft campaign copy aligned to brand voice.",
            role="Content Marketing",
            department="Marketing",
            persona_key="MARKETING",
            systems=["hubspot"],
            capabilities=["copywriting"],
        ),
        _agent(
            "marketing-designer",
            name="Marketing Designer",
            purpose="Spec creative assets and design briefs.",
            role="Creative",
            department="Marketing",
            persona_key="MARKETING",
            systems=["canva"],
            capabilities=["creative-brief"],
        ),
        _agent(
            "marketing-ops-coordinator",
            name="Marketing Ops Coordinator",
            purpose="Coordinate publish checklist and channel handoff.",
            role="Marketing Operations",
            department="Marketing",
            persona_key="MARKETING",
            systems=["hubspot", "google_analytics"],
            capabilities=["campaign-ops"],
        ),
    ]
    marketing_pack = CatalogAsset(
        slug="marketing-operations-pack",
        title="Marketing Operations Pack",
        description="Four-agent campaign chain: ICP → content → design → marketing ops, with brand RAG.",
        asset_type="department_pack",
        category="department_pack",
        department="Marketing",
        tags=["marketing", "department-pack", "tier-2"],
        pricing_type="paid",
        price_cents=14900,
        pack_tier=2,
        config=_department_pack_config(
            workflow_name="Marketing campaign production chain",
            workflow_description="Sequential handoffs: ICP strategist → content writer → designer → marketing ops.",
            agents=marketing_agents,
            rag_sources=[_rag_doc("rag:brand-voice", "Brand Voice Guide", pack="marketing-operations-pack")],
            workflow_steps=[
                _invoke("traffic", "Analytics snapshot", "analytics.reports.run", connector="google_analytics"),
                _agent_step(
                    "icp_content",
                    "ICP strategy and content draft",
                    "product-icp-strategist",
                    "Define ICP focus and campaign thesis for this run.",
                    next_agent_slug="content-writer",
                    receiver_task="Draft campaign copy using the ICP briefing and brand voice guide.",
                ),
                _agent_step(
                    "design_ops",
                    "Design brief and ops handoff",
                    "marketing-designer",
                    "Produce a creative brief from prior campaign context.",
                    next_agent_slug="marketing-ops-coordinator",
                    briefing_from_steps=True,
                    receiver_task="Build publish checklist and coordinate next marketing actions.",
                ),
            ],
        ),
        required_connectors=[HUBSPOT, GOOGLE_ANALYTICS, APOLLO, NOTION, GOOGLE_DRIVE, CANVA],
        pack_children=[
            "product-icp-strategist",
            "content-writer",
            "marketing-designer",
            "marketing-ops-coordinator",
            "marketing-campaign-production",
            "marketing-operations-knowledge",
        ],
    )

    msp_pack = CatalogAsset(
        slug="msp-operations-pack",
        title="MSP Operations Pack",
        description="Service desk coordination agent, runbooks, and weekly status workflow.",
        asset_type="department_pack",
        category="department_pack",
        department="Operations",
        tags=["msp", "operations", "department-pack"],
        config=_department_pack_config(
            workflow_name="Weekly service status",
            workflow_description="Summarize ticket trends and SLA posture.",
            agents=[
                _agent(
                    "msp-coordinator",
                    name="MSP Coordinator Agent",
                    purpose="Triages service requests and summarizes SLA risk.",
                    role="Service Operations",
                    department="Operations",
                    persona_key="DEVOPS",
                    systems=["slack"],
                    capabilities=["incident-triage"],
                ),
            ],
            rag_sources=[_rag_doc("rag:runbooks", "Service Runbooks", pack="msp-operations-pack")],
            workflow_steps=[
                _agent_step("status", "Weekly status draft", "msp-coordinator", "Summarize operational health."),
                _invoke("notify", "Notify channel", "slack.post_message", connector="slack"),
            ],
        ),
        required_connectors=[SLACK],
        pack_children=["msp-operations-knowledge", "weekly-team-status-report"],
    )

    revops_pack = CatalogAsset(
        slug="revenue-operations-pack",
        title="Revenue Operations Pack",
        description="RevOps agent, pipeline definitions, and executive rollup workflow.",
        asset_type="department_pack",
        category="department_pack",
        department="Revenue Operations",
        tags=["revops", "department-pack", "starter"],
        config=_department_pack_config(
            workflow_name="RevOps executive rollup",
            workflow_description="Cross-functional KPI rollup for leadership.",
            agents=[
                _agent("revenue-operations-agent", name="Revenue Operations Agent", purpose="Pipeline hygiene and forecasting.", role="RevOps", department="Revenue Operations", persona_key="REVENUE_OPS", systems=["hubspot", "salesforce"], capabilities=["forecasting"]),
                _agent("sales-pipeline-agent", name="Sales Pipeline Agent", purpose="Pipeline review and coaching.", role="Sales Operations", department="Sales", persona_key="SALES", systems=["hubspot"], capabilities=["pipeline-review"]),
            ],
            rag_sources=[_rag_doc("rag:pipeline-definitions", "Pipeline Stage Definitions", pack="revenue-operations-pack")],
            workflow_steps=[
                _invoke("pipeline", "CRM pipeline snapshot", "hubspot.search_contacts", connector="hubspot"),
                _agent_step("revops", "RevOps review", "revenue-operations-agent", "Summarize pipeline health."),
                _agent_step("exec", "Executive narrative", "cfo-agent", "Draft leadership summary."),
            ],
        ),
        required_connectors=[HUBSPOT, SALESFORCE],
        pack_children=[
            "revenue-operations-agent",
            "sales-pipeline-agent",
            "cfo-agent",
            "executive-summary-generation",
            "revenue-operations-knowledge",
        ],
    )

    cs_pack = CatalogAsset(
        slug="customer-success-pack",
        title="Customer Success Pack",
        description="CS agent, health rubric RAG, and account monitoring workflow.",
        asset_type="department_pack",
        category="department_pack",
        department="Customer Success",
        tags=["customer-success", "department-pack"],
        config=_department_pack_config(
            workflow_name="Customer health monitoring",
            workflow_description="Monitor account signals and flag renewal risk.",
            agents=[
                _agent("customer-success-agent", name="Customer Success Agent", purpose="Health scoring and renewal risk.", role="Customer Success", department="Customer Success", persona_key="CS", systems=["hubspot"], capabilities=["health-scoring"]),
            ],
            rag_sources=[_rag_doc("rag:health-rubric", "Customer Health Rubric", pack="customer-success-pack")],
            workflow_steps=[
                _invoke("accounts", "Account signals", "hubspot.search_contacts", connector="hubspot"),
                _agent_step("health", "Health review", "customer-success-agent", "Identify at-risk accounts."),
            ],
        ),
        required_connectors=[HUBSPOT],
        pack_children=[
            "customer-success-agent",
            "customer-health-monitoring",
            "customer-success-knowledge",
        ],
    )

    hr_pack = CatalogAsset(
        slug="hr-operations-pack",
        title="HR Operations Pack",
        description="HR policy RAG and onboarding checklist workflow.",
        asset_type="department_pack",
        category="department_pack",
        department="HR",
        tags=["hr", "department-pack"],
        config=_department_pack_config(
            workflow_name="HR onboarding checklist",
            workflow_description="Guide new hire onboarding with policy references.",
            agents=[
                _agent(
                    "hr-coordinator",
                    name="HR Coordinator Agent",
                    purpose="Answers policy questions and tracks onboarding tasks.",
                    role="HR Operations",
                    department="HR",
                    persona_key="HR",
                    systems=["slack"],
                    capabilities=["onboarding"],
                ),
            ],
            rag_sources=[_rag_doc("rag:policy-handbook", "Policy Handbook", pack="hr-operations-pack")],
            workflow_steps=[
                _agent_step("onboard", "Onboarding guidance", "hr-coordinator", "Summarize onboarding steps for a new hire."),
            ],
        ),
        required_connectors=[SLACK],
        pack_children=["hr-operations-knowledge"],
    )

    support_pack = CatalogAsset(
        slug="support-operations-pack",
        title="Support Operations Pack",
        description="Zendesk ticket triage agent, support knowledge pack, and optional SLA escalation workflow.",
        asset_type="department_pack",
        category="department_pack",
        department="Support",
        tags=["support", "zendesk", "department-pack", "tier-1", "starter"],
        pricing_type="paid",
        price_cents=4900,
        pack_tier=1,
        config=_department_pack_config(
            workflow_name="New ticket → triage → escalation",
            workflow_description="Zendesk ticket lookup and AI triage with escalation path.",
            agents=[
                _agent(
                    "ticket-triage",
                    name="Ticket Triage Agent",
                    purpose="Classifies support tickets, suggests macros, and escalates priority cases.",
                    role="Support Operations",
                    department="Support",
                    persona_key="SUPPORT",
                    systems=["zendesk"],
                    capabilities=["ticket-triage", "macro-suggestion"],
                ),
            ],
            rag_sources=[
                _rag_doc("rag:help-center", "Help Center Knowledge", pack="support-operations-pack"),
                _rag_doc("rag:escalation", "Escalation Matrix", pack="support-operations-pack"),
                _rag_doc("rag:macros", "Support Macros", pack="support-operations-pack"),
            ],
            workflow_steps=[
                {
                    "id": "ticket_lookup",
                    "name": "Fetch ticket context",
                    "type": "invoke_tool",
                    "config": {
                        "action": "zendesk.tickets.get",
                        "param_sources": {"ticket_id": "$ticket_id"},
                    },
                    "requires_connector": "zendesk",
                },
                _agent_step(
                    "triage",
                    "AI ticket triage",
                    "ticket-triage",
                    "Classify urgency, suggest response macro, and flag escalation if needed.",
                ),
            ],
        ),
        required_connectors=[ZENDESK],
        pack_children=[
            "ticket-triage",
            "zendesk-ticket-triage",
            "support-operations-knowledge",
            "sla-breach-escalation",
        ],
    )

    return [marketing_pack, msp_pack, revops_pack, cs_pack, hr_pack, support_pack]


def _intelligence_packs() -> list[CatalogAsset]:
    from app.marketplace.intelligence_packs.catalog import intelligence_pack_to_marketplace_asset, list_intelligence_pack_specs

    assets: list[CatalogAsset] = []
    for spec in list_intelligence_pack_specs():
        payload = intelligence_pack_to_marketplace_asset(spec)
        required: list[dict[str, Any]] = []
        if spec.pack_id in {"sales-intelligence-pack", "prospecting-intelligence-pack"}:
            required = [
                {
                    **HUBSPOT,
                    "required": True,
                    "label": "HubSpot CRM",
                },
                {
                    **APOLLO,
                    "required": True if spec.pack_id == "prospecting-intelligence-pack" else False,
                    "label": "Apollo.io (discovery = BYO search plan)",
                },
                {**PDL, "required": False},
                *([{**CLAY, "required": False}] if spec.pack_id == "prospecting-intelligence-pack" else []),
            ]
        elif spec.pack_id == "msp-intelligence-pack":
            required = [
                {
                    **APOLLO,
                    "required": True,
                    "label": "Apollo.io (MSP company/contact discovery + lists)",
                },
                {
                    **HUBSPOT,
                    "required": True,
                    "label": "HubSpot CRM (MSP list sync)",
                },
                {**CLAY, "required": False},
            ]
        elif spec.pack_id == "marketing-intelligence-pack":
            required = [
                {**GOOGLE_SEARCH_CONSOLE, "required": False},
                {**GOOGLE_ANALYTICS, "required": False},
                {**HUBSPOT, "required": False, "label": "HubSpot CRM"},
                {**SEMRUSH, "required": False},
                {**AHREFS, "required": False},
                {**PDL, "required": False},
            ]
        elif spec.pack_id == "revops-intelligence-pack":
            required = [
                {**HUBSPOT, "required": False, "label": "HubSpot CRM"},
                {
                    "connectorType": "salesforce",
                    "label": "Salesforce",
                    "required": False,
                    "connectPath": "/connectors?type=salesforce",
                },
            ]
        elif spec.pack_id == "ai-search-intelligence-pack":
            required = [
                {**AHREFS, "required": False},
                {**FINSEO, "required": False},
                {**AI_VISIBILITY_UI, "required": False},
            ]
        elif spec.pack_id == "finance-intelligence-pack":
            required = [
                {
                    "connectorType": "quickbooks",
                    "label": "QuickBooks",
                    "required": False,
                    "connectPath": "/connectors?type=quickbooks",
                },
                {
                    "connectorType": "xero",
                    "label": "Xero",
                    "required": False,
                    "connectPath": "/connectors?type=xero",
                },
                {
                    "connectorType": "netsuite",
                    "label": "NetSuite",
                    "required": False,
                    "connectPath": "/connectors?type=netsuite",
                },
                {
                    "connectorType": "plaid",
                    "label": "Plaid (if entitled)",
                    "required": False,
                    "connectPath": "/connectors?type=plaid",
                    "requirementNote": (
                        "Plaid Link public_token exchange — not generic OAuth. "
                        "Accounts/balances/transactions only after exchange."
                    ),
                },
            ]
        elif spec.pack_id == "hr-talent-intelligence-pack":
            required = [
                {
                    "connectorType": "workday",
                    "label": "Workday",
                    "required": False,
                    "connectPath": "/connectors?type=workday",
                },
                {
                    "connectorType": "bamboohr",
                    "label": "BambooHR",
                    "required": False,
                    "connectPath": "/connectors?type=bamboohr",
                },
                {
                    "connectorType": "greenhouse",
                    "label": "Greenhouse",
                    "required": False,
                    "connectPath": "/connectors?type=greenhouse",
                },
                {
                    "connectorType": "gusto",
                    "label": "Gusto (partner OAuth)",
                    "required": False,
                    "connectPath": "/connectors?type=gusto",
                    "requirementNote": (
                        "Gusto requires partner OAuth approval before connect. "
                        "Payroll/compensation Memory/KG writes remain gated."
                    ),
                },
            ]
        elif spec.demo_systems:
            for system in spec.demo_systems:
                required.append(
                    {
                        "connectorType": system,
                        "label": system.replace("_", " ").title(),
                        "required": False,
                        "connectPath": f"/connectors?type={system}",
                    }
                )
        assets.append(
            CatalogAsset(
                slug=payload["slug"],
                title=payload["title"],
                description=payload["description"],
                asset_type="intelligence_pack",
                category="intelligence_pack",
                department=payload["department"],
                tags=payload["tags"],
                config=payload["config"],
                required_connectors=required,
            )
        )
    return assets


def list_catalog_assets() -> list[CatalogAsset]:
    """Return the full Gravitre starter library in dependency order (children before packs)."""
    from app.marketplace.seed_catalog_expansion import expansion_catalog_assets

    assets = (
        _ai_agents()
        + _workflows()
        + _knowledge_packs()
        + _intelligence_packs()
        + expansion_catalog_assets()
        + _department_packs()
    )
    slugs = [asset.slug for asset in assets]
    if len(slugs) != len(set(slugs)):
        duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
        raise ValueError(f"duplicate catalog slugs: {duplicates}")
    return assets


def catalog_assets_by_slug() -> dict[str, CatalogAsset]:
    return {asset.slug: asset for asset in list_catalog_assets()}


LEGACY_PACK_SLUG_MAP: dict[str, str] = {
    "sales-ops": "revenue-operations-pack",
    "marketing-ops": "marketing-operations-pack",
    "support-ops": "support-operations-pack",
    "finance-ops": "revenue-operations-pack",
}
