"""Tests for the durable async agent-job queue (repo + endpoints)."""
from __future__ import annotations

import uuid

import pytest

import app.operators.agent_jobs as jobs
import app.routers.agent_jobs as jobs_router
from app.auth.dependencies import get_current_user, get_org_context
from app.config import get_settings
from app.main import app


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
        self._order = None
        self._desc = False
        self._limit = None

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

    def in_(self, col, vals):
        self._filters.append((col, "__in__", tuple(vals)))
        return self

    def order(self, col, desc=False):
        self._order = col
        self._desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _match(self, row):
        for filt in self._filters:
            if len(filt) == 3 and filt[1] == "__in__":
                col, _, vals = filt
                if row.get(col) not in vals:
                    return False
            else:
                col, val = filt
                if row.get(col) != val:
                    return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self._op == "insert":
            r = dict(self._payload)
            r.setdefault("id", str(uuid.uuid4()))
            r.setdefault("attempts", r.get("attempts", 0) or 0)
            r.setdefault("max_attempts", r.get("max_attempts", 3))
            rows.append(r)
            return _Resp([dict(r)])
        if self._op == "select":
            res = [r for r in rows if self._match(r)]
            if self._order:
                res = sorted(res, key=lambda r: r.get(self._order) or "", reverse=self._desc)
            if self._limit:
                res = res[: self._limit]
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


# --- repository ------------------------------------------------------------


def test_create_get_scoped():
    c = FakeSupabase()
    job = jobs.create_job(c, "org-1", payload={"task": "do x"}, created_by="u1")
    assert job["status"] == "queued"
    assert jobs.get_job(c, "org-1", job["id"])["id"] == job["id"]
    assert jobs.get_job(c, "org-2", job["id"]) is None  # cross-org isolated


def test_claim_and_complete():
    c = FakeSupabase()
    jobs.create_job(c, "org-1", payload={"task": "x"})
    claimed = jobs.claim_next_job(c)
    assert claimed["status"] == "running" and claimed["attempts"] == 1
    assert jobs.claim_next_job(c) is None  # nothing left queued
    jobs.complete_job(c, claimed["id"], {"ok": True})
    assert jobs.get_job(c, "org-1", claimed["id"])["status"] == "completed"


def test_fail_requeue_then_fail():
    c = FakeSupabase()
    j = jobs.create_job(c, "org-1", payload={"task": "x"})
    j["attempts"] = 1  # under max(3) -> requeue
    jobs.fail_or_requeue_job(c, j, "boom")
    assert jobs.get_job(c, "org-1", j["id"])["status"] == "queued"
    j["attempts"] = 3  # at max -> failed
    jobs.fail_or_requeue_job(c, j, "boom")
    assert jobs.get_job(c, "org-1", j["id"])["status"] == "failed"


def test_list_jobs_scoped_and_filtered():
    c = FakeSupabase()
    a = jobs.create_job(c, "org-1", payload={"task": "a"})
    jobs.create_job(c, "org-1", payload={"task": "b"})
    jobs.create_job(c, "org-2", payload={"task": "c"})  # other org
    org1 = jobs.list_jobs(c, "org-1", limit=10)
    assert len(org1) == 2
    assert all(j["org_id"] == "org-1" for j in org1)
    # status filter
    jobs.complete_job(c, a["id"], {"ok": True})
    completed = jobs.list_jobs(c, "org-1", status="completed")
    assert len(completed) == 1 and completed[0]["id"] == a["id"]


def test_cancel_and_retry():
    c = FakeSupabase()
    j = jobs.create_job(c, "org-1", payload={"task": "x"})
    assert jobs.cancel_job(c, "org-1", j["id"])["status"] == "cancelled"
    assert jobs.cancel_job(c, "org-1", j["id"]) is None  # already terminal
    assert jobs.retry_job(c, "org-1", j["id"])["status"] == "queued"
    assert jobs.retry_job(c, "org-2", j["id"]) is None  # cross-org cannot retry


# --- endpoints -------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


def _auth(org="org-1"):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    app.dependency_overrides[get_org_context] = lambda: org


