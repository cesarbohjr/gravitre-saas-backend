"""Regression: no fabricated run counts from unrelated FAST tools."""
from __future__ import annotations

from types import SimpleNamespace

from app.operators.assistant_mode_config import resolve_assistant_tool_names
from app.services.factual_claim_honesty import (
    RUN_HISTORY_REFUSAL,
    apply_run_history_honesty_gate,
    explanation_for_missing_run_history,
    is_run_history_question,
    should_escalate_fast_for_run_history,
    tool_results_include_workflow_runs,
)


def test_detects_run_history_question():
    assert is_run_history_question("What workflows have been ran?")
    assert is_run_history_question("How many recent runs do we have?")
    assert not is_run_history_question("What is my agent status?")


def test_fast_mode_escalates_when_workflow_runs_missing():
    """Routing/tool-availability gap: FAST omits workflow_runs for run-history."""
    fast_tools = resolve_assistant_tool_names("fast", None)
    assert "workflow_runs" not in fast_tools
    assert should_escalate_fast_for_run_history(
        "fast",
        "What workflows have been ran?",
        fast_tools,
    )
    standard_tools = resolve_assistant_tool_names("standard", None)
    assert "workflow_runs" in standard_tools
    assert not should_escalate_fast_for_run_history(
        "standard",
        "What workflows have been ran?",
        standard_tools,
    )


def test_honesty_gate_refuses_fabricated_zero_runs_from_agent_status():
    """FAST + run-history + only agent_status → refuse, not invent 0 recent runs."""
    fabricated = (
        "There are 8 workflows configured and active. "
        "0 recent runs are recorded and there are 0 open alerts."
    )
    react = SimpleNamespace(
        tool_calls=[
            {
                "toolName": "assistant_agent_status",
                "result": {
                    "success": True,
                    "agents": [{"name": "Ops", "status": "active"}],
                    "total": 1,
                },
            }
        ],
        to_dict=lambda: {
            "trace": [{"toolName": "assistant_agent_status", "action": "tool"}]
        },
    )
    assert not tool_results_include_workflow_runs(react_result=react)
    gated = apply_run_history_honesty_gate(
        fabricated,
        query="What workflows have been ran?",
        react_result=react,
    )
    assert gated == RUN_HISTORY_REFUSAL
    assert "0 recent" not in gated.lower()
    assert "don't have that information" in gated.lower()

    explanation = explanation_for_missing_run_history(
        "Live data came from assistant_agent_status (1 call).",
        query="What workflows have been ran?",
        react_result=react,
    )
    assert "not retrieved" in explanation.lower() or "workflow run" in explanation.lower()


def test_honesty_gate_allows_answer_when_workflow_runs_tool_returned_data():
    answer = "You have 3 recent completed runs in the last 7 days."
    tool_results = [
        {
            "toolName": "assistant_workflow_runs",
            "result": {
                "success": True,
                "runs": [{"id": "r1", "status": "completed"}],
                "total": 3,
            },
        }
    ]
    assert tool_results_include_workflow_runs(tool_results)
    gated = apply_run_history_honesty_gate(
        answer,
        query="How many recent runs?",
        tool_results=tool_results,
    )
    assert gated == answer
