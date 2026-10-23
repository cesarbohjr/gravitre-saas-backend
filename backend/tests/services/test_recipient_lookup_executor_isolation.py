"""Mailbox resolution must not wait behind unrelated default-executor work."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import MagicMock
import pytest
from app.services import recipient_resolution as rr


@pytest.mark.asyncio
async def test_default_executor_contention_does_not_turn_a_mailbox_lookup_into_unavailable(monkeypatch):
    loop = asyncio.get_running_loop()
    previous = loop._default_executor
    pool = ThreadPoolExecutor(max_workers=1)
    release = threading.Event()
    started = threading.Event()
    def unrelated_work():
        started.set()
        release.wait(2)
    loop.set_default_executor(pool)
    busy = loop.run_in_executor(None, unrelated_work)
    assert started.wait(1)
    monkeypatch.setattr(rr, "LOOKUP_BUDGET_S", 0.05)
    monkeypatch.setattr(rr, "_HARD_TIMEOUT_S", 0.2)
    monkeypatch.setattr(rr, "_scan_gmail_sync", lambda *a, **kw: rr._Scan(complete=True))
    try:
        result = await rr.resolve_email_recipient("Mike", org_id="org", client=MagicMock(),
            settings=MagicMock(), connected_integrations=["gmail"])
        assert result.status == "not_found"
        assert result.reason != "time_budget"
    finally:
        release.set()
        await busy
        loop._default_executor = previous
        pool.shutdown(wait=True)
