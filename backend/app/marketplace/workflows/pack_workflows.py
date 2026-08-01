"""Preconfigured intelligence-pack workflow graphs (agents + instructions + actions).

Each builder returns definition steps ready for ``steps_to_rich_contract`` /
``resolve_step_agent_seeds``. Agent seeds must match install entity seeds
(e.g. ``seo-marketing-analyst``).
"""
from __future__ import annotations

from typing import Any

from app.marketplace.workflows.msp_prospecting_list_workflow import (
    build_msp_prospecting_list_workflow_steps,
)
from app.marketplace.workflows.step_builders import agent_step, invoke_step, sandwich_workflow

# Install entity seeds (marketplace_entity_id third arg) — keep in sync with *_install.py
SLUG_MARKETING = "seo-marketing-analyst"
SLUG_REVOPS = "revenue-ops-analyst"
SLUG_AI_SEARCH = "ai-visibility-analyst"
SLUG_FINANCE = "cash-flow-analyst"
SLUG_HR = "recruiting-talent-analyst"
SLUG_SALES = "sales-pipeline-analyst"
SLUG_PROSPECTING = "lead-scouting-analyst"
SLUG_CS = "cs-health-analyst"
SLUG_EXECUTIVE = "executive-analyst"
SLUG_PLATFORM = "platform-reliability-analyst"
SLUG_SUPPORT = "support-queue-analyst"


def build_marketing_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_MARKETING,
        open_id="marketing-brief",
        open_name="Agent: SEO brief",
        open_task=(
            "Assignment: open an SEO / marketing intelligence brief. Confirm which Google Search "
            "Console property to inspect, note GA4 and HubSpot as supporting signals, and list "
            "the site inventory questions to answer. Do not invent rankings. Notify the operator "
            "that the GSC site snapshot is starting."
        ),
        tool_steps=[
            invoke_step(
                "gsc-sites",
                "List GSC Sites",
                "searchconsole.sites.list",
                connector="google_search_console",
                params={},
            ),
        ],
        close_id="marketing-summarize",
        close_name="Agent: Summarize GSC sites",
        close_task=(
            "Assignment: using prior GSC sites.list output, summarize connected properties and "
            "recommend the next SEO checks (coverage, top queries — without writing raw query "
            "strings into Memory/KG). Notify the operator with a short briefing."
        ),
    )


def build_revops_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_REVOPS,
        open_id="revops-brief",
        open_name="Agent: RevOps rollup brief",
        open_task=(
            "Assignment: open a RevOps pipeline rollup brief. Confirm HubSpot is the CRM source "
            "of truth for this snapshot and list which pipeline stages matter for forecast "
            "heuristic. Notify the operator that the pipeline inventory is starting."
        ),
        tool_steps=[
            invoke_step(
                "hubspot-pipelines",
                "List HubSpot Pipelines",
                "hubspot.pipelines.list",
                connector="hubspot",
                params={},
            ),
        ],
        close_id="revops-summarize",
        close_name="Agent: Summarize pipelines",
        close_task=(
            "Assignment: using prior HubSpot pipelines.list output, summarize pipeline names and "
            "stage counts for RevOps. Flag missing CRM connection clearly. Notify the operator."
        ),
    )


def build_ai_search_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_AI_SEARCH,
        open_id="ai-search-brief",
        open_name="Agent: AI visibility brief",
        open_task=(
            "Assignment: open an AI search / Brand Radar brief for brand 'Gravitree' (US). "
            "Confirm Ahrefs Brand Radar as the primary read; note Finseo / UI scrape as optional "
            "when connected. Do not store raw AI answer text in Memory/KG. Notify start."
        ),
        tool_steps=[
            invoke_step(
                "brand-radar-overview",
                "Brand Radar Overview",
                "ahrefs.brand_radar.overview",
                connector="ahrefs",
                params={"brand": "Gravitree", "country": "us"},
            ),
        ],
        close_id="ai-search-summarize",
        close_name="Agent: Summarize Brand Radar",
        close_task=(
            "Assignment: summarize Brand Radar overview metrics (impressions/mentions/SoV) for "
            "the operator. Call out gaps if Ahrefs is disconnected. Recommend next visibility checks."
        ),
    )


def build_finance_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_FINANCE,
        open_id="finance-brief",
        open_name="Agent: Cash flow brief",
        open_task=(
            "Assignment: open a cash-flow intelligence brief. Confirm QuickBooks as the primary "
            "read for this snapshot (Xero/NetSuite/Plaid only if already connected). Do not write "
            "payroll or banking PII into Memory/KG. Notify the operator that company info pull starts."
        ),
        tool_steps=[
            invoke_step(
                "qb-company",
                "QuickBooks Company Info",
                "quickbooks.companyinfo.get",
                connector="quickbooks",
                params={},
            ),
        ],
        close_id="finance-summarize",
        close_name="Agent: Summarize company info",
        close_task=(
            "Assignment: summarize QuickBooks company info for the cash-flow brief. If the call "
            "failed, state the connector gap and stop safely. Notify the operator."
        ),
    )


