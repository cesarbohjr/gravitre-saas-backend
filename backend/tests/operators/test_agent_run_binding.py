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
