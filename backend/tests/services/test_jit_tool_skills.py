"""3.0-E eligible-set + versioned JIT skills (not a second runtime)."""
from __future__ import annotations

from app.connectors.action_catalog.f1_read_slice import F1_CATALOG_ACTIONS
from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.services.jit_skill_procedure import (
    SKILL_REVISION,
    format_jit_skill_section,
    load_jit_procedures,
)
from app.services.jit_tool_discovery import (
    HARD_CAP_ELIGIBLE,
    attach_examples_to_tools,
    rank_tool_names,
    search_eligible_action_specs,
)
from app.services.progressive_tool_schemas import execute_search_catalog_tools


def test_eligible_set_never_dumps_full_catalog():
    catalog_n = len(all_catalog_action_specs())
    assert catalog_n > HARD_CAP_ELIGIBLE
    found = search_eligible_action_specs(
        query="website traffic last 30 days",
        capability_id="analytics.traffic_overview",
        connected=["google_analytics", "google_search_console", "hubspot", "github", "slack"],
        include_writes=False,
    )
    assert 0 < len(found) <= HARD_CAP_ELIGIBLE
    assert len(found) < catalog_n
    ids = {row.action_id for row in found}
    assert "google_analytics.reports.run" in ids
    assert all(row.kind != "write" for row in found)


def test_f1_eligible_protected_when_vendor_connected():
    found = search_eligible_action_specs(
        query="deals",
        capability_id="crm.deals.read",
        connected=["hubspot"],
    )
    ids = {row.action_id for row in found}
    assert "hubspot.deals.search" in F1_CATALOG_ACTIONS
    assert "hubspot.deals.search" in ids or "hubspot.deals.list" in ids


def test_disconnected_vendor_excluded():
    found = search_eligible_action_specs(
        query="list github issues",
        connected=["hubspot"],
    )
    assert all(not row.action_id.startswith("github.") for row in found)


def test_search_hits_github_issues_when_connected():
    found = search_eligible_action_specs(
        query="list github issues",
        connected=["github"],
    )
    ids = {row.action_id for row in found}
    assert any("issue" in action_id for action_id in ids)


def test_attach_examples_does_not_grow_tool_count():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "github_issues_list",
                "description": "List issues",
            },
            "invoke_action": "github.issues.list",
        }
    ]
    out = attach_examples_to_tools(tools)
    assert len(out) == 1
    desc = str((out[0].get("function") or {}).get("description") or "")
    assert "Example:" in desc or out[0].get("jit_examples")


def test_rank_tool_names_prefers_query_tokens():
    names = rank_tool_names(
        "github issues",
        ["hubspot_deals_search", "github_issues_list", "slack_conversations_list"],
        max_load=2,
    )
    assert names[0] == "github_issues_list"


def test_search_catalog_tools_uses_ranker():
    loaded, result = execute_search_catalog_tools(
        {"query": "github issues"},
        full_by_name={
            "hubspot_deals_search": {"function": {"name": "hubspot_deals_search"}},
            "github_issues_list": {
                "function": {"name": "github_issues_list"},
                "invoke_action": "github.issues.list",
            },
        },
        loaded_names=set(),
        max_load=1,
        connected=["github"],
    )
    assert "github_issues_list" in loaded
    assert result["count"] == 1


def test_search_catalog_tools_prefers_eligible_connected_vendor():
    loaded, result = execute_search_catalog_tools(
        {"query": "deals"},
        full_by_name={
            "hubspot_deals_list": {
                "function": {"name": "hubspot_deals_list"},
                "invoke_action": "hubspot.deals.list",
            },
            "github_issues_list": {
                "function": {"name": "github_issues_list"},
                "invoke_action": "github.issues.list",
            },
        },
        loaded_names=set(),
        max_load=2,
        connected=["hubspot"],
        capability_id="crm.deals.read",
    )
    assert "hubspot_deals_list" in loaded
    assert "github_issues_list" not in loaded
    assert result["count"] >= 1


def test_skills_are_versioned_procedures_not_runtime():
    skills = load_jit_procedures(
        query="website traffic",
        capability_id="analytics.traffic_overview",
        department="marketing",
        connected=["google_analytics"],
    )
    assert skills
    skill = skills[0]
    assert skill.version == SKILL_REVISION
    assert skill.owner
    assert skill.last_verified
    assert skill.tests
    assert skill.source in {"recipe", "tool_knowledge"}
    import app.services.jit_skill_procedure as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "def execute(" not in source
    assert "not a second agent runtime" in source.lower()


def test_tool_knowledge_skill_requires_connected_vendor():
    none = load_jit_procedures(query="hubspot lists enrollment", connected=["google_analytics"])
    assert all(not s.skill_id.startswith("tool_knowledge:hubspot") for s in none)
    hit = load_jit_procedures(query="hubspot lists enrollment", connected=["hubspot"])
    assert any(s.skill_id.startswith("tool_knowledge:hubspot") for s in hit)


def test_format_section_mentions_write_gate():
    text = format_jit_skill_section(
        query="pipeline deals",
        capability_id="crm.deals.read",
        department="sales",
        connected=["hubspot"],
    )
    assert "react_write_gate" in text
    assert "procedure_only" in text
