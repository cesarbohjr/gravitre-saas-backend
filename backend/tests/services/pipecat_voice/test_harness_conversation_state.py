"""Pin the harness database boundary and PostgREST revision predicates."""
import pytest
from tests.support.fake_supabase import FakeSupabase


def test_fake_revision_fences_and_timestamp_predicate():
    db = FakeSupabase()
    cid = db.seed_conversation(org_id="org", user_id="user")
    q = db.table("conversations")
    assert q.update({"task_state": {"task_revision": 1}}).eq("id", cid).filter("task_state->>task_revision", "is", "null").execute().data
    assert not db.table("conversations").update({"task_state": {}}).eq("id", cid).filter("task_state->>task_revision", "is", "null").execute().data
    assert not db.table("conversations").update({"task_state": {}}).eq("id", cid).eq("task_state->>task_revision", "0").execute().data
    assert db.table("conversations").update({"task_state": {"task_revision": 2}}).eq("id", cid).eq("task_state->>task_revision", "1").execute().data
    db.table("conversation_messages").insert([{"created_at": "2026-01-01"}, {"created_at": "2026-01-02"}]).execute()
    assert len(db.table("conversation_messages").select("*").gt("created_at", "2026-01-01").execute().data) == 1


@pytest.mark.asyncio
async def test_real_conversation_preparation_uses_injected_database(monkeypatch, mock_settings):
    from app.services import conversation_state_service
    from app.services.shared_turn_preparation import prepare_turn_conversation

    db = FakeSupabase()
    org, user = "org", "user"
    cid = db.seed_conversation(org_id=org, user_id=user)
    monkeypatch.setattr(conversation_state_service, "get_supabase_client", lambda *_: db)
    assert await prepare_turn_conversation(mock_settings, org_id=org, user_id=user,
                                           conversation_id=cid, user_text="Show the account status") == cid
    state = db.rows("conversations", id=cid)[0]["task_state"]
    assert state["recent_user_messages"] == ["Show the account status"]
    assert state["task_revision"] == 1
