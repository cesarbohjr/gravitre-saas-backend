"""Tests for async agent execution queue wiring."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators import agent_jobs as jobs
from app.workers.queue import AgentExecutionJob, enqueue_agent_execution_job, is_queue_available


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store, table):
        self.store = store
        self.table = table
        self._op = None
        self._payload = None
        self._filters: list[tuple] = []

    def insert(self, row):
        self._op, self._payload = "insert", row
        return self

    def select(self, *cols):
        self._op = "select"
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def limit(self, n):
        return self

    def _match(self, row):
        return all(row.get(c) == v for c, v in self._filters)

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self._op == "insert":
            r = dict(self._payload)
            r.setdefault("id", str(uuid.uuid4()))
            rows.append(r)
            return _Resp([dict(r)])
        if self._op == "select":
            res = [r for r in rows if self._match(r)]
            return _Resp([dict(r) for r in res])
        if self._op == "update":
            updated = []
            for r in rows:
                if self._match(r):
                    r.update(self._payload)
                    updated.append(dict(r))
            return _Resp(updated)
        return _Resp([])


class FakeSupabase:
    def __init__(self):
        self.store: dict = {}

    def table(self, name):
        return _Query(self.store, name)


@pytest.mark.asyncio
async def test_enqueue_agent_execution_job_local():
    job = AgentExecutionJob(
        job_id="job-1",
        org_id="org-1",
        user_id="u1",
        agent_id="agent-1",
        task={"task": "x"},
        context={},
    )
    with patch("app.workers.queue.get_settings") as gs:
        gs.return_value = MagicMock(redis_url="")
        await enqueue_agent_execution_job(job)


def test_create_job_sets_queued_fields():
    c = FakeSupabase()
    job = jobs.create_job(c, "org-1", payload={"task": "x"})
    assert job["status"] == "queued"
    assert job.get("queued_at")
    assert job.get("timeout_at")


@pytest.mark.asyncio
async def test_process_job_timeout(monkeypatch):
    c = FakeSupabase()
    job = jobs.create_job(c, "org-1", payload={"task": "x", "timeout_seconds": 1})
    job_id = job["id"]

    async def slow_handler(settings, job):
        return {"ok": True}

    monkeypatch.setitem(jobs._HANDLERS, "operator_task", slow_handler)
    monkeypatch.setattr(jobs, "get_supabase_client", lambda settings: c)

    async def instant_timeout(coro, timeout):
        coro.close()
        raise TimeoutError

    monkeypatch.setattr(jobs.asyncio, "wait_for", instant_timeout)

    handled = await jobs._process_job_id(MagicMock(), job_id)
    assert handled is True
    row = jobs.get_job(c, "org-1", job_id)
    assert row["status"] in ("queued", "failed")


def test_queue_unavailable_without_redis():
    with patch("app.workers.queue.get_settings") as gs:
        gs.return_value = MagicMock(redis_url="")
        assert is_queue_available() is False
