"""Regression tests for the durable execution context projection."""
from app.services.execution_context import build_execution_context


def test_projection_preserves_source_and_verified_actions():
    state = {
        "execution_plan": {"steps": [{"id": "read-1"}]},
        "pending_action": {"status": "awaiting_approval"},
        "recent_connector_invocations": [
            {"verification_status": "accepted", "id": "unverified"},
            {"verification_status": "verified", "id": "verified"},
        ],
    }
    projected = build_execution_context(task_state=state)
    assert projected["current_plan"]["steps"][0]["id"] == "read-1"
    assert projected["pending_action"]["status"] == "awaiting_approval"
    assert [row["id"] for row in projected["prior_verified_actions"]] == ["verified"]
    projected["current_plan"]["steps"][0]["id"] = "changed"
    assert state["execution_plan"]["steps"][0]["id"] == "read-1"


def test_projection_limits_history_to_user_and_assistant():
    history = [{"role": "tool", "content": "excluded"}]
    history.extend({"role": "user", "content": str(i)} for i in range(20))
    result = build_execution_context(task_state={}, conversation_history=history)
    assert len(result["conversation_tail"]) == 12
    assert result["conversation_tail"][-1]["content"] == "19"
