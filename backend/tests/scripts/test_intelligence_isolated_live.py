"""scripts/run-intelligence-isolated-live.py: approval waits on readback, runs once, fails closed."""
from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "run-intelligence-isolated-live.py"
ORG = "f07e57c0-1501-4000-8000-c04e57a00001"


@pytest.fixture(scope="module")
def runner():
    spec = importlib.util.spec_from_file_location("intelligence_isolated_live", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["intelligence_isolated_live"] = module
    spec.loader.exec_module(module)
    return module


class FakeApi:
    """The slice of the backend the runner talks to, with the real replay rule."""

    def __init__(self, *, stage: str = "create_assignment", job_end: str = "completed",
                 learning: bool = True, replay: bool = True, run_on_chat: bool = False) -> None:
        self.stage, self.job_end, self.learning = stage, job_end, learning
        self.replay, self.run_on_chat = replay, run_on_chat
        self.conversation: str | None = None
        self.pending: dict[str, Any] = {}
        self.jobs: dict[str, dict[str, Any]] = {"old-job": {"status": "completed"}}
        self.calls: list[tuple[str, str, str]] = []

    def _new_job(self) -> str:
        job_id = "job-" + uuid.uuid4().hex[:6]
        self.jobs[job_id] = {"status": "queued", "polls": 0}
        return job_id

    def __call__(self, method: str, url: str, token: str, org: str, payload: Any = None,
                 *, stream: bool = False) -> tuple[int, Any]:
        path = url.split("api.gravitre.app", 1)[1]
        self.calls.append((method, path, org))
        assert token == "tok"
        if org != ORG:
            return 403, {"detail": "Not a member"}
        if method == "POST" and path == "/api/conversations":
            self.conversation = "conv-1"
            return 201, {"id": self.conversation}
        if method == "POST" and path == "/api/assistant/chat":
            text = payload["messages"][-1]["parts"][0]["text"]
            self.pending = {"type": self.stage, "status": "awaiting_confirm",
                            "params": {"assignment_task": text}}
            if self.run_on_chat:
                self._new_job()
            return 200, 'data: {"type":"text-delta","delta":"Staged."}\n\n'
        if path.startswith("/api/assistant/conversation/"):
            conv = path.split("/")[4]
            if conv != self.conversation:
                return 404, {"detail": "Conversation not found"}
            if path.endswith("/state"):
                return 200, {"task_state": {"pending_task": self.pending}}
            if self.pending.get("status") == "executed" and self.replay:
                return 200, {"success": True, "execution_result": {
                    "entity_type": "agent_job", "entity_id": "",
                    "structured": {"replayed": True}}}
            job_id = self._new_job()
            self.pending = {"type": self.pending.get("type"), "status": "executed"}
            return 200, {"success": True, "execution_result": {
                "entity_type": "agent_job", "entity_id": job_id, "structured": {}}}
        if path.startswith("/api/agent-jobs?"):
            return 200, {"jobs": [{"jobId": k} for k in self.jobs]}
        if path.startswith("/api/agent-jobs/"):
            job = self.jobs.get(path.rsplit("/", 1)[1])
            if job is None:
                return 404, {}
            job["polls"] = job.get("polls", 0) + 1
            if job["polls"] >= 2:
                job["status"] = self.job_end
            return 200, {"jobId": path.rsplit("/", 1)[1], "status": job["status"]}
        if path.startswith("/api/admin/intelligence/outcomes/trace?jobId="):
            job_id = path.split("=", 1)[1]
            done = self.jobs.get(job_id, {}).get("status") == "completed"
            runs = [{"id": "run-1", "status": "completed"}] if done else []
            events = [{"event_id": "evt-1", "run_id": "run-1", "status": "delivered",
                       "learning_delivered": True}] if done and self.learning else []
            return 200, {"found": True, "runs": runs, "events": events}
        if path == "/api/admin/intelligence/outcomes/delivery":
            return 200, {"status": "idle", "blockers": []}
        raise AssertionError(f"unexpected call {method} {path}")


def _run(runner, api: FakeApi):
    run = runner.Run(api, base=runner.API_ROOT, token="tok", org=ORG, sleep=lambda _s: None,
                     job_timeout=60, learning_timeout=0)
    try:
        run.execute()
    except runner.ProbeError as exc:
        run.report["blocker"] = str(exc)
    return run.report


def test_full_lifecycle_passes_with_exactly_one_assignment(runner):
    api = FakeApi()
    report = _run(runner, api)
    assert report["verdict"] == "PASS", report.get("blocker")
    approvals = [c for c in api.calls if c[1].endswith("/execute")]
    # other org, other conversation, the approval, the duplicate
    assert len(approvals) == 4
    assert len(api.jobs) == 2
    assert report["outcome"]["run_ids"] == ["run-1"]
    assert set(report["not_covered"]) == set(runner.NOT_COVERED)


def test_approval_is_read_back_before_it_is_sent(runner):
    api = FakeApi()
    _run(runner, api)
    paths = [c[1] for c in api.calls]
    first_state = next(i for i, p in enumerate(paths) if p.endswith("/state"))
    first_execute = next(i for i, p in enumerate(paths) if p.endswith("/execute"))
    assert first_state < first_execute


def test_wrong_staged_action_is_never_approved(runner):
    api = FakeApi(stage="connector_action")
    report = _run(runner, api)
    assert report["verdict"] == "FAIL"
    assert report["blocker"] == "staged_action_is_internal_assignment"
    assert not any(c[1].endswith("/execute") for c in api.calls)


def test_work_started_by_chat_alone_fails(runner):
    report = _run(runner, FakeApi(run_on_chat=True))
    assert report["blocker"] == "nothing_ran_before_approval"


def test_second_approval_creating_work_fails(runner):
    report = _run(runner, FakeApi(replay=False))
    assert report["verdict"] == "FAIL"
    assert report["blocker"] == "duplicate_approval_replayed"


def test_failed_assignment_is_not_reported_as_outcome(runner):
    report = _run(runner, FakeApi(job_end="failed"))
    assert report["blocker"] == "assignment_completed"
    assert "outcome" not in report


def test_undelivered_learning_fails(runner):
    report = _run(runner, FakeApi(learning=False))
    assert report["blocker"] == "learning_received_this_outcome"


def test_main_refuses_without_smoke_session(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(tmp_path / "r.json"), "--allow-synthetic-write"])
    monkeypatch.setenv("PLATFORM_LIVE_ORG_ID", ORG)
    monkeypatch.setenv("PLATFORM_LIVE_BEARER_TOKEN", "tok")
    monkeypatch.delenv("PLATFORM_LIVE_AUTH_MODE", raising=False)
    with pytest.raises(SystemExit, match="smoke-org session"):
        runner.main()
    monkeypatch.setenv("PLATFORM_LIVE_AUTH_MODE", "smoke_org_short_lived")
    monkeypatch.setenv("PLATFORM_LIVE_ORG_ID", str(uuid.uuid4()))
    with pytest.raises(SystemExit, match="isolated smoke org"):
        runner.main()