async def test_enqueue_returns_202(async_client, monkeypatch):
    _auth()
    fake = FakeSupabase()
    monkeypatch.setattr(jobs_router, "create_client", lambda *a, **k: fake)
    resp = await async_client.post(
        "/api/agent-jobs", headers={"Authorization": "Bearer t"}, json={"task": "investigate failures"}
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued" and body["jobId"]
    assert body.get("kind") == "operator_task"


async def test_enqueue_with_agent_id_creates_agent_task(async_client, monkeypatch):
    _auth()
    fake = FakeSupabase()
    monkeypatch.setattr(jobs_router, "create_client", lambda *a, **k: fake)
    resp = await async_client.post(
        "/api/agent-jobs",
        headers={"Authorization": "Bearer t"},
        json={
            "task": "Reconcile CRM and billing for Acme",
            "agent_id": "agent-abc",
            "context": {"priority": "high", "useTrainingKnowledge": True},
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["kind"] == "agent_task"
    assert body["status"] == "queued" and body["jobId"]
    stored = fake.store["agent_jobs"][0]
    assert stored["kind"] == "agent_task"
    assert stored["payload"]["agent_id"] == "agent-abc"
    assert stored["payload"]["context"]["priority"] == "high"
    assert stored["payload"]["context"]["agent_id"] == "agent-abc"


async def test_list_endpoint(async_client, monkeypatch):
    _auth()
    fake = FakeSupabase()
    monkeypatch.setattr(jobs_router, "create_client", lambda *a, **k: fake)
    await async_client.post("/api/agent-jobs", headers={"Authorization": "Bearer t"}, json={"task": "a"})
    await async_client.post("/api/agent-jobs", headers={"Authorization": "Bearer t"}, json={"task": "b"})
    resp = await async_client.get("/api/agent-jobs", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert len(resp.json()["jobs"]) == 2


async def test_get_missing_returns_404(async_client, monkeypatch):
    _auth()
    monkeypatch.setattr(jobs_router, "create_client", lambda *a, **k: FakeSupabase())
    resp = await async_client.get("/api/agent-jobs/nope", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 404


async def test_unauthenticated_401(async_client):
    resp = await async_client.post("/api/agent-jobs", json={"task": "x"})
    assert resp.status_code == 401


async def test_cancel_then_retry_flow(async_client, monkeypatch):
    _auth()
    fake = FakeSupabase()
    monkeypatch.setattr(jobs_router, "create_client", lambda *a, **k: fake)
    enq = await async_client.post(
        "/api/agent-jobs", headers={"Authorization": "Bearer t"}, json={"task": "x"}
    )
    job_id = enq.json()["jobId"]
    cancelled = await async_client.post(f"/api/agent-jobs/{job_id}/cancel", headers={"Authorization": "Bearer t"})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    retried = await async_client.post(f"/api/agent-jobs/{job_id}/retry", headers={"Authorization": "Bearer t"})
    assert retried.status_code == 200 and retried.json()["status"] == "queued"
    # retry on a queued job is a 409 (not failed/cancelled)
    again = await async_client.post(f"/api/agent-jobs/{job_id}/retry", headers={"Authorization": "Bearer t"})
    assert again.status_code == 409


async def test_approve_and_reject_pending_job(async_client, monkeypatch):
    _auth()
    fake = FakeSupabase()
    monkeypatch.setattr(jobs_router, "create_client", lambda *a, **k: fake)
    enq = await async_client.post(
        "/api/agent-jobs", headers={"Authorization": "Bearer t"}, json={"task": "weekly report"}
    )
    job_id = enq.json()["jobId"]
    row = fake.store["agent_jobs"][0]
    row["status"] = "completed"
    row["result"] = {"requires_approval": True, "summary": "Weekly report ready"}

    approved = await async_client.post(
        f"/api/agent-jobs/{job_id}/approve",
        headers={"Authorization": "Bearer t"},
        json={"notes": "Looks good"},
    )
    assert approved.status_code == 200
    assert approved.json()["result"]["approval_status"] == "approved"

    row["result"] = {"requires_approval": True, "summary": "Needs another review"}
    rejected = await async_client.post(
        f"/api/agent-jobs/{job_id}/reject",
        headers={"Authorization": "Bearer t"},
        json={"reason": "Missing Q3 comparison"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["result"]["approval_status"] == "rejected"
    assert rejected.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_run_operator_job_falls_back_when_ai_unavailable(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("All AI providers failed")

    intel = type("I", (), {"execute_task": _boom})()
    monkeypatch.setattr("app.operators.agent_intelligence.get_agent_intelligence", lambda: intel)
    monkeypatch.setattr(
        "app.operators.agent_jobs.get_supabase_client",
        lambda settings: type("C", (), {"table": lambda self, name: type("Q", (), {"select": lambda *a, **k: self, "eq": lambda *a, **k: self, "limit": lambda *a, **k: self, "execute": lambda *a, **k: type("R", (), {"data": []})()})()})(),
    )
    monkeypatch.setattr("app.operators.agent_jobs._assert_job_runnable", lambda *a, **k: None)
    monkeypatch.setattr("app.operators.agent_jobs.apply_usage_with_overage", lambda **kwargs: None)
    monkeypatch.setattr("app.operators.agent_jobs.get_plan_for_org", lambda *a, **k: {})
    monkeypatch.setattr("app.operators.agent_jobs.get_current_period", lambda: ("2026-01-01", "2026-02-01"))
    monkeypatch.setattr(
        "app.operators.agent_jobs.build_ai_usage_metadata",
        lambda *a, **k: {"credits": 1},
    )

    job = {
        "id": "job-1",
        "org_id": "org-1",
        "environment": "production",
        "payload": {"task": "Monitor overdue invoices", "context": {"smoke": True}},
    }
    result = await jobs.run_operator_job(get_settings(), job)
    assert result["aiStatus"] == "degraded"
    assert result["finding_description"]
    assert result["action_title"]
    assert result["task"]["status"] == "planned"
    assert result["react_trace"] == []


@pytest.mark.asyncio
async def test_run_operator_job_includes_react_trace(monkeypatch):
    from app.operators.agent_intelligence import AgentResult

    async def _execute_task(*args, **kwargs):
        return AgentResult(
            summary="Weekly invoice monitoring plan ready.",
            answer="Weekly invoice monitoring plan ready.",
            react_status="completed",
            status="completed",
            confidence=82,
            persona="REVENUE_OPS",
            react_trace=[{"iteration": 1, "thought": "Drafted monitoring plan.", "action": None}],
            recommended_actions=["Schedule weekly finance digest"],
            model="gpt-5.5",
        )

    intel = type("I", (), {"execute_task": _execute_task})()
    monkeypatch.setattr("app.operators.agent_intelligence.get_agent_intelligence", lambda: intel)
    monkeypatch.setattr(
        "app.operators.agent_jobs.get_supabase_client",
        lambda settings: type("C", (), {"table": lambda self, name: type("Q", (), {"select": lambda *a, **k: self, "eq": lambda *a, **k: self, "limit": lambda *a, **k: self, "execute": lambda *a, **k: type("R", (), {"data": []})()})()})(),
    )
    monkeypatch.setattr("app.operators.agent_jobs._assert_job_runnable", lambda *a, **k: None)
    monkeypatch.setattr("app.operators.agent_jobs.apply_usage_with_overage", lambda **kwargs: None)
    monkeypatch.setattr("app.operators.agent_jobs.get_plan_for_org", lambda *a, **k: {})
    monkeypatch.setattr("app.operators.agent_jobs.get_current_period", lambda: ("2026-01-01", "2026-02-01"))
    monkeypatch.setattr(
        "app.operators.agent_jobs.build_ai_usage_metadata",
        lambda *a, **k: {"credits": 1},
    )

    job = {
        "id": "job-2",
        "org_id": "org-1",
        "environment": "production",
        "payload": {"task": "Monitor overdue invoices", "context": {"smoke": True}},
    }
    result = await jobs.run_operator_job(get_settings(), job)
    assert result["aiStatus"] == "ok"
    assert result["persona"] == "REVENUE_OPS"
    assert len(result["react_trace"]) == 1
    assert result["react_trace"][0]["thought"]
    assert result.get("report_content")
    assert result.get("destination") == "export"


def test_resolve_deliverable_content_uses_answer():
    content = jobs._resolve_deliverable_content(
        {
            "answer": "Found 2 Apollo lists ready for membership.",
            "summary": "ignored when answer present",
        }
    )
    assert "Apollo lists" in content


def test_resolve_push_destination_from_wizard_context():
    destination = jobs._resolve_push_destination(
        {"payload": {"context": {"destinations": ["HubSpot", "Slack"]}}, "result": {}},
        {},
    )
    assert destination == "hubspot"


def test_push_job_deliverable_export_without_connector(monkeypatch):
    store = {
        "agent_jobs": [
            {
                "id": "job-push-1",
                "org_id": "org-1",
                "status": "completed",
                "payload": {"context": {"destinations": ["Export"]}},
                "result": {
                    "answer": "Membership plan ready for MSP Prospects.",
                    "approval_status": "approved",
                },
            }
        ]
    }

    class _Client:
        def table(self, name):
            return _Query(store, name)

    client = _Client()
    monkeypatch.setattr(jobs, "get_job", lambda c, org, jid: store["agent_jobs"][0])
    out = jobs.push_job_deliverable(
        client,
        "org-1",
        "job-push-1",
        user_id="user-1",
        settings=get_settings(),
    )
    assert out["ok"] is True
    assert out["destination"] == "export"
    assert store["agent_jobs"][0]["result"]["push_status"] == "exported"
