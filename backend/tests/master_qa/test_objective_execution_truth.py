"""P27/DEC: existing objective API must report actual governed Play dispatch truth.

No parallel executor. Uses the real goals.execute_objective route and the
existing Plays delegation boundary; substitutes only org records and vendor
dispatch for deterministic, no-side-effect control tests.
"""
from __future__ import annotations

from types import SimpleNamespace
import pytest
from fastapi import HTTPException


class GoalTable:
    def __init__(self):
        self.updates = []
        self.filters = []
    def update(self, payload):
        self.updates.append(payload)
        return self
    def eq(self, k, v):
        self.filters.append((k, v))
        return self
    def execute(self):
        return SimpleNamespace(data=[{"id": "goal-1"}])


@pytest.mark.asyncio
@pytest.mark.parametrize("behavior", ["blocked_request", "denied_dispatch", "no_run_receipt", "started", "partial"])
async def test_existing_objective_execute_uses_actual_play_result_before_active(monkeypatch, behavior):
    from app.routers import goals, plays
    from app.services import objective_capability_composer as composer

    goal_table = GoalTable()
    client = SimpleNamespace(table=lambda name: goal_table)
    monkeypatch.setattr(goals, "shared_service_client", lambda *a: client)
    monkeypatch.setattr(composer, "load_objective", lambda *a: {
        "id": "goal-1", "plan": {"proposed_steps": [{"playKey": "qualified-prospecting"}]},
    })
    monkeypatch.setattr(composer, "org_context", lambda *a, **kw: {"playInstallations": []})
    requests = [
        {"state": "blocked" if behavior == "blocked_request" else "runnable",
         "playKey": "qualified-prospecting",
         "installationId": "installation-1", "capabilityVendors": {}},
    ]
    if behavior == "partial":
        requests.append({"state": "runnable", "playKey": "revenue-recovery",
                         "installationId": "installation-2", "capabilityVendors": {}})
    monkeypatch.setattr(composer, "execution_requests", lambda *a: requests)
    calls = []

    async def controlled_play(key, body, *, member, environment_name, settings):
        calls.append(key)
        assert member[1] == "tenant-one"
        assert body.objective_id == "goal-1"
        if behavior == "denied_dispatch" or (behavior == "partial" and key == "revenue-recovery"):
            raise HTTPException(status_code=409, detail="Approval or connector readiness missing")
        if behavior == "no_run_receipt":
            return {"playRunId": "play-1", "status": "awaiting_approval",
                    "workflowRuns": [], "executionAuthority": "canonical_workflow_runtime"}
        return {"playRunId": "play-1", "status": "awaiting_approval",
                "executionAuthority": "canonical_workflow_runtime",
                "workflowRuns": [{"workflowId": "workflow-1", "runId": "run-1",
                                  "status": "pending_approval", "approvalRequired": True}]}

    monkeypatch.setattr(plays, "run_play", controlled_play)
    result = await goals.execute_objective(
        "goal-1", {"user_id": "qa-user"}, "tenant-one", "synthetic", object(),
    )
    expected = 1 if behavior in ("started", "partial") else 0
    assert len(result["started"]) == expected
    assert len(goal_table.updates) == expected
    if expected:
        assert goal_table.updates == [{"status": "active"}]
        assert result["steps"][0]["runStatus"] == "awaiting_approval"
    else:
        assert goal_table.updates == []
        assert all(item["state"] != "started" for item in result["steps"])
    if behavior in ("denied_dispatch", "partial"):
        assert any(item.get("reason") == "Approval or connector readiness missing"
                   for item in result["steps"])
    assert goal_table.filters == (
        [("id", "goal-1"), ("org_id", "tenant-one")] if expected else []
    )
    assert calls == (
        [] if behavior == "blocked_request"
        else ["qualified-prospecting", "revenue-recovery"] if behavior == "partial"
        else ["qualified-prospecting"]
    )


@pytest.mark.asyncio
async def test_missing_objective_does_not_dispatch_play_or_mutate_goals(monkeypatch):
    from app.routers import goals, plays
    from app.services import objective_capability_composer as composer

    table = GoalTable()
    monkeypatch.setattr(goals, "shared_service_client",
                        lambda *a: SimpleNamespace(table=lambda _: table))
    monkeypatch.setattr(composer, "load_objective", lambda *a: None)

    async def unauthorized(*a, **kw):
        raise AssertionError("provider execution must not be reached")
    monkeypatch.setattr(plays, "run_play", unauthorized)
    with pytest.raises(HTTPException) as exc:
        await goals.execute_objective(
            "not-found", {"user_id": "qa-user"}, "tenant-one", "synthetic", object(),
        )
    assert exc.value.status_code == 404
    assert table.updates == []
