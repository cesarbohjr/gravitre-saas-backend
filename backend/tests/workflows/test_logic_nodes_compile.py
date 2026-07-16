"""Canvas IF/Switch/Merge/Loop + decision compile to executable condition/noop steps."""
from __future__ import annotations

from app.config import Settings
from app.workflows.builder_sync import graph_to_definition
from app.workflows.handlers import ConditionHandler, _eval_simple_condition
from app.workflows.registry import StepContext


def test_decision_compiles_to_condition_not_noop():
    nodes = [
        {
            "id": "d1",
            "node_type": "decision",
            "title": "Route",
            "metadata": {
                "builder_node_type": "decision",
                "decisionConfig": {
                    "strategy": "rule-based",
                    "conditions": "$score == high",
                },
            },
        }
    ]
    definition = graph_to_definition(nodes, [])
    assert len(definition["steps"]) == 1
    step = definition["steps"][0]
    assert step["type"] == "condition"
    assert step["config"]["expression"] == "$score == high"
    assert step["config"]["builder_node_type"] == "decision"


def test_if_switch_merge_loop_compile():
    nodes = [
        {
            "id": "if1",
            "node_type": "task",
            "title": "IF",
            "metadata": {"builder_node_type": "if"},
            "config": {"expression": "$ready == true"},
        },
        {
            "id": "sw1",
            "node_type": "task",
            "title": "Switch",
            "metadata": {"builder_node_type": "switch"},
            "config": {"expression": "$status"},
        },
        {
            "id": "m1",
            "node_type": "task",
            "title": "Merge",
            "metadata": {"builder_node_type": "merge"},
        },
        {
            "id": "l1",
            "node_type": "task",
            "title": "Loop",
            "metadata": {"builder_node_type": "loop"},
            "config": {"max_iterations": 5},
        },
    ]
    definition = graph_to_definition(nodes, [])
    by_id = {s["id"]: s for s in definition["steps"]}
    assert by_id["if1"]["type"] == "condition"
    assert by_id["sw1"]["type"] == "condition"
    assert by_id["m1"]["type"] == "noop"
    assert by_id["m1"]["config"]["builder_node_type"] == "merge"
    assert by_id["l1"]["type"] == "noop"
    assert by_id["l1"]["config"]["max_iterations"] == 5


def test_eval_simple_condition_equality():
    ok, branch = _eval_simple_condition("$status == closed", {"status": "closed"})
    assert ok is True
    assert branch == "true"
    ok2, branch2 = _eval_simple_condition("$status == closed", {"status": "open"})
    assert ok2 is False
    assert branch2 == "false"


def test_condition_handler_execute_sets_when_branch():
    handler = ConditionHandler()
    ctx = StepContext(
        settings=Settings(),
        org_id="org",
        user_id=None,
        run_id=None,
        environment_name="production",
        step_id="c1",
        step_type="condition",
        step_index=0,
        config={"expression": "$ready == true", "builder_node_type": "if"},
        parameters={"ready": "true"},
        step_outputs={},
        client=None,
        is_dry_run=False,
    )
    out = handler.execute(ctx)
    assert out["matched"] is True
    assert out["when_branch"] == "true"
