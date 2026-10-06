"""IF / Switch / Decision nodes route: untaken branches are skipped, not executed."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.workflows import graph_model
from app.workflows.branching import ConditionContext, ConditionError, evaluate_condition
from app.workflows.builder_sync import graph_to_definition
from app.workflows.handlers import ConditionHandler
from app.workflows.registry import StepContext


def _ctx(**params):
    return ConditionContext(parameters=params)


@pytest.mark.parametrize(
    ("expr", "params", "expected"),
    [
        ("score > 80", {"score": 91}, True),
        ("score > 80", {"score": 12}, False),
        ("$score >= 80 and $region == EMEA", {"score": 80, "region": "emea"}, True),
        ("$score >= 80 && $region == EMEA", {"score": 80, "region": "US"}, False),
        ("$tier == gold or $score > 90", {"tier": "silver", "score": 95}, True),
        ("not ($tier == gold)", {"tier": "silver"}, True),
        ("$stage != 'closed won'", {"stage": "closed won"}, False),
        ("$email contains '@acme.com'", {"email": "Jo@ACME.com"}, True),
        ("$tags not contains vip", {"tags": ["new", "trial"]}, True),
        ("$missing > 3", {}, False),
        ("$ready == true", {"ready": "true"}, True),
        ("$status == closed", {"status": "closed"}, True),
        ("$owner == empty", {"owner": ""}, True),
    ],
)
def test_evaluate_condition(expr, params, expected):
    assert evaluate_condition(expr, _ctx(**params)) is expected


def test_condition_reads_earlier_step_outputs_by_name_and_input():
    ctx = ConditionContext(
        step_outputs={"n1": {"score": 88, "lead": {"owner": "dana"}}},
        node_names={"lead_scorer": "n1"},
        upstream={"n1": {"score": 88, "lead": {"owner": "dana"}}},
    )
    assert evaluate_condition("steps.lead_scorer.score > 80", ctx) is True
    assert evaluate_condition("{{steps.Lead Scorer.lead.owner}} == dana", ctx) is True
    assert evaluate_condition("steps.n1.lead.owner == dana", ctx) is True
    assert evaluate_condition("input.score > 90", ctx) is False


def test_malformed_condition_raises():
    with pytest.raises(ConditionError):
        evaluate_condition("($a == 1", _ctx(a=1))


def _handler_ctx(config, params, step_outputs=None):
    return StepContext(
        settings=Settings(),
        org_id="org",
        user_id=None,
        run_id=None,
        environment_name="production",
        step_id="c1",
        step_type="condition",
        step_index=0,
        config=config,
        parameters=params,
        step_outputs=step_outputs or {},
        client=None,
        is_dry_run=False,
    )


def test_switch_picks_first_matching_case_then_default():
    paths = [
        {"id": "hot", "label": "Hot", "condition": "$score > 80"},
        {"id": "warm", "label": "Warm", "condition": "$score > 40"},
        {"id": "cold", "label": "Cold", "is_default": True},
    ]
    cfg = {"builder_node_type": "switch", "strategy": "rule-based", "paths": paths}
    assert ConditionHandler().execute(_handler_ctx(cfg, {"score": 95}))["branch"] == "hot"
    assert ConditionHandler().execute(_handler_ctx(cfg, {"score": 55}))["branch"] == "warm"
    out = ConditionHandler().execute(_handler_ctx(cfg, {"score": 5}))
    assert out["branch"] == "cold"
    assert out["method"] == "default"


def test_ai_decision_calls_model_and_maps_label():
    paths = [{"id": "p1", "label": "Escalate"}, {"id": "p2", "label": "Self-serve"}]
    cfg = {"builder_node_type": "decision", "strategy": "ai-assisted", "paths": paths, "instructions": "pick"}
    response = type("R", (), {"parsed": {"branch": "Self-serve", "reasoning": "low risk", "confidence": 0.8}, "content": ""})()
    router = AsyncMock()
    router.complete.return_value = response
    with patch("app.services.model_router.get_model_router", return_value=router):
        out = ConditionHandler().execute(_handler_ctx(cfg, {"upstream_outputs": {"a": {"risk": "low"}}}))
    assert out["branch"] == "p2"
    assert out["method"] == "ai"
    assert router.complete.await_count == 1


def test_ai_decision_preview_does_not_call_model():
    paths = [{"id": "p1", "label": "A"}, {"id": "p2", "label": "B", "is_default": True}]
    cfg = {"builder_node_type": "decision", "strategy": "ai-assisted", "paths": paths}
    with patch("app.services.model_router.get_model_router") as router:
        out = ConditionHandler().simulate(_handler_ctx(cfg, {}))
    router.assert_not_called()
    assert out["branch"] == "p2"


def _if_graph():
    nodes = [
        {"id": "src", "node_type": "source", "title": "Start"},
        {"id": "if1", "node_type": "task", "title": "Ready?", "metadata": {"builder_node_type": "if"},
         "config": {"expression": "$ready == true"}},
        {"id": "yes", "node_type": "task", "title": "Send Slack"},
        {"id": "no", "node_type": "task", "title": "Create deal"},
        {"id": "after_yes", "node_type": "task", "title": "Log"},
        {"id": "merge", "node_type": "task", "title": "Merge", "metadata": {"builder_node_type": "merge"}},
    ]
    edges = [
        {"from_node_id": "src", "to_node_id": "if1"},
        {"from_node_id": "if1", "to_node_id": "yes", "condition": {"branch": "true"}},
        {"from_node_id": "if1", "to_node_id": "no", "condition": {"branch": "false"}},
        {"from_node_id": "yes", "to_node_id": "after_yes"},
        {"from_node_id": "after_yes", "to_node_id": "merge"},
        {"from_node_id": "no", "to_node_id": "merge"},
    ]
    return graph_model.build_execution_graph(nodes, edges)


def test_untaken_branch_and_its_descendants_are_skipped_but_merge_runs():
    graph = _if_graph()
    outputs = {"src": {"passthrough": True}, "if1": {"branch": "false"}}
    assert graph_model.untaken_branch_reason(graph, "yes", outputs, []) is not None
    assert graph_model.untaken_branch_reason(graph, "no", outputs, []) is None
    outputs["yes"] = graph_model.untaken_branch_reason(graph, "yes", outputs, [])
    outputs["no"] = {"ok": True}
    outputs["after_yes"] = graph_model.untaken_branch_reason(graph, "after_yes", outputs, [])
    assert outputs["after_yes"] is not None
    assert graph_model.untaken_branch_reason(graph, "merge", outputs, []) is None


def test_on_failure_skip_does_not_cut_downstream():
    graph = _if_graph()
    outputs = {"if1": {"branch": "true"}, "yes": {"skipped": True, "reason": "on_failure_skip"}}
    assert graph_model.untaken_branch_reason(graph, "after_yes", outputs, ["yes"]) is None


def test_edge_branches_survive_checkpoint_round_trip():
    graph = _if_graph()
    rebuilt = graph_model.build_execution_graph(
        list(graph.nodes_by_id.values()), graph_model.graph_edge_dicts(graph)
    )
    assert rebuilt.edge_branches == graph.edge_branches


def test_decision_paths_compile_from_metadata():
    nodes = [
        {"id": "d1", "node_type": "decision", "title": "Route", "metadata": {
            "builder_node_type": "decision",
            "decisionConfig": {"strategy": "hybrid", "conditions": "Route by risk"},
            "outputPaths": [
                {"id": "hi", "label": "High", "condition": "$risk > 7"},
                {"id": "lo", "label": "Low", "isDefault": True},
            ],
        }},
        {"id": "n2", "node_type": "task", "title": "Lead Scorer"},
    ]
    step = next(s for s in graph_to_definition(nodes, [])["steps"] if s["id"] == "d1")
    cfg = step["config"]
    assert [p["id"] for p in cfg["paths"]] == ["hi", "lo"]
    assert cfg["paths"][1]["is_default"] is True
    assert cfg["instructions"] == "Route by risk"
    assert cfg["expression"] == ""
    assert cfg["node_aliases"]["lead_scorer"] == "n2"


def test_if_node_paths_use_node_expression():
    nodes = [{"id": "if1", "node_type": "task", "title": "IF", "metadata": {
        "builder_node_type": "if",
        "outputPaths": [{"id": "true", "label": "True"}, {"id": "false", "label": "False", "isDefault": True}],
    }, "config": {"expression": "$score > 80"}}]
    cfg = graph_to_definition(nodes, [])["steps"][0]["config"]
    assert ConditionHandler().execute(_handler_ctx(cfg, {"score": 90}))["branch"] == "true"
    assert ConditionHandler().execute(_handler_ctx(cfg, {"score": 10}))["branch"] == "false"
