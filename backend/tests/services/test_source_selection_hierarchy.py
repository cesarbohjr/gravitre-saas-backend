"""2.0-C source hierarchy tests."""
from __future__ import annotations

from app.capability_ontology.cognitive_recipe_planner import match_recipe_for_query
from app.services.source_selection_hierarchy import SOURCE_ORDER, prefer_live_systems


def test_source_order_puts_live_systems_first() -> None:
    assert SOURCE_ORDER[0] == "live_systems"
    assert SOURCE_ORDER[-1] == "model"
    assert SOURCE_ORDER.index("company_knowledge") > SOURCE_ORDER.index("org_graph")
    assert SOURCE_ORDER.index("web") > SOURCE_ORDER.index("memory")


def test_pipeline_query_prefers_live_hubspot() -> None:
    assert prefer_live_systems("How is the pipeline?", connected_integrations=["hubspot"]) is True
    assert prefer_live_systems("How is the pipeline?", connected_integrations=[]) is False


def test_match_three_department_read_recipes() -> None:
    assert match_recipe_for_query("show my deals").recipe_id == "sales.pipeline.health"
    assert match_recipe_for_query("overdue invoices").recipe_id == "finance.receivables.overdue"
    assert match_recipe_for_query("open tickets").recipe_id == "support.issue_trends"
