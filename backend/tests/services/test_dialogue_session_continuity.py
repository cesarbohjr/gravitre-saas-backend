import json

from app.services.dialogue_session_continuity import build_session_continuity


def build(**kwargs):
    return build_session_continuity(**{"org_id": "org-a", "user_id": "user-a", "conversation_id": "conv-a", "history": [], "task_state": {}, **kwargs})


def test_latest_user_corrections_are_bounded_and_not_authority():
    result = build(history=[{"role": "user", "content": "old choice"}, {"role": "assistant", "content": "assistant invented a fact"}, {"role": "user", "content": "Actually I meant the new choice"}], task_state={"pending_task": {"status": "awaiting_confirm", "params": {"secret": "do-not-copy"}}})
    assert "newest corrections before older recalled facts" in result.section
    assert "historical confirmations never authorize" in result.section
    assert "new choice" in result.section
    assert "assistant invented" not in result.section
    assert "do-not-copy" not in result.section
    assert result.pending
    assert "choice" not in json.dumps(result.diagnostics())


def test_foreign_bindings_missing_identity_and_resolved_tasks():
    assert build(user_id=None, history=[{"role": "user", "content": "secret"}]).section == ""
    assert build(task_state={"org_id": "org-b"}, history=[{"role": "user", "content": "secret"}]).section == ""
    assert build(history=[{"role": "user", "org_id": "org-b", "content": "foreign secret"}]).section == ""
    assert build(task_state={"pending_task": {"status": "completed"}}).section == ""


def test_json_stored_state_limits_and_no_cross_session_cache():
    state = json.dumps({"pending_task": {"status": "awaiting_params"}})
    result = build(task_state=state, history=[{"role": "user", "content": str(i) + "x"*1000} for i in range(20)])
    assert result.recent_user_turns == 3
    assert len(result.section) < 2200
    assert result.pending
    assert build().section == ""


def test_existing_pending_action_and_offer_shapes_are_supported():
    for key in ("pending_action", "offered_action"):
        assert build(task_state={key: {"status": "awaiting_confirm"}}).pending
