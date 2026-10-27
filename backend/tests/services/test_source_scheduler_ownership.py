import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services import source_sync_service as svc

OWNER = "11111111-1111-4111-8111-111111111111"
ADMIN = "22222222-2222-4222-8222-222222222222"


def test_scheduler_excludes_static_and_connector_ingested_knowledge():
    assert not svc.scheduled_source_owned({"type": "manual", "metadata": {}})
    assert not svc.scheduled_source_owned({"type": "hubspot", "metadata": {"source": "notes_and_emails", "connector_id": "c"}})
    assert svc.scheduled_source_owned({"type": "hubspot", "metadata": {}, "connection_string_encrypted": "cipher"})
    assert svc.scheduled_source_owned({"type": "postgresql", "metadata": {}})
    assert not svc.scheduled_source_owned({"type": "unknown", "metadata": {}})


def test_responsible_actor_is_current_member_and_never_system():
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"user_id": ADMIN, "role": "admin"}, {"user_id": OWNER, "role": "owner"},
    ]
    assert svc.resolve_source_sync_actor(db, "org", {"created_by": "system"}) == OWNER
    assert svc.resolve_source_sync_actor(db, "org", {"created_by": ADMIN}) == ADMIN
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    assert svc.resolve_source_sync_actor(db, "org", {"created_by": OWNER}) is None


def test_scheduler_passes_real_actor_and_leaves_other_owners_untouched(monkeypatch):
    rows = [
        {"id": "external", "org_id": "org", "type": "postgresql", "metadata": {}},
        {"id": "static", "org_id": "org", "type": "manual", "metadata": {}},
        {"id": "ingested", "org_id": "org", "type": "hubspot", "metadata": {"source": "notes_and_emails", "connector_id": "c"}},
    ]
    db = MagicMock()
    db.table.return_value.select.return_value.is_.return_value.in_.return_value.execute.return_value.data = rows
    monkeypatch.setattr(svc, "shared_service_client", lambda *_: db)
    monkeypatch.setattr(svc, "resolve_source_sync_actor", lambda *_: OWNER)
    run = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(svc, "sync_source_row", run)
    assert asyncio.run(svc.run_scheduled_source_syncs(SimpleNamespace())) == {"due_count": 1, "processed": 1, "errors": 0}
    assert run.await_args.kwargs["actor_id"] == OWNER
    assert run.await_args.kwargs["row"]["id"] == "external"


def test_successful_check_clears_stale_error_and_audits_automation(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(svc, "run_connection_test", AsyncMock(return_value={}))
    monkeypatch.setattr(svc, "discover_schema", AsyncMock(return_value={}))
    audit = MagicMock()
    monkeypatch.setattr(svc, "write_audit_event", audit)
    row = {"id": OWNER, "org_id": "org", "type": "postgresql", "metadata": {"lastSyncError": "stale"}}
    result = asyncio.run(svc.sync_source_row(db, SimpleNamespace(encryption_key=None), org_id="org", row=row, environment="production", actor_id=OWNER, trigger="scheduled"))
    assert result["success"]
    final = db.table.return_value.update.call_args_list[-1].args[0]
    assert "lastSyncError" not in final["metadata"]
    assert "last_sync_at" not in final
    assert audit.call_args.kwargs["actor_id"] == OWNER
    assert audit.call_args.kwargs["metadata"]["executionActor"] == "system"


def test_foreign_source_is_rejected_before_mutation():
    import pytest
    db = MagicMock()
    with pytest.raises(ValueError, match="organization mismatch"):
        asyncio.run(svc.sync_source_row(db, SimpleNamespace(encryption_key=None), org_id="org", row={"id": OWNER, "org_id": "foreign"}, environment="production", actor_id=OWNER))
    db.table.assert_not_called()


def test_scheduler_without_a_responsible_member_does_not_run_unaudited(monkeypatch):
    db = MagicMock()
    db.table.return_value.select.return_value.is_.return_value.in_.return_value.execute.return_value.data = [
        {"id": "external", "org_id": "org", "type": "postgresql", "metadata": {}},
    ]
    monkeypatch.setattr(svc, "shared_service_client", lambda *_: db)
    monkeypatch.setattr(svc, "resolve_source_sync_actor", lambda *_: None)
    run = AsyncMock()
    monkeypatch.setattr(svc, "sync_source_row", run)
    assert asyncio.run(svc.run_scheduled_source_syncs(SimpleNamespace())) == {"due_count": 1, "processed": 0, "errors": 1}
    run.assert_not_awaited()
