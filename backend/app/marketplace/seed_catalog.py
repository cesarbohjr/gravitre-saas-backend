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
    config: dict[str, Any] = {"action": action, "tool_action": action}
    if connector:
        config["vendor"] = connector
        config["connector"] = connector
        if "." in action:
            _vendor, selected = action.split(".", 1)
            config["selectedAction"] = selected
            config["selected_action"] = selected
    step: dict[str, Any] = {
        "id": step_id,
        "name": name,
        "type": "invoke_tool",
        "config": config,
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
                _invoke("lookup", "HubSpot contact lookup", "hubspot.contacts.search", connector="hubspot"),
                _agent_step("qualify", "Qualify lead", "sales-pipeline-agent", "Score HubSpot contact fit against ICP, recommend next sales step, and flag missing firmographics."),
            ],
        ),
        (
            "monthly-executive-reporting",
            "Monthly Executive Reporting",
            "Finance",
            [],
            [
                _agent_step("summarize", "Executive summary", "cfo-agent", "Draft a monthly executive KPI narrative covering revenue, margin, and risks with clear owners."),
                _invoke("notify", "Notify leadership", "slack.post_message", connector="slack"),
            ],
        ),
        (
            "customer-health-monitoring",
            "Customer Health Monitoring",
            "Customer Success",
            [HUBSPOT],
            [
                _invoke("accounts", "Pull account signals", "hubspot.contacts.search", connector="hubspot"),
                _agent_step("health", "Health score review", "customer-success-agent", "Flag at-risk HubSpot accounts with evidence, churn drivers, and a concrete save play for CS."),
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
                    "Define ICP focus and campaign thesis for this run using analytics signals and brand constraints.",
                    next_agent_slug="content-writer",
                    receiver_task="Draft campaign copy using the ICP briefing and brand voice guide with CTA variants.",
                ),
                _agent_step(
                    "design_ops",
                    "Design brief and ops handoff",
                    "marketing-designer",
                    "Produce a creative brief from prior campaign context including channels, assets, and due dates.",
                    next_agent_slug="marketing-ops-coordinator",
                    briefing_from_steps=True,
                    receiver_task="Build publish checklist and coordinate next marketing actions with owners and SLAs.",
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
                _agent_step("attribute", "Attribution review", "marketing-analyst", "Summarize channel contribution from analytics, call out low-confidence gaps, and recommend budget shifts."),
            ],
        ),
        (
            "competitive-intelligence-monitoring",
            "Competitive Intelligence Monitoring",
            "Marketing",
            [],
            [
                _agent_step("scan", "Competitive scan", "competitor-research-agent", "Summarize competitor product, pricing, and messaging moves with sources and confidence labels."),
                _agent_step("brief", "Marketing brief", "marketing-analyst", "Translate competitive intel into concrete campaign actions, owners, and measurement checks."),
            ],
        ),
        (
            "salesforce-pipeline-review",
            "Salesforce Pipeline Review",
            "Sales",
            [SALESFORCE],
            [
                _invoke("pipeline", "Pipeline snapshot", "salesforce.query", connector="salesforce"),
                _agent_step("review", "Pipeline review", "sales-pipeline-agent", "Highlight stalled Salesforce deals with stage age, risk reasons, and recommended owner actions."),
            ],
        ),
        (
            "executive-summary-generation",
            "Executive Summary Generation",
            "Revenue Operations",
            [],
            [
                _agent_step("revops", "RevOps rollup", "revenue-operations-agent", "Summarize cross-functional revenue KPIs, pipeline health, and handoff gaps for leadership."),
                _agent_step("exec", "Executive narrative", "cfo-agent", "Produce a board-ready executive summary with decisions needed and quantified risks."),
            ],
        ),
        (
            "weekly-team-status-report",
            "Weekly Team Status Report",
            "Revenue Operations",
            [SLACK],
            [
                _agent_step("collect", "Collect status themes", "revenue-operations-agent", "Draft weekly status bullets covering wins, blockers, and asks with clear owners for Slack."),
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
                        "param_sources": {"ticket_id": "$TICKET_ID"},
                    },
                    "requires_connector": "zendesk",
                },
                _agent_step(
                    "triage",
                    "AI ticket triage",
                    "ticket-triage",
                    "Classify Zendesk ticket urgency, suggest a response macro, and flag escalation paths when needed.",
                ),
            ],
        ),
        (
            "msp-prospects-clay-hubspot-enrichment",
            "MSP Prospects Clay Enrichment → HubSpot Sync",
            "Sales",
            # Asset-local required flags — do not mutate shared APOLLO/CLAY constants.
            [
                {**APOLLO, "required": True, "label": "Apollo.io (MSP Prospects list + search)"},
                {**CLAY, "required": True, "label": "Clay (enrichment push / CRM sync)"},
                HUBSPOT,
            ],
            build_msp_enrichment_workflow_steps(),
        ),
    ]
    ticket_id_install_var = {
        "key": "TICKET_ID",
        "label": "Zendesk ticket ID",
        "required": True,
        "description": "Ticket to look up for triage (install/run parameter for $TICKET_ID).",
    }
    assets: list[CatalogAsset] = []
    for slug, title, department, connectors, steps in definitions:
        is_msp_enrichment = slug == "msp-prospects-clay-hubspot-enrichment"
        if is_msp_enrichment:
            install_vars = list(MSP_ENRICHMENT_INSTALL_VARS)
        elif slug == "zendesk-ticket-triage":
            install_vars = [ticket_id_install_var]
        else:
            install_vars = []
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
                install_variables=install_vars,
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



