"""Marketing / SEO Outcome Pack.

Declarations only. Organic results are verified by re-reading Search Console
for the exact page a Play changed, comparing the post-change window with an
equal-length window before the change.
"""
from __future__ import annotations

from typing import Any

from app.outcome_packs.builders import approval_step, dashboard, play, runtime_profile_actions, tool_step

PACK_ID = "marketing-seo"
DEPARTMENT = "marketing"

_PAGE_CHANGE_ACTIONS = ["manual.page_update", "manual.page_published", "semrush.position_tracking.add", "ahrefs.rank_tracker.add"]
_GSC_READ = {
    "page_url": "{record_id}",
    "start_date": "{window_start_date}",
    "end_date": "{window_end_date}",
    "dimensions": ["page"],
    "row_limit": 1,
}

KPIS: list[dict[str, Any]] = [
    {
        "key": "organic_clicks",
        "label": "Organic clicks gained",
        "description": "Extra Search Console clicks on pages a Play improved, versus the equal window before the change.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "sum",
        "department": "marketing",
        "departments": ["marketing", "growth"],
        "source_system": "google_search_console",
        "source_record_type": "page",
        "verification_recipe": "search-console-page-performance",
        "evidence_strategy": "Compare page clicks after the change with the same-length window before it.",
        "synonyms": ["organic clicks", "seo clicks", "organic traffic", "search traffic", "seo traffic", "clicks from google"],
        "definition_prompt": "I'll count the extra Search Console clicks on pages we change, compared with before the change.",
    },
    {
        "key": "organic_impressions",
        "label": "Organic impressions gained",
        "description": "Extra Search Console impressions on improved pages, versus before the change.",
        "unit": "count",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "sum",
        "department": "marketing",
        "source_system": "google_search_console",
        "source_record_type": "page",
        "verification_recipe": "search-console-page-performance",
        "evidence_strategy": "Compare page impressions after the change with the window before it.",
        "synonyms": ["impressions", "search impressions", "organic visibility"],
    },
    {
        "key": "avg_search_position",
        "label": "Average search position",
        "description": "Average Google position of improved pages after the change (lower is better).",
        "unit": "position",
        "direction": "decrease",
        "kind": "business",
        "aggregation": "avg",
        "department": "marketing",
        "source_system": "google_search_console",
        "source_record_type": "page",
        "verification_recipe": "search-console-page-performance",
        "evidence_strategy": "Read the page's average position after the change and before it.",
        "synonyms": ["rankings", "search ranking", "google ranking", "search position", "seo rankings"],
    },
    {
        "key": "organic_ctr",
        "label": "Organic click-through rate",
        "description": "Average Search Console CTR of improved pages after the change.",
        "unit": "ratio",
        "direction": "increase",
        "kind": "funnel",
        "aggregation": "avg",
        "department": "marketing",
        "source_system": "google_search_console",
        "source_record_type": "page",
        "verification_recipe": "search-console-page-performance",
        "evidence_strategy": "Read the page CTR after the change.",
        "synonyms": ["ctr", "click through rate"],
    },
    {
        "key": "pages_improved",
        "label": "Pages with more organic clicks",
        "description": "Changed pages whose organic clicks rose versus the window before the change.",
        "unit": "count",
        "direction": "increase",
        "kind": "business",
        "aggregation": "count",
        "department": "marketing",
        "source_system": "google_search_console",
        "source_record_type": "page",
        "verification_recipe": "search-console-page-performance",
        "evidence_strategy": "A page counts when post-change clicks exceed pre-change clicks.",
        "synonyms": ["pages improved", "seo wins"],
    },
]

_CLICKS_NOW = "current.rows.0.clicks"
_CLICKS_BEFORE = "baseline.rows.0.clicks"

