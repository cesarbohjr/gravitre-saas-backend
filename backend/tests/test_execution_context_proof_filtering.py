"""Regression coverage for canonical context proof filtering."""
from app.services.execution_context import build_execution_context


def test_generic_success_status_is_not_verified_proof():
    state = {
        "recent_connector_invocations": [
            {"id": "generic", "status": "verified"},
            {"id": "explicit", "verification_status": "verified"},
            {"id": "failed", "verification_status": "failed", "status": "verified"},
        ]
    }
    result = build_execution_context(task_state=state)
    assert [item["id"] for item in result["prior_verified_actions"]] == ["explicit"]
    assert len(result["recent_connector_invocations"]) == 3


def test_context_does_not_mutate_durable_state():
    state = {"resolved_entities": {"company": {"id": "original"}}}
    result = build_execution_context(task_state=state)
    result["resolved_entities"]["company"]["id"] = "changed"
    assert state["resolved_entities"]["company"]["id"] == "original"
