"""Failure/identity contracts; real SQL uniqueness is certified in QA12."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.core.durable_insert import insert_once, outcome_delivery_id

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
RUN = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
ACTOR = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


class UniqueConflict(Exception):
    code = "23505"


class Memory:
    def __init__(self):
        self.rows = {}
        self.ambiguous = False

    def table(self, name):
        memory = self
        class Query:
            def __init__(self):
                self.payload = None
                self.filters = {}
            def insert(self, row): self.payload = deepcopy(row); return self
            def select(self, *_): return self
            def eq(self, key, value): self.filters[key] = value; return self
            def limit(self, *_): return self
            def execute(self):
                rows = memory.rows.setdefault(name, {})
                if self.payload is not None:
                    if self.payload['id'] in rows:
                        raise UniqueConflict()
                    rows[self.payload['id']] = deepcopy(self.payload)
                    return SimpleNamespace(data=[] if memory.ambiguous else [deepcopy(self.payload)])
                return SimpleNamespace(data=[deepcopy(row) for row in rows.values()
                    if all(row.get(key) == value for key, value in self.filters.items())])
        return Query()


def test_delivery_identity_scopes_and_uuid_normalization():
    base = outcome_delivery_id(ORG, RUN, "completed", "audit")
    assert base == outcome_delivery_id(ORG.upper(), RUN.upper(), "completed", "audit")
    assert len({base, outcome_delivery_id(ACTOR, RUN, "completed", "audit"),
        outcome_delivery_id(ORG, ACTOR, "completed", "audit"),
        outcome_delivery_id(ORG, RUN, "failed", "audit"),
        outcome_delivery_id(ORG, RUN, "completed", "learning")}) == 5


def test_duplicate_readback_does_not_overwrite_effect_or_mutable_state():
    db = Memory()
    row = {"id": RUN, "org_id": ORG, "type": "completed", "is_read": False}
    assert insert_once(db, "notifications", row, identity=("org_id", "type")) == (True, True)
    db.rows["notifications"][RUN]["is_read"] = True
    assert insert_once(db, "notifications", row, identity=("org_id", "type")) == (True, False)
    assert db.rows["notifications"][RUN]["is_read"] is True


@pytest.mark.parametrize("patch", [{"org_id": ACTOR}, {"type": "failed"}])
def test_collision_with_wrong_context_is_not_acknowledged(patch):
    db = Memory()
    row = {"id": RUN, "org_id": ORG, "type": "completed"}
    assert insert_once(db, "events", row, identity=("org_id", "type")) == (True, True)
    assert insert_once(db, "events", {**row, **patch}, identity=("org_id", "type")) == (False, False)
    assert db.rows["events"][RUN] == row


def test_committed_write_without_ack_resumes_by_identity_readback():
    db = Memory()
    db.ambiguous = True
    row = {"id": RUN, "org_id": ORG}
    assert insert_once(db, "events", row, identity=("org_id",)) == (False, False)
    assert insert_once(db, "events", row, identity=("org_id",)) == (True, False)
    assert len(db.rows["events"]) == 1


def test_unrelated_unique_conflict_without_matching_id_is_not_acknowledged():
    client = Mock()
    client.table.return_value.insert.return_value.execute.side_effect = UniqueConflict()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    assert insert_once(client, "events", {"id": RUN, "org_id": ORG}, identity=("org_id",)) == (False, False)


def test_storage_error_does_not_become_duplicate_acknowledgement():
    client = Mock()
    client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        insert_once(client, "events", {"id": RUN, "org_id": ORG}, identity=("org_id",))
    client.table.return_value.select.assert_not_called()


def test_replayed_inbox_delivery_does_not_repeat_optional_channels(monkeypatch):
    from app.services import notification_emitter as emitter
    from app.services import notification_preference_service as prefs
    db = Memory()
    monkeypatch.setattr(prefs, "channel_enabled", lambda *_: True)
    monkeypatch.setattr(prefs, "held_by_quiet_hours", lambda *_: False)
    callbacks = []
    for name in ("_send_email_if_configured", "_send_slack_dm_if_configured", "_publish_live_notification", "_record_connector_activity"):
        callback = Mock()
        monkeypatch.setattr(emitter, name, callback)
        callbacks.append(callback)
    kwargs = dict(org_id=ORG, user_id=ACTOR, event_type="run_completed", title="Done", body="Verified",
        delivery_id=outcome_delivery_id(ORG, RUN, "completed", "notification"),
        entity_ref={"entity_type": "workflow_run", "entity_id": RUN}, channel_hints={"bell": True, "email": True})
    assert emitter.emit_notification(db, **kwargs) == kwargs["delivery_id"]
    assert emitter.emit_notification(db, **kwargs) == kwargs["delivery_id"]
    assert all(callback.call_count == 1 for callback in callbacks)
    assert len(db.rows["notifications"]) == 1


def test_replayed_audit_keeps_dual_rows_and_optional_export_once(monkeypatch):
    from app.workflows import audit
    db = Memory()
    export = Mock()
    monkeypatch.setattr(audit, "_get_org_pii_mode", lambda *_: "standard")
    monkeypatch.setattr(audit, "_schedule_siem_dispatch", export)
    args = (db, ORG, ACTOR, "workflow.execute.completed", "workflow_run", RUN)
    delivery_id = outcome_delivery_id(ORG, RUN, "completed", "audit")
    assert audit.write_audit_event(*args, delivery_id=delivery_id)
    assert audit.write_audit_event(*args, delivery_id=delivery_id)
    assert len(db.rows["audit_logs"]) == len(db.rows["audit_events"]) == 1
    export.assert_called_once()
