"""Phase D — unified turn trace, structured response blocks, harness registry."""
from __future__ import annotations

from app.services.cognitive_agent_benchmark import (
    MANDATORY_SCENARIOS,
    list_mandatory_scenario_ids,
    scenarios_for_layer,
)
from app.services.cognitive_harness_behavior import harness_behavior_section
from app.services.cognitive_trace_engine import (
    attach_cognitive_turn_trace,
    start_cognitive_turn_trace,
    unify_turn_id,
)
from app.services.structured_assistant_response import (
    ResponseBlock,
    blocks_from_dicts,
    blocks_from_ga4_reports,
    merge_blocks_with_prose,
    render_response_blocks,
)


def test_unify_turn_id_prefers_cognitive_trace() -> None:
    turn_id = unify_turn_id(
        {
            "cognitive_turn_trace": {"turn_id": "trace-primary"},
            "resolution_trace": {"turn_id": "resolution-secondary"},
            "_cognitive_turn_id": "kernel-id",
            "execution_plan": {"plan_id": "plan-id"},
        }
    )
    assert turn_id == "trace-primary"


def test_start_cognitive_turn_trace_links_resolution() -> None:
    trace = start_cognitive_turn_trace(
        conversation_id="conv-1",
        tenant_id="org-1",
        task_state={"resolution_trace": {"turn_id": "res-1"}},
    )
    assert trace.turn_id
    assert trace.linked.get("resolution_trace") == "res-1"
    assert any(s.stage == "gateway" for s in trace.stages)


def test_attach_cognitive_turn_trace_aligns_resolution_turn_id() -> None:
    trace = start_cognitive_turn_trace(
        conversation_id="conv-1",
        tenant_id="org-1",
        task_state={},
    )
    merged = attach_cognitive_turn_trace(
        {"resolution_trace": {"turn_id": "old-id", "steps": []}},
        trace,
    )
    assert merged["cognitive_turn_trace"]["turn_id"] == trace.turn_id
    assert merged["resolution_trace"]["turn_id"] == trace.turn_id
    assert merged["_cognitive_turn_id"] == trace.turn_id


def test_blocks_from_ga4_reports_renders_metrics() -> None:
    current = {
        "metricHeaders": [{"name": "activeUsers"}, {"name": "sessions"}],
        "totals": [{"metricValues": [{"value": "1200"}, {"value": "3400"}]}],
    }
    previous = {
        "metricHeaders": [{"name": "activeUsers"}, {"name": "sessions"}],
        "totals": [{"metricValues": [{"value": "1000"}, {"value": "3000"}]}],
    }
    blocks = blocks_from_ga4_reports(
        property_name="Main Site",
        current=current,
        previous=previous,
    )
    assert len(blocks) == 1
    assert blocks[0].type == "metrics"
    assert blocks[0].title == "Main Site (last 30 days)"
    rendered = render_response_blocks(blocks)
    assert "Active users" in rendered
    assert "1,200" in rendered
    merged = merge_blocks_with_prose(blocks, "Traffic is steady.")
    assert "Traffic is steady." in merged
    assert "Sessions" in merged


def test_blocks_from_dicts_round_trip() -> None:
    raw = [
        ResponseBlock(
            type="metrics",
            title="GA4",
            metrics=(("Users", "500", "↑ 10%"),),
        ).as_dict()
    ]
    blocks = blocks_from_dicts(raw)
    assert len(blocks) == 1
    assert blocks[0].metrics[0][0] == "Users"


def test_harness_behavior_section_formats_rules() -> None:
    section = harness_behavior_section("Rule one.", "Rule two.")
    assert "HARNESS RULES" in section
    assert "Rule one." in section


def test_mandatory_benchmark_registry_includes_phase_d() -> None:
    ids = list_mandatory_scenario_ids()
    assert "D-trace" in ids
    assert "D-blocks" in ids
    trace_scenarios = scenarios_for_layer("trace")
    assert any(s.pytest_node == "test_unify_turn_id_prefers_cognitive_trace" for s in trace_scenarios)
    assert len(MANDATORY_SCENARIOS) >= 16