RECIPES: list[dict[str, Any]] = [
    {
        "key": "search-console-page-performance",
        "source_system": "google_search_console",
        "record_type": "page",
        "match_actions": _PAGE_CHANGE_ACTIONS,
        "read_action": "google_search_console.searchAnalytics.query",
        "record_id_param": "page_url",
        "record_id_fields": ["record_ids.page", "page_url", "url", "entity_id"],
        "read_params": _GSC_READ,
        "baseline_read": True,
        "verification_method": "search_console_window_comparison",
        "measure_after_hours": 24 * 14,
        "measure_window_days": 28,
        "contributions": [
            {
                "metric_key": "organic_clicks",
                "when": {"field": _CLICKS_NOW, "op": "gt", "value": 0},
                "value": {"field": _CLICKS_NOW},
                "baseline": {"field": _CLICKS_BEFORE, "default": 0},
            },
            {
                "metric_key": "organic_impressions",
                "when": {"field": "current.rows.0.impressions", "op": "gt", "value": 0},
                "value": {"field": "current.rows.0.impressions"},
                "baseline": {"field": "baseline.rows.0.impressions", "default": 0},
            },
            {
                "metric_key": "avg_search_position",
                "when": {"field": "current.rows.0.position", "op": "exists"},
                "value": {"field": "current.rows.0.position"},
                "baseline": {"field": "baseline.rows.0.position", "default": 100},
            },
            {
                "metric_key": "organic_ctr",
                "when": {"field": "current.rows.0.ctr", "op": "exists"},
                "value": {"field": "current.rows.0.ctr"},
                "baseline": {"field": "baseline.rows.0.ctr", "default": 0},
            },
            {
                "metric_key": "pages_improved",
                "when": {
                    "any": [
                        {"field": _CLICKS_NOW, "op": "gt", "value_field": _CLICKS_BEFORE},
                        {
                            "all": [
                                {"field": _CLICKS_BEFORE, "op": "missing"},
                                {"field": _CLICKS_NOW, "op": "gt", "value": 0},
                            ]
                        },
                    ]
                },
                "fail_when": {"field": _CLICKS_NOW, "op": "lte", "value_field": _CLICKS_BEFORE},
            },
        ],
    },
]

_SEED_STRATEGIST = "agent:seo-strategist"
_SEED_EDITOR = "agent:seo-content-editor"

_PAGE_CHANGE = {"action": "manual.page_update", "approval": "attested"}

