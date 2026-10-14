from app.services.lifecycle_envelope import (
    CUSTOMER_STAGE,
    build_lifecycle_envelope,
    enrich_task_state_with_lifecycle_envelope,
    patch_needs_lifecycle_refresh,
)


def test_customer_stage_maps_completed():
    env = build_lifecycle_envelope(
        {
            "pending_task": {"status": "executed", "params": {"invoke_action": "x.y.z"}},
            "execution_observations": [
                {
                    "success": True,
                    "structured": {"verification_status": "verified"},
                    "capability_id": "x.y.z",
                }
            ],
        },
        org_id="org-1",
        conversation_id="conv-1",
    )
    assert env["customer_stage"] == CUSTOMER_STAGE["COMPLETED"]
    assert env["logical_action_id"]


def test_persist_refresh_detection():
    assert patch_needs_lifecycle_refresh({"pending_task": {"status": "awaiting_confirm"}})
    assert not patch_needs_lifecycle_refresh({"persona_override": "x"})


def test_enrich_writes_envelope_keys():
    state = enrich_task_state_with_lifecycle_envelope({"pending_task": None})
    assert "lifecycle_envelope" in state
    assert state["action_lifecycle"] == state["lifecycle_envelope"]["semantic_stage"]
