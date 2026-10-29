"""Persistent native action journal restart and replay regression, both browser adapters."""
import tempfile
import time
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from app.services.native_agent_adapters import AdapterScope
from app.services.native_runtime.store import Journal, LeaseLost


@pytest.mark.parametrize("adapter", ["browser_use", "playwright"])
def test_crash_restart_fences_native_replay_without_duplicate_action(adapter):
    # Playwright is an opt-in implementation of browser_use jobs; both adapters
    # must retain the same journal, lease, and exactly-one submission semantics.
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "private"
        root.mkdir(mode=0o700)
        path = str(root / "journal.sqlite3")
        key = Fernet.generate_key()
        scope = AdapterScope("fixture-org", "fixture-agent", "fixture-run")
        first = Journal(path, key)
        stamp = time.time()
        payload = {"task": {"task": "fixture", "allowed_hosts": ["www.selenium.dev"]}}
        job_id = first.enqueue(scope, "browser_use", "same-approved-intent", payload,
                               now=stamp, ttl=10000, max_attempts=1)
        assert first.enqueue(scope, "browser_use", "same-approved-intent", payload,
                             now=stamp, ttl=10000, max_attempts=1) == job_id
        active = first.claim("browser_use", now=stamp + 1, lease_seconds=60)
        assert active["id"] == job_id
        action = {"actions": {"navigate": {"url": "https://www.selenium.dev/selenium/web/web-form.html"}},
                  "page_fingerprint": "a" * 64}
        original = first.request_action(active, 0, action)
        assert first.request_action(active, 0, action)["id"] == original["id"]
        assert len(first.actions(scope, job_id)) == 1

        # Simulate a fresh process after the engine and broker have died.
        recovered = Journal(path, key)
        assert recovered.claim("browser_use", now=stamp + 62) is None
        current = recovered.get(scope, job_id)
        assert current["state"] == "uncertain"
        assert job_id in recovered.uncertain_jobs()
        assert len(recovered.actions(scope, job_id)) == 1
        with pytest.raises(LeaseLost):
            recovered.request_action(active, 1, action)
        with pytest.raises(LeaseLost):
            recovered.update(active, "completed", now=stamp + 63)
        assert recovered.claim("browser_use", now=stamp + 64) is None
        recovered.reconciled(job_id)
        assert job_id not in recovered.uncertain_jobs()
        # A stale idempotency key cannot grant another execution.
        assert recovered.enqueue(scope, "browser_use", "same-approved-intent", payload,
                                 now=stamp + 65, ttl=10000, max_attempts=1) == job_id
        assert recovered.claim("browser_use", now=stamp + 66) is None
        assert len(recovered.actions(scope, job_id)) == 1