def build_hr_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_HR,
        open_id="hr-brief",
        open_name="Agent: Recruiting brief",
        open_task=(
            "Assignment: open a recruiting talent brief. Confirm Greenhouse as the ATS source for "
            "open jobs. Do not scrape LinkedIn; keep employee PII out of Memory/KG. Notify start."
        ),
        tool_steps=[
            invoke_step(
                "greenhouse-jobs",
                "List Greenhouse Jobs",
                "greenhouse.jobs.list",
                connector="greenhouse",
                params={},
            ),
        ],
        close_id="hr-summarize",
        close_name="Agent: Summarize open jobs",
        close_task=(
            "Assignment: summarize Greenhouse open jobs (titles, counts, notable roles) for the "
            "recruiting brief. Flag if Greenhouse is disconnected. Notify the operator."
        ),
    )


def build_sales_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_SALES,
        open_id="sales-brief",
        open_name="Agent: Pipeline brief",
        open_task=(
            "Assignment: open a sales pipeline brief. Confirm HubSpot CRM pipelines as the source. "
            "This is pipeline management — not outbound prospecting. Notify start."
        ),
        tool_steps=[
            invoke_step(
                "hubspot-pipelines",
                "List HubSpot Pipelines",
                "hubspot.pipelines.list",
                connector="hubspot",
                params={},
            ),
        ],
        close_id="sales-summarize",
        close_name="Agent: Summarize pipelines",
        close_task=(
            "Assignment: summarize HubSpot deal pipelines and stages for the sales brief. "
            "Recommend focus stages. Notify the operator."
        ),
    )


def build_prospecting_workflow_steps() -> list[dict[str, Any]]:
    """Primary prospecting pack canvas — agent sandwich around Apollo/HubSpot tools."""
    open_task = (
        "Assignment: open an outbound prospecting brief. Confirm ICP keywords and target list "
        'names ("Prospecting Pack Scout List" / "Prospecting Pack Sync List"). Plan Apollo org '
        "then people search. Paid Apollo search may be required for discovery; list create works "
        "on free plans. Notify the operator that scouting is starting."
    )
    close_task = (
        "Assignment: using prior Apollo org/people search and list-create results, summarize "
        "companies/contacts found and list IDs created. Note HubSpot sync list status. If search "
        "failed due to plan limits, say so clearly. Notify the operator with next membership steps."
    )
    return [
        agent_step("prospecting-brief", "Agent: ICP & scout plan", open_task, agent_slug=SLUG_PROSPECTING),
        invoke_step(
            "apollo-orgs",
            "Find Companies",
            "apollo.organizations.search",
            connector="apollo",
            params={"q_organization_name": "Microsoft", "per_page": 5},
        ),
        invoke_step(
            "apollo-people",
            "Find Contacts",
            "apollo.people.search",
            connector="apollo",
            params={"q_keywords": "VP Sales", "per_page": 5},
        ),
        invoke_step(
            "apollo-list",
            "Create Apollo List",
            "apollo.lists.create",
            connector="apollo",
            params={"name": "Prospecting Pack Scout List", "modality": "contacts"},
        ),
        invoke_step(
            "hubspot-list",
            "Create HubSpot List",
            "hubspot.lists.create",
            connector="hubspot",
            params={"name": "Prospecting Pack Sync List"},
        ),
        agent_step(
            "prospecting-summarize",
            "Agent: Summarize scout results",
            close_task,
            agent_slug=SLUG_PROSPECTING,
            briefing_from_steps=True,
        ),
    ]


def build_cs_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_CS,
        open_id="cs-brief",
        open_name="Agent: Account health brief",
        open_task=(
            "Assignment: open a customer-success health brief. Confirm HubSpot CRM + Zendesk "
            "support as read sources for retention signals. Notify that the health snapshot starts."
        ),
        tool_steps=[
            invoke_step(
                "hubspot-pipelines",
                "List HubSpot Pipelines",
                "hubspot.pipelines.list",
                connector="hubspot",
                params={},
            ),
            invoke_step(
                "hubspot-deals",
                "List HubSpot Deals",
                "hubspot.deals.list",
                connector="hubspot",
                params={"limit": 10},
            ),
            invoke_step(
                "zendesk-tickets",
                "List Zendesk Tickets",
                "zendesk.tickets.list",
                connector="zendesk",
                params={"limit": 10},
            ),
        ],
        close_id="cs-summarize",
        close_name="Agent: Health briefing",
        close_task=(
            "Assignment: synthesize HubSpot pipeline/deal signals with Zendesk ticket volume into "
            "a short account-health briefing. Flag renewals risk hypotheses without inventing data. "
            "Notify the operator."
        ),
    )