PLAYS: list[dict[str, Any]] = [
    play(
        "seo-content-refresh",
        "SEO Content Refresh",
        "Find pages losing clicks, prepare an evidence-based refresh, and verify the click change after publishing.",
        objective="Recover and grow organic clicks on existing pages.",
        kpis=["organic_clicks", "pages_improved", "organic_ctr"],
        outcome_event="seo_page_refreshed",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_EDITOR,
        task=(
            "Rank pages by lost clicks, explain the likely cause from search evidence, and draft a refresh "
            "brief. The page change is confirmed by the person who publishes it."
        ),
        evidence_steps=[
            tool_step("page-performance", "Read page search performance", "capability.seo.page_performance",
                      param_sources={"dimensions": ["page"], "row_limit": 100}),
        ],
        action_steps_after=[approval_step("confirm-publish", "Confirm the refresh is published", "Records the page change")],
        capability_groups=[["seo.page_performance"]],
        required_connector_groups=[["google_search_console"]],
        write_actions=[_PAGE_CHANGE],
    ),
    play(
        "keyword-opportunity-finder",
        "Keyword Opportunity Finder",
        "Find keywords where the site ranks just off page one and recommend the page to target.",
        objective="Grow organic clicks from near-miss rankings.",
        kpis=["avg_search_position", "organic_clicks"],
        outcome_event="seo_keyword_targeted",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_STRATEGIST,
        task="Rank keyword opportunities by demand and current position. Recommend one target page per keyword.",
        evidence_steps=[
            tool_step("keyword-research", "Research keyword opportunities", "capability.seo.keyword_research",
                      param_sources={"query": "$TOPIC"}),
        ],
        action_steps_after=[approval_step("confirm-target", "Confirm the target page change", "Records the page change")],
        capability_groups=[["seo.keyword_research"]],
        required_connector_groups=[["google_search_console", "semrush", "ahrefs"]],
        write_actions=[_PAGE_CHANGE],
    ),
    play(
        "competitor-content-gap",
        "Competitor Content Gap",
        "Compare organic visibility with competitors and brief the highest-value missing pages.",
        objective="Win organic demand competitors currently capture.",
        kpis=["organic_impressions", "organic_clicks"],
        outcome_event="seo_gap_briefed",
        trigger={"type": "scheduled", "cadence": "monthly"},
        agent_seed=_SEED_STRATEGIST,
        task="Identify competitor topics the site lacks, size each gap, and draft briefs. Cite the sources used.",
        evidence_steps=[
            tool_step("competitor-gap", "Compare competitor visibility", "capability.seo.competitor_analysis",
                      param_sources={"domain": "$SITE_DOMAIN", "competitors": "$COMPETITORS"}),
        ],
        action_steps_after=[approval_step("confirm-new-page", "Confirm the new page is published", "Records the page change")],
        capability_groups=[["seo.competitor_analysis"]],
        optional_connectors=["semrush", "ahrefs"],
        write_actions=[{"action": "manual.page_published", "approval": "attested"}],
    ),
    play(
        "ctr-snippet-optimizer",
        "Search Snippet Optimizer",
        "Find pages with high impressions and low CTR and rewrite titles and descriptions.",
        objective="Turn existing impressions into clicks.",
        kpis=["organic_ctr", "organic_clicks", "pages_improved"],
        outcome_event="seo_snippet_rewritten",
        trigger={"type": "scheduled", "cadence": "weekly"},
        agent_seed=_SEED_EDITOR,
        task="Draft title and meta description options for low-CTR pages with the reason each should win clicks.",
        evidence_steps=[
            tool_step("ctr-scan", "Scan page CTR", "capability.seo.page_performance",
                      param_sources={"dimensions": ["page"], "row_limit": 200}),
        ],
        action_steps_after=[approval_step("confirm-snippet", "Confirm the snippet change", "Records the page change")],
        capability_groups=[["seo.page_performance"]],
        required_connector_groups=[["google_search_console"]],
        write_actions=[_PAGE_CHANGE],
    ),
    play(
        "rank-tracking-setup",
        "Rank Tracking Setup",
        "Start tracking the keywords tied to changed pages so ranking movement is measured continuously.",
        objective="Measure ranking movement for every page Gravitre changes.",
        kpis=["avg_search_position"],
        outcome_event="seo_tracking_started",
        trigger={"type": "event", "event": "seo.page_changed"},
        agent_seed=_SEED_STRATEGIST,
        task="Choose the keywords to track for each changed page and explain why.",
        evidence_steps=[
            tool_step("tracking-keywords", "Research tracked keywords", "capability.seo.keyword_research",
                      param_sources={"query": "$PAGE_TOPIC"}),
        ],
        action_steps_after=[
            approval_step("approve-tracking", "Approve rank tracking", "Adds keywords to rank tracking"),
            tool_step("add-tracking", "Add rank tracking", "capability.seo.rank_tracking",
                      param_sources={"url": "$PAGE_URL", "keywords": "$KEYWORDS"}),
        ],
        capability_groups=[["seo.keyword_research"], ["seo.rank_tracking"]],
        required_connector_groups=[["semrush", "ahrefs"]],
        write_actions=[{"capability": "seo.rank_tracking", "approval": "always"}],
    ),
    play(
        "internal-link-boost",
        "Internal Link Boost",
        "Point internal links from strong pages to pages that need ranking support.",
        objective="Lift rankings of priority pages with internal authority.",
        kpis=["avg_search_position", "organic_clicks"],
        outcome_event="seo_internal_links_added",
        trigger={"type": "scheduled", "cadence": "monthly"},
        agent_seed=_SEED_EDITOR,
        task="Pick source pages with relevant authority and propose exact anchor text and placement.",
        evidence_steps=[
            tool_step("authority-scan", "Find strong source pages", "capability.seo.page_performance",
                      param_sources={"dimensions": ["page"], "row_limit": 200}),
        ],
        action_steps_after=[approval_step("confirm-links", "Confirm links are live", "Records the page change")],
        capability_groups=[["seo.page_performance"]],
        required_connector_groups=[["google_search_console"]],
        write_actions=[_PAGE_CHANGE],
    ),
]


