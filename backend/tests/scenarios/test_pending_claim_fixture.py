import pytest

from app.services.conversation_state_service import ConversationStateService
from tests.scenarios.conversation_harness import ORG, USER, ScenarioDB


@pytest.mark.asyncio
async def test_scenario_claim_uses_missing_rpc_fallback_once(mock_settings):
    db = ScenarioDB()
    pending = {"actor_id": USER, "status": "awaiting_confirm"}
    row = {"id": "fixture-conversation", "org_id": ORG,
           "task_state": {"topic": "keep", "task_revision": 8, "pending_task": pending}}
    db.tables["conversations"] = [row]
    service = ConversationStateService(mock_settings)

    async def claim():
        return await service.compare_and_set_pending_status(
            row["id"], ORG, client=db, actor_id=USER, expected_status="awaiting_confirm",
            updates={"pending_task": {**pending, "status": "executing", "execution_claim_id": "test-claim"}},
        )

    assert await claim()
    assert not await claim()
    stored = db.rows("conversations")[0]["task_state"]
    assert stored["topic"] == "keep"
    assert stored["task_revision"] == 9
    assert stored["pending_task"]["execution_claim_id"] == "test-claim"