def build_executive_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_EXECUTIVE,
        open_id="exec-brief",
        open_name="Agent: Macro brief",
        open_task=(
            "Assignment: open an executive macro brief. Plan to read FRED GDP and a SEC EDGAR "
            "search for context. Gravitree-managed sources — no customer OAuth. Notify start."
        ),
        tool_steps=[
            invoke_step(
                "fred-gdp",
                "Fetch FRED GDP",
                "fred.series.get",
                connector="fred",
                params={"series_id": "GDP"},
            ),
            invoke_step(
                "sec-filings",
                "Search SEC EDGAR filings",
                "sec_edgar.filings.search",
                connector="sec_edgar",
                params={"query": "Microsoft"},
            ),
        ],
        close_id="exec-summarize",
        close_name="Agent: Macro summary",
        close_task=(
            "Assignment: summarize FRED GDP and SEC search highlights for the executive brief. "
            "Keep it decision-useful and cite series/query used. Notify the operator."
        ),
    )


def build_platform_health_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_PLATFORM,
        open_id="platform-brief",
        open_name="Agent: Reliability brief",
        open_task=(
            "Assignment: open a platform reliability brief. Plan to pull org-local health KPIs "
            "(approvals, flaky connectors, stalled runs). No new external connectors. Notify start."
        ),
        tool_steps=[
            invoke_step(
                "platform-health-snapshot",
                "Platform Health Snapshot",
                "platform.health.snapshot",
                connector="platform",
                params={},
            ),
        ],
        close_id="platform-summarize",
        close_name="Agent: Reliability recommendations",
        close_task=(
            "Assignment: turn platform.health.snapshot into ranked recommendations (approval "
            "latency, connector auth churn, stalled workflows). Notify the operator."
        ),
    )


def build_support_workflow_steps() -> list[dict[str, Any]]:
    return sandwich_workflow(
        agent_slug=SLUG_SUPPORT,
        open_id="support-brief",
        open_name="Agent: Support queue brief",
        open_task=(
            "Assignment: open a technical support brief. Confirm Zendesk as the ticket source and "
            "list what to check in the open queue. Notify that ticket inventory is starting."
        ),
        tool_steps=[
            invoke_step(
                "zendesk-tickets",
                "List Zendesk Tickets",
                "zendesk.tickets.list",
                connector="zendesk",
                params={"limit": 15},
            ),
        ],
        close_id="support-summarize",
        close_name="Agent: Queue summary",
        close_task=(
            "Assignment: summarize open Zendesk tickets (volume, themes if present). Recommend "
            "escalations using playbook knowledge. Notify the operator."
        ),
    )


def build_msp_workflow_steps() -> list[dict[str, Any]]:
    """Delegate to the gold-standard MSP prospecting builder."""
    return build_msp_prospecting_list_workflow_steps()


# pack_id → builder (support included once demo install exists)
PACK_WORKFLOW_BUILDERS: dict[str, Any] = {
    "marketing-intelligence-pack": build_marketing_workflow_steps,
    "revops-intelligence-pack": build_revops_workflow_steps,
    "ai-search-intelligence-pack": build_ai_search_workflow_steps,
    "finance-intelligence-pack": build_finance_workflow_steps,
    "hr-talent-intelligence-pack": build_hr_workflow_steps,
    "sales-intelligence-pack": build_sales_workflow_steps,
    "prospecting-intelligence-pack": build_prospecting_workflow_steps,
    "customer-success-intelligence-pack": build_cs_workflow_steps,
    "msp-intelligence-pack": build_msp_workflow_steps,
    "executive-intelligence-pack": build_executive_workflow_steps,
    "platform-health-intelligence-pack": build_platform_health_workflow_steps,
    "support-intelligence-pack": build_support_workflow_steps,
}


def assert_pack_workflow_preconfigured(steps: list[dict[str, Any]]) -> None:
    """Raise AssertionError if steps lack agent instructions or tool actions."""
    if not steps:
        raise AssertionError("workflow has no steps")
    agent_steps = [s for s in steps if s.get("type") == "agent"]
    tool_steps = [s for s in steps if s.get("type") == "invoke_tool"]
    if not agent_steps:
        raise AssertionError("workflow missing agent steps with instructions")
    if not tool_steps:
        raise AssertionError("workflow missing invoke_tool actions")
    for step in agent_steps:
        task = str((step.get("metadata") or {}).get("task") or "").strip()
        if len(task) < 40:
            raise AssertionError(f"agent step {step.get('id')} missing substantive task")
        if not (step.get("metadata") or {}).get("agent_seed"):
            raise AssertionError(f"agent step {step.get('id')} missing agent_seed")
    for step in tool_steps:
        action = str((step.get("config") or {}).get("action") or "").strip()
        if "." not in action:
            raise AssertionError(f"tool step {step.get('id')} missing vendor.action")
        if not step.get("requires_connector"):
            raise AssertionError(f"tool step {step.get('id')} missing requires_connector")
