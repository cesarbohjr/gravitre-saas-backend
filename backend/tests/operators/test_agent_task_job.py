from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.operators.agent_jobs as jobs


@pytest.mark.asyncio
async def test_run_agent_task_job_uses_agent_intelligence():
    settings = SimpleNamespace()
    job = {
        "id": "job-1",
        "org_id": "org-1",
        "environment": "default",
        "created_by": "user-1",
        "payload": {
            "task": "Reconcile CRM and billing for Acme",
            "agent_id": "agent-1",
            "context": {"useTrainingKnowledge": True},
        },
    }
    agent_row = {"id": "agent-1", "name": "RevOps", "status": "active", "systems": ["hubspot"]}
    mock_result = MagicMock()
    mock_result.to_handoff_dict.return_value = {
        "summary": "Done",
        "status": "completed",
        "confidence": 88,
    }
    mock_result.error = None
    mock_result.status = "completed"

    client = MagicMock()
    with patch("app.operators.agent_jobs.get_supabase_client", return_value=client):
        with patch("app.operators.agent_jobs._assert_job_runnable"):
            with patch("app.operators.agent_intelligence.resolve_agent_record", return_value=agent_row):
                with patch(
                    "app.operators.agent_intelligence.get_agent_intelligence"
                ) as mock_intel:
                    mock_intel.return_value.execute_task = AsyncMock(return_value=mock_result)
                    output = await jobs.run_agent_task_job(settings, job)

    assert output["summary"] == "Done"
    assert output["aiStatus"] == "ok"
    assert output["task"]["description"].startswith("Reconcile")
    mock_intel.return_value.execute_task.assert_awaited_once()
    call_kwargs = mock_intel.return_value.execute_task.await_args.kwargs
    assert call_kwargs["agent"]["id"] == "agent-1"
    assert call_kwargs["parameters"]["include_agent_memory"] is True


def test_handlers_include_agent_task():
    assert "agent_task" in jobs._HANDLERS
