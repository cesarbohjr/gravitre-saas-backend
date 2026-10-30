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
    journal.save_browser_checkpoint(job, 0, {"url": "https://example.com", "before_effect": True})
    assert journal.browser_checkpoint(scope, job_id)["sequence"] == 0
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


def test_checkpoint_cannot_follow_action_or_lost_lease(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    journal = Journal(str(private / "journal.sqlite"), Fernet.generate_key())
    scope = AdapterScope("org", "agent", "run")
    journal.enqueue(scope, "browser_use", "identity", {"task": {}}, actor="actor")
    job = journal.claim("browser_use")
    journal.save_browser_checkpoint(job, 0, {"before_effect": True})
    with pytest.raises(ValueError):
        journal.save_browser_checkpoint(job, 0, {"before_effect": True})
    journal.request_action(job, 0, {"type": "click"})
    with pytest.raises(PermissionError):
        journal.save_browser_checkpoint(job, 1, {"before_effect": True})
    assert journal.fence_browser_for_fallback(job, checkpoint_before_effect=True) is False
    with pytest.raises(LeaseLost):
        journal.save_browser_checkpoint(job, 2, {"before_effect": True})


def test_fenced_reservation_is_single_use(tmp_path):
    private=tmp_path / "private"
    private.mkdir(mode=0o700)
    journal=Journal(str(private / "journal.sqlite"),Fernet.generate_key())
    scope=AdapterScope("org","agent","run")
    job_id=journal.enqueue(scope,"browser_use","identity",{"task":{}},actor="actor")
    job=journal.claim("browser_use")
    journal.save_browser_checkpoint(job,0,{"before_effect":True})
    journal.fence_browser_for_fallback(job,checkpoint_before_effect=True)
    assert journal.claim_fenced_handoff(scope,job_id)
    with pytest.raises(LeaseLost):
        journal.claim_fenced_handoff(scope,job_id)


def test_fenced_reservation_rejects_non_pre_effect_checkpoint(tmp_path):
    private=tmp_path / "private"
    private.mkdir(mode=0o700)
    journal=Journal(str(private / "journal.sqlite"),Fernet.generate_key())
    scope=AdapterScope("org","agent","run")
    job_id=journal.enqueue(scope,"browser_use","identity",{"task":{}},actor="actor")
    job=journal.claim("browser_use")
    journal.save_browser_checkpoint(job,0,{"before_effect":False})
    assert journal.fence_browser_for_fallback(job,checkpoint_before_effect=True)
    with pytest.raises(LeaseLost,match="Verified pre-effect checkpoint"):
        journal.claim_fenced_handoff(scope,job_id)
    assert journal.get(scope,job_id)["phase"]=="fallback_fenced"


def test_recovery_inspection_rejects_invalid_checkpoint_marker(tmp_path):
    private=tmp_path / "private"
    private.mkdir(mode=0o700)
    journal=Journal(str(private / "journal.sqlite"),Fernet.generate_key())
    scope=AdapterScope("org","agent","run")
    job_id=journal.enqueue(scope,"browser_use","identity",{"task":{}},actor="actor")
    job=journal.claim("browser_use")
    journal.save_browser_checkpoint(job,0,{"before_effect":False})
    assert journal.fence_browser_for_fallback(job,checkpoint_before_effect=True)
    assert journal.fallback_candidate(scope,job_id) is None
