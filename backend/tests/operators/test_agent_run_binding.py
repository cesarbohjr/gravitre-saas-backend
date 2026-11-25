import pytest
from unittest.mock import Mock
from app.operators import agent_run_binding as binding


@pytest.mark.parametrize("payload", [{"run_id": "forged"}, {"workflow_run_id": "forged"}, {}])
def test_unbound_job_ignores_payload(monkeypatch, payload):
    reader = Mock()
    monkeypatch.setattr(binding, "get_run_with_steps", reader)
    assert binding.resolve_bound_run(None, {"payload": payload}) is None
    reader.assert_not_called()


@pytest.mark.parametrize("run", [None, {}, {"triggered_by": "other"}])
def test_binding_rejects_missing_or_wrong_actor(monkeypatch, run):
    monkeypatch.setattr(binding, "get_run_with_steps", Mock(return_value=run))
    with pytest.raises(ValueError):
        binding.resolve_bound_run(None, {"bound_run_id": "r", "org_id": "o", "environment": "qa", "created_by": "a"})


@pytest.mark.parametrize("missing", ["org_id", "environment", "created_by"])
def test_binding_rejects_incomplete_scope(missing):
    job = {"bound_run_id": "r", "org_id": "o", "environment": "qa", "created_by": "a"}
    del job[missing]
    with pytest.raises(ValueError):
        binding.resolve_bound_run(None, job)


def test_binding_uses_persisted_scope(monkeypatch):
    reader = Mock(return_value={"triggered_by": "a"})
    monkeypatch.setattr(binding, "get_run_with_steps", reader)
    assert binding.resolve_bound_run(None, {"bound_run_id": "r", "org_id": "o", "environment": "qa", "created_by": "a", "payload": {"run_id": "forged"}}) == "r"
    reader.assert_called_once_with(None, "o", "r", "qa")


def test_tracking_binding_cannot_supply_run_write_authority(monkeypatch):
    job = {"bound_run_id": "r", "org_id": "o", "environment": "qa", "created_by": "a",
           "payload": {"run_id": "forged", "assignment_tracking_only": False}}
    monkeypatch.setattr(binding, "get_run_with_steps", Mock(return_value={
        "triggered_by": "a", "parameters": {"assignment_tracking_only": True},
        "approval_status": "approved", "required_approvals": 1,
    }))
    assert binding.resolve_bound_run(None, job, for_execution=True) is None
    assert binding.resolve_bound_run(None, job) == "r"


def test_nontracking_binding_retains_governed_run_identity(monkeypatch):
    job = {"bound_run_id": "r", "org_id": "o", "environment": "qa", "created_by": "a"}
    monkeypatch.setattr(binding, "get_run_with_steps", Mock(return_value={
        "triggered_by": "a", "parameters": {}, "approval_status": "revoked",
    }))
    # The identity is not approval; the live execution gate must reject revocation.
    assert binding.resolve_bound_run(None, job, for_execution=True) == "r"
    from app.services.canvas_write_gate import run_allows_catalog_write_execution
    assert not run_allows_catalog_write_execution({"required_approvals": 1, "approval_status": "revoked"})


def test_pg_conflict_ignore_preserves_terminal_outcome():
    from tests.master_qa.canonical_pg_repository import canonical_pg_cluster, PgRepositoryClient, ORG
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        first = client.table("workflow_runs").insert({"org_id": ORG, "status": "completed"}).execute().data[0]
        duplicate = client.table("workflow_runs").upsert(
            {"id": first["id"], "org_id": ORG, "status": "running"},
            on_conflict="id", ignore_duplicates=True,
        ).execute()
        assert duplicate.data == []
        rows = client.table("workflow_runs").select("status").eq("id", first["id"]).execute().data
        assert rows == [{"status": "completed"}]
