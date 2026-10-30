from cryptography.fernet import Fernet
import pytest

from app.services.native_agent_adapters import AdapterScope
from app.services.native_runtime.store import Journal, LeaseLost


def test_browser_fence_revokes_lease_and_never_queues_replay(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    journal = Journal(str(private / "journal.sqlite"), Fernet.generate_key())
    scope = AdapterScope("org", "agent", "run")
    job_id = journal.enqueue(scope, "browser_use", "identity", {"task": {}}, actor="actor")
    job = journal.claim("browser_use")
    assert job["id"] == job_id
    assert journal.fence_browser_for_fallback(job, checkpoint_before_effect=True) is True
    assert not journal.active(job)
    assert journal.get(scope, job_id)["state"] == "uncertain"
    assert journal.get(scope, job_id)["phase"] == "fallback_fenced"
    assert journal.claim("browser_use") is None
    with pytest.raises(LeaseLost):
        journal.fence_browser_for_fallback(job, checkpoint_before_effect=True)


def test_checkpoint_with_prior_action_requires_reconciliation(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    journal = Journal(str(private / "journal.sqlite"), Fernet.generate_key())
    scope = AdapterScope("org", "agent", "run")
    job_id = journal.enqueue(scope, "browser_use", "identity", {"task": {}}, actor="actor")
    job = journal.claim("browser_use")
    journal.request_action(job, 0, {"type": "click"})
    assert journal.fence_browser_for_fallback(job, checkpoint_before_effect=True) is False
    assert journal.get(scope, job_id)["phase"] == "fallback_reconcile"
    assert journal.claim("browser_use") is None
