import pytest
from app.services.conversation_state_service import ConversationStateService
from tests.test_eco013_plan_authority_postgrest import CONV, ORG, OTHER_CONV, plan_api, pytestmark


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_api", ["claim_rpc", "missing_rpc"], indirect=True)
async def test_claim_preserves_committed_topic(plan_api, mock_settings, request):
    rpc = request.node.callspec.params["plan_api"] == "claim_rpc"
    pending = {"status": "awaiting_confirm", "actor_id": "fixture-owner"}
    initial = {"task_revision": 8, "topic": "original", "pending_task": pending}
    plan_api.write(initial)
    foreign = plan_api.read(OTHER_CONV)

    def commit_topic():
        plan_api.write({**initial, "topic": "updated", "task_revision": 9})

    if rpc:
        plan_api.before_rpc = commit_topic
    else:
        plan_api.before_patch = commit_topic
    result = await ConversationStateService(mock_settings).compare_and_set_pending_status(
        CONV, ORG, client=plan_api.client, expected_status="awaiting_confirm", actor_id="fixture-owner",
        updates={"pending_task": {**pending, "status": "executing", "execution_claim_id": "fixture-claim",
                                 "claimed_at": "2026-11-23T00:00:00Z"}},
    )
    assert plan_api.read(OTHER_CONV) == foreign
    assert result and plan_api.read()["pending_task"]["execution_claim_id"] == "fixture-claim"
    assert any(method == "PATCH" for method, _ in plan_api.requests) == (not rpc)
    assert (plan_api.read()["topic"], plan_api.read()["task_revision"]) == ("updated", 9 if rpc else 10)


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_field", ["pending_task", "execution_plan"])
async def test_fallback_rejects_changed_authority(plan_api, mock_settings, changed_field):
    pending = {"status": "awaiting_confirm", "actor_id": "fixture-owner", "label": "first"}
    plan_api.write({"task_revision": 8, "pending_task": pending})
    fresh = {"task_revision": 9, "pending_task": pending}
    fresh[changed_field] = ({**pending, "label": "second"} if changed_field == "pending_task"
                            else {"terminal_status": "cancelled"})
    plan_api.before_patch = lambda: plan_api.write(fresh)
    result = await ConversationStateService(mock_settings).compare_and_set_pending_status(
        CONV, ORG, client=plan_api.client, expected_status="awaiting_confirm", actor_id="fixture-owner",
        updates={"pending_task": {**pending, "status": "executing", "execution_claim_id": "fixture-claim"}},
    )
    assert result is False
    assert plan_api.read() == fresh