def _msp_service_desk_3_assets() -> list[CatalogAsset]:
    """Marketplace 3.0 flagship MSP Service Desk operating capability."""
    coordinator = _agent(
        "msp-service-desk-coordinator",
        name="MSP Service Desk Coordinator",
        purpose="Coordinates triage, SLA risk, ownership, escalation, and customer communication across the service desk.",
        role="Service Desk Operations",
        department="MSP Service Desk",
        persona_key="SUPPORT",
        systems=["halopsa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"],
        capabilities=["ticket-triage", "sla-management", "service-coordination"],
    )
    resolution = _agent(
        "msp-resolution-specialist",
        name="MSP Resolution Specialist",
        purpose="Builds evidence-backed remediation plans from ticket history, device context, runbooks, and prior resolutions.",
        role="Technical Resolution",
        department="MSP Service Desk",
        persona_key="DEVOPS",
        systems=["intune", "jumpcloud", "jamf_pro", "huntress", "sentinelone", "crowdstrike"],
        capabilities=["root-cause-analysis", "remediation-planning", "incident-analysis"],
    )
    optimizer = _agent(
        "msp-service-optimizer",
        name="MSP Service Optimizer",
        purpose="Finds recurring problems, knowledge gaps, backlog patterns, and automation opportunities across service operations.",
        role="Service Improvement",
        department="MSP Service Desk",
        persona_key="SUPPORT",
        systems=["halopsa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"],
        capabilities=["problem-management", "knowledge-gap-analysis", "service-optimization"],
    )

    knowledge_docs = [
        _rag_doc("rag:msp-sla-policy", "SLA & Priority Matrix", pack="msp-service-desk-3"),
        _rag_doc("rag:msp-triage-policy", "Ticket Triage & Routing Policy", pack="msp-service-desk-3"),
        _rag_doc("rag:msp-escalation", "Escalation & Major Incident Matrix", pack="msp-service-desk-3"),
        _rag_doc("rag:msp-runbooks", "Service Remediation Runbooks", pack="msp-service-desk-3"),
        _rag_doc("rag:msp-client-comms", "Client Communication Standards", pack="msp-service-desk-3"),
        _rag_doc("rag:msp-kb", "Service Desk Knowledge Base", pack="msp-service-desk-3"),
    ]

    kpis = [
        {"key": "mtta", "label": "Mean time to acknowledge", "unit": "minutes", "direction": "decrease", "source": "tickets"},
        {"key": "mttr", "label": "Mean time to resolve", "unit": "minutes", "direction": "decrease", "source": "tickets"},
        {"key": "sla_compliance", "label": "SLA compliance", "unit": "percent", "direction": "increase", "source": "tickets"},
        {"key": "automation_rate", "label": "Automation rate", "unit": "percent", "direction": "increase", "source": "play_runs"},
        {"key": "backlog", "label": "Open ticket backlog", "unit": "count", "direction": "decrease", "source": "tickets"},
        {"key": "reopen_rate", "label": "Ticket reopen rate", "unit": "percent", "direction": "decrease", "source": "tickets"},
        {"key": "first_contact_resolution", "label": "First-contact resolution", "unit": "percent", "direction": "increase", "source": "tickets"},
        {"key": "tickets_rescued", "label": "SLA-risk tickets rescued", "unit": "count", "direction": "increase", "source": "play_runs"},
        {"key": "knowledge_gap_rate", "label": "Knowledge gap rate", "unit": "percent", "direction": "decrease", "source": "knowledge_events"},
        {"key": "customer_update_latency", "label": "Customer update latency", "unit": "minutes", "direction": "decrease", "source": "ticket_events"},
    ]

    def play(
        key: str,
        name: str,
        description: str,
        *,
        agent_slug: str,
        task: str,
        outcome_event: str,
        kpi_keys: list[str],
        trigger: dict[str, Any],
        approvals: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "name": name,
            "description": description,
            "trigger": trigger,
            "workflow_steps": [
                _agent_step(
                    f"{key}-analyze",
                    name,
                    agent_slug,
                    task,
                    briefing_from_steps=True,
                )
            ],
            "outcome_events": [outcome_event],
            "kpi_keys": kpi_keys,
            "approvals": approvals or [],
            "verification": {
                "mode": "source_of_record",
                "required": True,
                "executionLifecycle": [
                    "requested",
                    "executing",
                    "accepted",
                    "verifying",
                    "completed|failed|verification_inconclusive",
                ],
            },
        }

    plays = [
        play(
            "intelligent-ticket-intake",
            "Intelligent Ticket Intake",
            "Classify, prioritize, enrich, and route incoming service work using client, asset, SLA, urgency, and sentiment context.",
            agent_slug="msp-service-desk-coordinator",
            task="Review the incoming service item, apply the SLA and triage policies, identify missing context, recommend priority and ownership, and record evidence for every decision.",
            outcome_event="ticket_triaged",
            kpi_keys=["mtta", "automation_rate", "sla_compliance"],
            trigger={"type": "event", "event": "ticket.created"},
        ),
        play(
            "resolution-copilot",
            "Resolution Copilot",
            "Assemble ticket history, endpoint context, prior resolutions, and runbooks into an evidence-backed remediation plan.",
            agent_slug="msp-resolution-specialist",
            task="Build a remediation plan from available service history, endpoint/security context, and runbooks. Separate verified facts from hypotheses and require approval before consequential remediation.",
            outcome_event="resolution_plan_prepared",
            kpi_keys=["mttr", "first_contact_resolution"],
            trigger={"type": "event", "event": "ticket.investigation_requested"},
            approvals=[{"when": "consequential_write", "role": "service_manager"}],
        ),
        play(
            "sla-rescue",
            "SLA Rescue",
            "Detect tickets approaching breach, diagnose why they are stalled, and coordinate intervention before the SLA is missed.",
            agent_slug="msp-service-desk-coordinator",
            task="Identify the blocking condition for an SLA-risk ticket, determine the safest next action and owner, and escalate according to the SLA matrix before the breach threshold.",
            outcome_event="ticket_sla_saved",
            kpi_keys=["sla_compliance", "tickets_rescued", "mttr"],
            trigger={"type": "threshold", "metric": "sla_remaining_minutes", "operator": "lte", "value": 60},
        ),
        play(
            "stale-ticket-recovery",
            "Stale Ticket Recovery",
            "Find tickets stalled on technicians, customers, vendors, approvals, or missing information and restart the correct next step.",
            agent_slug="msp-service-desk-coordinator",
            task="Classify why the ticket is stale, identify the party or evidence required to move it forward, and propose or execute the policy-safe recovery action.",
            outcome_event="stale_ticket_recovered",
            kpi_keys=["backlog", "mttr", "automation_rate"],
            trigger={"type": "threshold", "metric": "hours_without_progress", "operator": "gte", "value": 24},
        ),
        play(
            "recurring-problem-hunter",
            "Recurring Problem Hunter",
            "Cluster repeated service issues across clients, users, and assets to expose root problems and preventive automation opportunities.",
            agent_slug="msp-service-optimizer",
            task="Analyze recurring service patterns, distinguish symptoms from likely common causes, and recommend a problem record, runbook change, automation, or preventive maintenance action.",
            outcome_event="recurring_problem_detected",
            kpi_keys=["reopen_rate", "backlog", "mttr"],
            trigger={"type": "scheduled", "cadence": "daily"},
        ),
        play(
            "client-communication-manager",
            "Client Communication Manager",
            "Prepare timely customer updates from verified service status, SLA posture, sentiment, and business impact.",
            agent_slug="msp-service-desk-coordinator",
            task="Prepare a client-safe update using only verified service facts, current SLA posture, next action, and expected follow-up. Never invent resolution timing.",
            outcome_event="client_update_prepared",
            kpi_keys=["customer_update_latency", "sla_compliance"],
            trigger={"type": "event", "event": "ticket.material_status_changed"},
            approvals=[{"when": "external_message", "role": "service_owner"}],
        ),
        play(
            "knowledge-gap-miner",
            "Knowledge Gap Miner",
            "Turn repeated unresolved questions, failed retrievals, escalations, and manual fixes into prioritized knowledge improvements.",
            agent_slug="msp-service-optimizer",
            task="Identify missing or weak knowledge that caused repeated manual investigation or escalation, then propose a KB article, SOP change, decision rule, or new reusable skill with supporting evidence.",
            outcome_event="knowledge_gap_identified",
            kpi_keys=["knowledge_gap_rate", "mttr", "automation_rate"],
            trigger={"type": "scheduled", "cadence": "weekly"},
        ),
        play(
            "service-desk-optimization-review",
            "Service Desk Optimization Review",
            "Review MTTA, MTTR, SLA, backlog, reopen rate, automation coverage, and recurring problems to recommend measurable operating improvements.",
            agent_slug="msp-service-optimizer",
            task="Review the service KPI dataset and Play outcomes, rank the highest-impact operational bottlenecks, and recommend concrete changes with an owner and measurable target.",
            outcome_event="service_optimization_recommended",
            kpi_keys=["mtta", "mttr", "sla_compliance", "automation_rate", "backlog", "reopen_rate"],
            trigger={"type": "scheduled", "cadence": "weekly"},
        ),
    ]

    dataset = {
        "entities": [
            {"name": "tickets", "source": "psa", "primary_key": "id", "fields": ["id", "client_id", "status", "priority", "created_at", "acknowledged_at", "resolved_at", "sla_due_at", "owner_id", "reopen_count"]},
            {"name": "clients", "source": "psa", "primary_key": "id", "fields": ["id", "name", "service_tier", "account_owner"]},
            {"name": "assets", "source": "endpoint_management", "primary_key": "id", "fields": ["id", "client_id", "user_id", "device_type", "health_status"]},
            {"name": "ticket_events", "source": "psa", "primary_key": "id", "fields": ["id", "ticket_id", "event_type", "actor_type", "created_at"]},
            {"name": "play_runs", "source": "gravitre", "primary_key": "id", "fields": ["id", "play_key", "status", "started_at", "completed_at", "outcome_events"]},
        ],
        "metrics": [
            {"key": "mtta", "label": "MTTA", "formula": "avg(acknowledged_at - created_at)", "unit": "minutes"},
            {"key": "mttr", "label": "MTTR", "formula": "avg(resolved_at - created_at)", "unit": "minutes"},
            {"key": "sla_compliance", "label": "SLA compliance", "formula": "resolved_within_sla / resolved_tickets", "unit": "percent"},
            {"key": "automation_rate", "label": "Automation rate", "formula": "verified_automated_outcomes / eligible_outcomes", "unit": "percent"},
            {"key": "backlog", "label": "Backlog", "formula": "count(open_tickets)", "unit": "count"},
            {"key": "reopen_rate", "label": "Reopen rate", "formula": "reopened_tickets / resolved_tickets", "unit": "percent"},
            {"key": "first_contact_resolution", "label": "First-contact resolution", "formula": "first_contact_resolved / resolved_tickets", "unit": "percent"},
            {"key": "tickets_rescued", "label": "Tickets rescued", "formula": "count(ticket_sla_saved)", "unit": "count"},
            {"key": "knowledge_gap_rate", "label": "Knowledge gap rate", "formula": "knowledge_gap_events / investigated_tickets", "unit": "percent"},
            {"key": "customer_update_latency", "label": "Customer update latency", "formula": "avg(customer_update_at - material_status_change_at)", "unit": "minutes"},
        ],
    }

    dashboard = {
        "title": "MSP Service Desk Outcomes",
        "refresh_mode": "event",
        "metrics": [
            {"kpi_key": "mtta", "label": "MTTA", "visualization": "trend", "description": "Average time from ticket creation to acknowledgement."},
            {"kpi_key": "mttr", "label": "MTTR", "visualization": "trend", "description": "Average time from ticket creation to verified resolution."},
            {"kpi_key": "sla_compliance", "label": "SLA compliance", "visualization": "progress", "description": "Share of resolved tickets completed inside SLA."},
            {"kpi_key": "automation_rate", "label": "Automation rate", "visualization": "trend", "description": "Verified eligible service outcomes completed automatically."},
            {"kpi_key": "backlog", "label": "Open backlog", "visualization": "metric", "description": "Open service items requiring action."},
            {"kpi_key": "reopen_rate", "label": "Reopen rate", "visualization": "trend", "description": "Resolved tickets subsequently reopened."},
            {"kpi_key": "first_contact_resolution", "label": "First-contact resolution", "visualization": "progress", "description": "Tickets resolved without repeat handling."},
            {"kpi_key": "tickets_rescued", "label": "SLA tickets rescued", "visualization": "metric", "description": "At-risk tickets moved back inside policy before breach."},
        ],
    }

    agent_assets = [
        CatalogAsset(
            slug=slug,
            title=cfg["name"],
            description=cfg["purpose"],
            asset_type="ai_agent",
            category="ai_agent",
            department="MSP Service Desk",
            tags=["msp", "service-desk", "marketplace-3", "agent"],
            config=cfg,
        )
        for slug, cfg in [
            ("msp-service-desk-coordinator", coordinator),
            ("msp-resolution-specialist", resolution),
            ("msp-service-optimizer", optimizer),
        ]
    ]

    play_assets = [
        CatalogAsset(
            slug=f"msp-{cfg['key']}",
            title=cfg["name"],
            description=cfg["description"],
            asset_type="play",
            category="play",
            department="MSP Service Desk",
            tags=["msp", "service-desk", "marketplace-3", "play", cfg["key"]],
            config=cfg,
        )
        for cfg in plays
    ]

    knowledge_asset = CatalogAsset(
        slug="msp-service-desk-3-knowledge",
        title="MSP Service Desk 3.0 Knowledge Pack",
        description="SLA policy, triage rules, escalation matrix, remediation runbooks, customer communication standards, and service desk knowledge.",
        asset_type="knowledge_pack",
        category="knowledge_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "marketplace-3", "knowledge"],
        config=_knowledge_pack(knowledge_docs),
    )

    dataset_asset = CatalogAsset(
        slug="msp-service-desk-3-dataset",
        title="MSP Service Desk 3.0 Dataset Pack",
        description="Normalized service desk entities and KPI definitions for verified service outcomes.",
        asset_type="dataset_pack",
        category="dataset_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "marketplace-3", "dataset", "kpi"],
        config=dataset,
    )

    dashboard_asset = CatalogAsset(
        slug="msp-service-desk-3-dashboard",
        title="MSP Service Desk 3.0 Dashboard Pack",
        description="Outcome dashboard for MTTA, MTTR, SLA, automation, backlog, reopen rate, first-contact resolution, and SLA rescue.",
        asset_type="dashboard_pack",
        category="dashboard_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "marketplace-3", "dashboard", "outcomes"],
        config=dashboard,
    )

    connector_alternatives = [
        ["halopsa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"],
        ["intune", "jumpcloud", "jamf_pro"],
        ["huntress", "sentinelone", "crowdstrike", "connectsecure"],
    ]
    optional_connectors = [
        {
            "connectorType": connector_type,
            "label": connector_type.replace("_", " ").title(),
            "required": False,
            "connectPath": f"/connectors?type={connector_type}",
        }
        for connector_type in sorted({item for group in connector_alternatives for item in group})
    ]

    pack = CatalogAsset(
        slug="msp-service-desk-3",
        title="MSP Service Desk 3.0",
        description="Operate the service desk with eight governed Plays spanning intake, resolution, SLA rescue, stale-ticket recovery, recurring-problem detection, client communication, knowledge improvement, and service optimization.",
        asset_type="outcome_pack",
        category="outcome_pack",
        department="MSP Service Desk",
        tags=["msp", "service-desk", "marketplace-3", "outcome-pack", "flagship"],
        business_outcome="Reduce manual service work while improving response time, resolution time, SLA performance, and service quality.",
        use_case="MSP service desk operations",
        estimated_hours_saved=40.0,
        pricing_type="paid",
        price_cents=24900,
        pack_tier=3,
        required_connectors=optional_connectors,
        config={
            "marketplace_version": "3.0",
            "outcome_contract": {
                "problem": "MSP service desks lose technician capacity to manual triage, stalled tickets, repetitive investigation, inconsistent client communication, and reactive SLA management.",
                "target_outcome": "Reduce MTTA and MTTR, improve SLA compliance and first-contact resolution, shrink backlog, and increase verified automation without weakening governance.",
                "baseline_metric": "mttr",
                "success_criteria": [
                    "All eight required Plays install and bind to the canonical workflow runtime.",
                    "Every consequential action follows approval policy and source-of-record verification.",
                    "The dashboard can calculate the declared service KPIs from normalized service data.",
                    "Outcome events reconcile to Play Runs and Activity evidence.",
                ],
                "outcome_events": [
                    "ticket_triaged",
                    "resolution_plan_prepared",
                    "ticket_sla_saved",
                    "stale_ticket_recovered",
                    "recurring_problem_detected",
                    "client_update_prepared",
                    "knowledge_gap_identified",
                    "service_optimization_recommended",
                ],
                "kpis": kpis,
                "verification_required": True,
            },
            "agents": [coordinator, resolution, optimizer],
            "plays": plays,
            "knowledge": knowledge_docs,
            "dataset": dataset,
            "dashboard": dashboard,
            "skills": [
                "ticket-triage",
                "root-cause-analysis",
                "sla-risk-analysis",
                "customer-communication",
                "knowledge-gap-analysis",
                "service-optimization",
            ],
            "connector_alternatives": connector_alternatives,
        },
        pack_children=[
            "msp-service-desk-coordinator",
            "msp-resolution-specialist",
            "msp-service-optimizer",
            *[asset.slug for asset in play_assets],
            "msp-service-desk-3-knowledge",
            "msp-service-desk-3-dataset",
            "msp-service-desk-3-dashboard",
        ],
    )

    return [
        *agent_assets,
        *play_assets,
        knowledge_asset,
        dataset_asset,
        dashboard_asset,
        pack,
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
                    "Assignment: define ICP focus and campaign thesis for this run. Confirm GA4 "
                    "snapshot inputs, cite brand voice RAG, and hand off a clear brief to content. "
                    "Notify the operator that campaign production has started.",
                    next_agent_slug="content-writer",
                    receiver_task=(
                        "Assignment: draft campaign copy using the ICP briefing and brand voice "
                        "guide. Keep claims factual; flag missing product facts. Notify when draft ready."
                    ),
                ),
                _agent_step(
                    "design_ops",
                    "Design brief and ops handoff",
                    "marketing-designer",
                    "Assignment: produce a creative brief from prior campaign context and copy. "
                    "List asset formats needed and brand constraints. Notify design handoff complete.",
                    next_agent_slug="marketing-ops-coordinator",
                    briefing_from_steps=True,
                    receiver_task=(
                        "Assignment: build publish checklist, schedule next marketing actions, and "
                        "notify the operator that the campaign chain is ready for review."
                    ),
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
                _agent_step(
                    "status",
                    "Weekly status draft",
                    "msp-coordinator",
                    "Assignment: open a weekly MSP service-status brief. Summarize ticket trends, "
                    "SLA posture, and top risks using assigned runbooks. Notify the operator that "
                    "status drafting has started.",
                ),
                _invoke("notify", "Notify channel", "slack.post_message", connector="slack"),
                _agent_step(
                    "status_close",
                    "Confirm status posted",
                    "msp-coordinator",
                    "Assignment: confirm the Slack status notification was posted (or report the "
                    "connector gap). List follow-ups for the ops team. Notify completion.",
                    briefing_from_steps=True,
                ),
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
                _invoke("pipeline", "CRM pipeline snapshot", "hubspot.pipelines.list", connector="hubspot"),
                _agent_step(
                    "revops",
                    "RevOps review",
                    "revenue-operations-agent",
                    "Assignment: summarize HubSpot pipeline inventory for RevOps hygiene — stage "
                    "coverage, forecast heuristic risks, and data gaps. Notify with a short rollup.",
                    briefing_from_steps=True,
                ),
                _agent_step(
                    "exec",
                    "Executive narrative",
                    "cfo-agent",
                    "Assignment: draft a leadership-ready narrative from the RevOps review. Keep "
                    "numbers tied to prior CRM snapshot; flag missing CRM connection clearly. Notify.",
                    briefing_from_steps=True,
                ),
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
                _invoke("accounts", "Account signals", "hubspot.deals.list", connector="hubspot"),
                _agent_step(
                    "health",
                    "Health review",
                    "customer-success-agent",
                    "Assignment: using prior HubSpot deal signals and the customer health rubric, "
                    "identify at-risk accounts and renewal watch items. Do not invent usage data. "
                    "Notify the operator with a short risk list.",
                    briefing_from_steps=True,
                ),
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
                _agent_step(
                    "onboard",
                    "Onboarding guidance",
                    "hr-coordinator",
                    "Assignment: open an HR onboarding brief for a new hire. Use the policy handbook "
                    "RAG to list day-1 through week-1 checklist items. Notify that guidance is ready.",
                ),
                _invoke("notify", "Notify HR channel", "slack.post_message", connector="slack"),
                _agent_step(
                    "onboard_close",
                    "Confirm onboarding notify",
                    "hr-coordinator",
                    "Assignment: confirm Slack notify for onboarding checklist (or report connector "
                    "gap). Summarize remaining owner actions. Notify completion.",
                    briefing_from_steps=True,
                ),
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
                _agent_step(
                    "triage_open",
                    "Open triage assignment",
                    "ticket-triage",
                    "Assignment: open a Zendesk ticket triage brief. Confirm ticket_id input and "
                    "which macros/escalation matrix apply. Notify that ticket lookup is starting.",
                ),
                {
                    "id": "ticket_lookup",
                    "name": "Fetch ticket context",
                    "type": "invoke_tool",
                    "config": {
                        "action": "zendesk.tickets.get",
                        "tool_action": "zendesk.tickets.get",
                        "vendor": "zendesk",
                        "connector": "zendesk",
                        "selectedAction": "tickets.get",
                        "selected_action": "tickets.get",
                        "param_sources": {"ticket_id": "$TICKET_ID"},
                    },
                    "requires_connector": "zendesk",
                },
                _agent_step(
                    "triage",
                    "AI ticket triage",
                    "ticket-triage",
                    "Assignment: using prior Zendesk ticket context, classify urgency, suggest a "
                    "response macro from assigned knowledge, and flag escalation if SLA risk is "
                    "present. Notify the operator with the triage outcome.",
                    briefing_from_steps=True,
                ),
            ],
        ),
        required_connectors=[ZENDESK],
        install_variables=[
            {
                "key": "TICKET_ID",
                "label": "Zendesk ticket ID",
                "required": True,
                "description": "Ticket to look up for triage (install/run parameter for $TICKET_ID).",
            }
        ],
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
                # Clay required: pack installs MSP enrichment (clay.leads.push → clay.crm.sync).
                *([{**CLAY, "required": True, "label": "Clay (list enrichment)"}] if spec.pack_id == "prospecting-intelligence-pack" else []),
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
        + _msp_service_desk_3_assets()
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