def build() -> dict[str, Any]:
    config: dict[str, Any] = {
        "marketplace_version": "3.0",
        "pack_id": PACK_ID,
        "department": DEPARTMENT,
        "outcome_contract": {
            "problem": "SEO work is hard to tie to results, so effort goes to pages that do not move clicks.",
            "target_outcome": "Grow verified organic clicks and rankings on the pages Gravitre helps change.",
            "baseline_metric": "organic_clicks",
            "success_criteria": [
                "Every page change is compared with an equal window before the change in Search Console.",
                "Pages without post-change data stay unknown rather than zero.",
            ],
            "outcome_events": sorted({p["outcome_events"][0] for p in PLAYS}),
            "kpis": KPIS,
            "verification_required": True,
        },
        "objectives": [
            {"key": "grow-organic-traffic", "statement": "Grow organic search traffic", "kpi_keys": ["organic_clicks"]},
            {"key": "improve-rankings", "statement": "Improve search rankings", "kpi_keys": ["avg_search_position"]},
        ],
        "agents": [
            {
                "seed_label": _SEED_STRATEGIST,
                "name": "SEO Strategist",
                "purpose": "Find keyword and competitor opportunities and plan the highest-value page changes.",
                "role": "SEO Strategy",
                "department": "Marketing",
                "capabilities": ["keyword-research", "competitor-analysis"],
                "systems": ["google_search_console", "semrush", "ahrefs"],
            },
            {
                "seed_label": _SEED_EDITOR,
                "name": "SEO Content Editor",
                "purpose": "Draft refreshes, snippets and internal links from search evidence.",
                "role": "Content Optimization",
                "department": "Marketing",
                "capabilities": ["content-refresh", "on-page-seo"],
                "systems": ["google_search_console"],
            },
        ],
        "plays": PLAYS,
        "knowledge": [
            {"seed_label": "seo-style-guide", "title": "Content and SEO Style Guide", "type": "manual",
             "metadata": {"purpose": "Voice, on-page rules and priority topics."}},
        ],
        "dataset": {
            "entities": [
                {"name": "search_pages", "source": "google_search_console", "primary_key": "page",
                 "fields": ["page", "clicks", "impressions", "ctr", "position"]},
            ],
            "metrics": [
                {"key": row["key"], "label": row["label"], "formula": row["description"], "unit": row["unit"]}
                for row in KPIS
            ],
        },
        "dashboard": dashboard(
            title="SEO Results",
            template_id="seo-results",
            department=DEPARTMENT,
            kpis=KPIS,
            sections=[
                {"title": "Organic results", "kpi_keys": ["organic_clicks", "pages_improved"]},
                {"title": "Visibility", "kpi_keys": ["organic_impressions", "avg_search_position", "organic_ctr"]},
            ],
            system_health_kpis=["connector-health"],
        ),
        "runtime_profiles": [
            {"provider": "capability-resolved", "status": "tested", "actions": runtime_profile_actions(PLAYS)}
        ],
        "connector_alternatives": [["google_search_console"], ["semrush", "ahrefs"]],
        "verification_recipes": RECIPES,
        "governance": {"always_approve_actions": [], "max_autonomy": "act_with_approval"},
        "certification": {
            "minimum_plays": 6,
            "fixtures": {
                "search-console-page-performance": {
                    "record_id": "https://example.com/pricing",
                    "current": {"rows": [{"clicks": 140, "impressions": 4000, "ctr": 0.035, "position": 6.2}]},
                    "baseline": {"rows": [{"clicks": 90, "impressions": 3500, "ctr": 0.026, "position": 8.9}]},
                }
            },
            "degraded_scenarios": [
                {"capability": "seo.keyword_research", "unavailable_vendor": "semrush", "reason": "plan_limit"},
            ],
        },
    }
    return {
        "marketplace": {
            "slug": "marketing-seo-operator",
            "title": "SEO Results Operator",
            "description": "Grow organic clicks and rankings with six SEO Plays verified against Search Console.",
            "department_label": "Marketing",
            "tags": ["marketing", "seo", "outcome-pack"],
            "price_cents": 0,
            "pricing_type": "free",
            "required_connectors": [
                {"connectorType": "google_search_console", "label": "Google Search Console", "required": True,
                 "connectPath": "/connectors?type=google_search_console",
                 "requirementNote": "Source of record for clicks, impressions and position."},
            ],
            "business_outcome": "Grow verified organic clicks and rankings.",
            "use_case": "SEO growth",
            "estimated_hours_saved": 12.0,
        },
        "config": config,
    }
