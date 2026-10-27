from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.dialogue_memory_policy import load_dialogue_memory_access, live_memory_row, filter_dialogue_recall


NOW = datetime.now(timezone.utc)


def row(**changes):
    return {"id": "m1", "org_id": "org-a", "content": "current corrected preference", "is_active": True, "is_current": True, "source_connector_id": None, "created_at": NOW.isoformat(), **changes}


def db(policy=None, *, members=None, memories=None):
    client = MagicMock()
    tables = {}
    data = {
        "organization_members": [{"org_id": "org-a", "user_id": "user-a"}] if members is None else members,
        "organizations": [{"id": "org-a", "settings": {"dialogueMemory": policy or {}}}],
        "agent_memories": memories or [],
    }
    for table, rows in data.items():
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.in_.return_value = q
        q.limit.return_value = q
        q.execute.return_value = SimpleNamespace(data=rows)
        tables[table] = q
    client.table.side_effect = lambda name: tables[name]
    return client, tables


def test_policy_requires_membership_and_explicit_separate_consent():
    client, tables = db({"recallEnabled": True, "learnEnabled": False, "actorIds": ["user-a"], "retentionDays": 7})
    access = load_dialogue_memory_access(client, "org-a", "user-a")
    assert access.recall and not access.learn
    assert access.retention_days == 7
    tables["organization_members"].eq.assert_any_call("org_id", "org-a")
    tables["organization_members"].eq.assert_any_call("user_id", "user-a")
    assert not load_dialogue_memory_access(client, "org-b", "user-a").recall
    assert not load_dialogue_memory_access(client, "org-a", "other-user").recall


@pytest.mark.parametrize("policy", [{}, {"recallEnabled": "true"}, {"recallEnabled": True, "actorIds": []}, {"recallEnabled": True, "actorIds": "user-a"}, {"recallEnabled": True, "retentionDays": "7"}, {"recallEnabled": True, "retentionDays": 0}])
def test_missing_or_malformed_policy_never_enables_recall(policy):
    client, _ = db(policy)
    assert not load_dialogue_memory_access(client, "org-a", "user-a").recall


def test_revocation_and_read_failure_are_not_cached():
    client, tables = db({"recallEnabled": True, "learnEnabled": True})
    assert load_dialogue_memory_access(client, "org-a", "user-a").learn
    tables["organizations"].execute.side_effect = RuntimeError("private provider text")
    assert load_dialogue_memory_access(client, "org-a", "user-a").reason == "policy_unavailable"
    client.table.reset_mock()
    assert not load_dialogue_memory_access(client, "org-a", None).recall
    client.table.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"org_id": "foreign"}, {"is_active": False}, {"is_current": False},
    {"deleted_at": NOW.isoformat()}, {"superseded_by": "new-id"},
    {"expires_at": (NOW - timedelta(seconds=1)).isoformat()},
    {"expires_at": "malformed"}, {"valid_until": NOW.isoformat()},
    {"valid_from": (NOW + timedelta(days=1)).isoformat()},
    {"visibility": "private", "created_by": "other-user"},
    {"visibility": "unknown"}, {"created_at": (NOW - timedelta(days=8)).isoformat()},
])
def test_foreign_deleted_expired_superseded_private_and_retained_rows_are_denied(changes):
    assert not live_memory_row(row(**changes), org_id="org-a", user_id="user-a", now=NOW, retention_days=7)


def test_live_private_owner_and_valid_time_are_permitted():
    assert live_memory_row(row(visibility="private", created_by="user-a", expires_at=(NOW+timedelta(days=1)).isoformat()), org_id="org-a", user_id="user-a", now=NOW)


def test_authoritative_snapshot_replaces_stale_hit_and_drops_missing_rows():
    client, tables = db(memories=[row()])
    hits = [{"id": "m1", "content": "outdated value"}, {"id": "deleted", "content": "deleted secret"}, {"content": "unscoped graph secret"}]
    result = filter_dialogue_recall(client, "org-a", "user-a", hits)
    assert [r["content"] for r in result] == ["current corrected preference"]
    tables["agent_memories"].eq.assert_called_with("org_id", "org-a")
    assert hits[0]["content"] == "outdated value"


def test_revoked_connector_and_failed_metadata_lookup_are_denied():
    client, tables = db(memories=[row(source_connector_id="revoked")])
    with patch("app.services.memory_source_liveness.live_connector_ids", return_value=set()):
        assert filter_dialogue_recall(client, "org-a", "user-a", [{"id": "m1"}]) == []
    tables["agent_memories"].execute.side_effect = RuntimeError("private")
    diagnostic = {}
    assert filter_dialogue_recall(client, "org-a", "user-a", [{"id": "m1"}], diagnostics=diagnostic) == []
    assert diagnostic == {"candidates": 1, "permitted": 0, "reason": "metadata_unavailable"}


def test_another_agents_memory_is_denied():
    client, _ = db(memories=[row(agent_id="other-agent")])
    assert filter_dialogue_recall(client, "org-a", "user-a", [{"id": "m1"}], agent_id="agent-a") == []
