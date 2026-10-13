"""A background read-back result reaches the conversation, without clobbering newer work."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.action_lifecycle import background_verification_patch, semantic_stage_from_state


def _verifying_state(invoke="hubspot.contacts.create", record="101"):
    return {
        "pending_task": {
            "type": "connector_action",
            "status": "verifying",
            "lifecycle": "VERIFYING",
            "params": {"invoke_action": invoke, "provider_record_id": record, "args": {"email": "a@b.co"}},
        },
        "execution_observations": [
            {"success": True, "capability_id": invoke, "structured": {"id": record, "invoke_action": invoke}}
        ],
    }


def _apply(state, patch_):
    return {**state, **patch_}


def test_verified_read_back_completes_the_conversation():
    state = _verifying_state()
    assert semantic_stage_from_state(state) == "VERIFYING"
    p = background_verification_patch(
        state, invoke_action="hubspot.contacts.create", provider_record="101", terminal="completed",
        verification={"detail": "entity_found"},
    )
    assert p is not None and p["action_lifecycle"] == "COMPLETED"
    assert semantic_stage_from_state(_apply(state, p)) == "COMPLETED"


def test_failed_read_back_fails_the_conversation():
    state = _verifying_state()
    p = background_verification_patch(
        state, invoke_action="hubspot.contacts.create", provider_record="101", terminal="failed",
        verification={"detail": "entity_id_mismatch"},
    )
    assert semantic_stage_from_state(_apply(state, p)) == "FAILED"


def test_inconclusive_is_unverified_not_done():
    state = _verifying_state()
    p = background_verification_patch(
        state, invoke_action="hubspot.contacts.create", provider_record="101",
        terminal="verification_inconclusive", verification={},
    )
    assert semantic_stage_from_state(_apply(state, p)) == "EXECUTED_UNVERIFIED"


def test_newer_task_is_left_alone():
    newer = _verifying_state()
    newer["pending_task"] = {"type": "connector_action", "status": "awaiting_confirmation",
                             "params": {"invoke_action": "gmail.messages.send"}}
    assert background_verification_patch(
        newer, invoke_action="hubspot.contacts.create", provider_record="101", terminal="completed", verification={}
    ) is None
    other_record = _verifying_state(record="202")
    assert background_verification_patch(
        other_record, invoke_action="hubspot.contacts.create", provider_record="101", terminal="completed",
        verification={},
    ) is None
    other_action = _verifying_state(invoke="asana.tasks.create")
    assert background_verification_patch(
        other_action, invoke_action="hubspot.contacts.create", provider_record="101", terminal="completed",
        verification={},
    ) is None


def test_finalize_carries_the_result_into_the_conversation():
    from app.services import write_success_verification as wsv

    run_row = {
        "status": "verifying",
        "triggered_by": "user-1",
        "parameters": {"conversation_id": "conv-1", "verification_owns_terminal": True,
                       "provider_record_id": "101", "integration": "hubspot", "label": "Create contact"},
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [run_row]
    stored = _verifying_state()
    saved: list[dict] = []

    class _State:
        async def update_task_state_from(self, conversation_id, org_id, build, *, client=None, effect_record=False):
            assert conversation_id == "conv-1" and effect_record is True
            p = build(stored)
            if p:
                saved.append(p)

    with (
        patch("app.services.conversation_state_service.get_conversation_state_service", return_value=_State()),
        patch("app.workflows.repository.merge_run_parameters"),
        patch("app.services.execution_outcome.finalize_execution_outcome"),
    ):
        wsv._finalize_verified_write_run(
            client=client, org_id="org-1", run_id="run-1", invoke_action="hubspot.contacts.create",
            verification_kind="entity_get", verification={"verified": True, "entity_id": "101"},
        )
    assert saved and saved[0]["action_lifecycle"] == "COMPLETED"
