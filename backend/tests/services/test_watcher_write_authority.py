"""Watcher → agent adapter must gate writes via catalog_write_authority (no bypass)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.watcher_agent_adapter import (
    WatcherAgentAdapter,
    WatcherAgentError,
    assert_watcher_write_allowed,
    gate_watcher_write,
)


def _settings() -> Settings:
    return MagicMock(spec=Settings)


def test_gate_watcher_write_calls_catalog_write_authority():
    with patch(
        "app.services.watcher_agent_adapter.invoke_action_requires_write_approval",
        return_value=True,
    ) as mock_gate:
        assert gate_watcher_write("hubspot.contacts.create") is True
        mock_gate.assert_called_once_with("hubspot.contacts.create")


def test_assert_watcher_write_blocks_without_approval():
    with patch(
        "app.services.watcher_agent_adapter.invoke_action_requires_write_approval",
        return_value=True,
    ):
        with pytest.raises(WatcherAgentError) as exc:
            assert_watcher_write_allowed("apollo.lists.create", approval_granted=False)
        assert exc.value.code == "WRITE_AUTHORITY_DENIED"


def test_assert_watcher_write_allows_read_actions():
    with patch(
        "app.services.watcher_agent_adapter.invoke_action_requires_write_approval",
        return_value=False,
    ):
        result = assert_watcher_write_allowed("hubspot.contacts.search", approval_granted=False)
    assert result["requires_write_approval"] is False
    assert result["gated"] is True


def test_assert_watcher_write_allows_approved_writes():
    with patch(
        "app.services.watcher_agent_adapter.invoke_action_requires_write_approval",
        return_value=True,
    ):
        result = assert_watcher_write_allowed("hubspot.contacts.create", approval_granted=True)
    assert result["requires_write_approval"] is True
    assert result["approval_granted"] is True


@pytest.mark.asyncio
async def test_enqueue_from_watcher_refuses_ungated_write():
    adapter = WatcherAgentAdapter(settings=_settings())
    with patch(
        "app.services.watcher_agent_adapter.invoke_action_requires_write_approval",
        return_value=True,
    ):
        with pytest.raises(WatcherAgentError) as exc:
            await adapter.enqueue_from_watcher(
                "org-1",
                objective="Create a HubSpot contact",
                source="webhook",
                proposed_action="hubspot.contacts.create",
                approval_granted=False,
            )
        assert exc.value.code == "WRITE_AUTHORITY_DENIED"


@pytest.mark.asyncio
async def test_enqueue_from_watcher_creates_job_when_gated():
    adapter = WatcherAgentAdapter(settings=_settings())
    client = MagicMock()
    job = {"id": "job-1", "status": "queued"}

    with (
        patch.object(adapter, "_client", return_value=client),
        patch(
            "app.services.watcher_agent_adapter.invoke_action_requires_write_approval",
            return_value=False,
        ),
        patch(
            "app.operators.agent_jobs.create_job",
            return_value=job,
        ) as create_job,
        patch(
            "app.workers.queue.enqueue_agent_execution_job",
            new_callable=AsyncMock,
        ),
    ):
        result = await adapter.enqueue_from_watcher(
            "org-1",
            objective="Investigate failed invoice sync",
            source="cron",
            agent_id="agent-1",
            created_by="user-1",
        )

    assert result["jobId"] == "job-1"
    assert result["writeAuthorityGated"] is True
    create_job.assert_called_once()
    payload = create_job.call_args.kwargs["payload"]
    assert payload["source"] == "watcher"
    assert payload["writeAuthorityGated"] is True


def _app(monkeypatch, captured):
    from fastapi import FastAPI

    from app.auth.dependencies import get_org_context, require_admin
    from app.config import get_settings
    from app.routers import watcher_agents

    class _Adapter:
        async def enqueue_from_watcher(self, org_id, **kwargs):
            captured.append(kwargs)
            return {"jobId": "j1"}

    monkeypatch.setattr(watcher_agents, "get_watcher_agent_adapter", lambda _s: _Adapter())
    app = FastAPI()
    app.include_router(watcher_agents.router)
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "u1"}, "org-1")
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    app.dependency_overrides[get_settings] = lambda: MagicMock(watcher_agent_webhook_secret="")
    return app


@pytest.mark.parametrize("path", ["/api/watchers/agent", "/api/watchers/agent/signal"])
def test_caller_cannot_assert_its_own_approval(monkeypatch, path):
    """approvalGranted in the request body used to pre-approve a proposed write."""
    from fastapi.testclient import TestClient

    captured: list[dict] = []
    client = TestClient(_app(monkeypatch, captured))
    resp = client.post(
        path,
        json={
            "objective": "Create a contact",
            "proposedAction": "hubspot.contacts.create",
            "approvalGranted": True,
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured and captured[0]["approval_granted"] is False


@pytest.mark.asyncio
async def test_proposed_write_with_asserted_approval_is_refused_end_to_end(monkeypatch):
    from fastapi.testclient import TestClient

    from app.routers import watcher_agents
    from app.services.watcher_agent_adapter import WatcherAgentAdapter

    captured: list[dict] = []
    app = _app(monkeypatch, captured)
    monkeypatch.setattr(watcher_agents, "get_watcher_agent_adapter", lambda _s: WatcherAgentAdapter(settings=_settings()))
    with patch(
        "app.services.watcher_agent_adapter.invoke_action_requires_write_approval",
        return_value=True,
    ):
        resp = TestClient(app).post(
            "/api/watchers/agent/signal",
            json={"objective": "Create", "proposedAction": "hubspot.contacts.create", "approvalGranted": True},
        )
    assert resp.status_code == 403
