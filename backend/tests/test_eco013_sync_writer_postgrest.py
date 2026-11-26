from app.services.conversation_state_service import ConversationStateService
from tests.test_eco013_plan_authority_postgrest import CONV, ORG, plan_api, pytestmark  # noqa: F401


def test_sync_preference_preserves_concurrent_context(plan_api, mock_settings):
    initial = {"task_revision": 8, "topic": "original"}
    plan_api.write(initial)
    plan_api.before_patch = lambda: plan_api.write({"task_revision": 9, "topic": "updated"})
    saved = ConversationStateService(mock_settings).apply_task_state_change_sync(
        CONV, ORG, lambda state: state.update(preferred_connector="gmail"), client=plan_api.client
    )
    stored = plan_api.read()
    assert saved and stored["preferred_connector"] == "gmail"
    assert (stored["topic"], stored["task_revision"]) == ("updated", 10)
