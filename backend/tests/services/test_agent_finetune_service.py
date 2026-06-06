"""STA-99: fine-tuned model assignment and agent inference resolution."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.agent_finetune_service import (
    assign_trained_model_to_agent,
    complete_for_agent,
    resolve_agent_inference_model,
)
from app.services.model_router import ModelResponse, TaskType
from app.services.providers.base import AllProvidersFailedError


def _chainable(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], error=None)
    return mock


def test_resolve_agent_inference_model_without_assignment():
    client = MagicMock()
    client.table.return_value = _chainable()
    agent = {"id": "agent-1", "model": "gpt-4.1-mini"}
    result = resolve_agent_inference_model(client, "org-1", agent)
    assert result.fine_tuned_openai_id is None
    assert result.base_model == "gpt-4.1-mini"


def test_resolve_agent_inference_model_with_deployed_fine_tune():
    trained_model_id = "model-1"
    agent = {"id": "agent-1", "model": "gpt-4.1", "trained_model_id": trained_model_id}

    def table_side_effect(name: str):
        if name == "trained_models":
            return _chainable(
                [
                    {
                        "id": trained_model_id,
                        "org_id": "org-1",
                        "model_type": "fine_tuned_llm",
                        "status": "deployed",
                        "base_model": "gpt-4.1",
                        "deployed_version": 2,
                        "current_version": 2,
                    }
                ]
            )
        if name == "model_versions":
            return _chainable([{"metrics": {"custom_metrics": {"fine_tuned_model": "ft:gpt-4.1:org:abc"}}}])
        return _chainable()

    client = MagicMock()
    client.table.side_effect = table_side_effect
    result = resolve_agent_inference_model(client, "org-1", agent)
    assert result.fine_tuned_openai_id == "ft:gpt-4.1:org:abc"
    assert result.trained_model_version == 2


def test_assign_trained_model_to_agent_rejects_wrong_type():
    agent_id = "agent-1"

    def table_side_effect(name: str):
        if name == "agents":
            return _chainable([{"id": agent_id, "org_id": "org-1", "name": "Sales"}])
        if name == "trained_models":
            return _chainable(
                [{"id": "model-1", "org_id": "org-1", "model_type": "forecaster", "status": "ready", "name": "F"}]
            )
        return _chainable()

    client = MagicMock()
    client.table.side_effect = table_side_effect
    with pytest.raises(HTTPException) as exc:
        assign_trained_model_to_agent(
            client, org_id="org-1", agent_id=agent_id, trained_model_id="model-1", actor_id="user-1"
        )
    assert exc.value.status_code == 400


def test_assign_trained_model_to_agent_clears_assignment():
    agent_id = "agent-1"
    updated = {"id": agent_id, "trained_model_id": None}

    def table_side_effect(name: str):
        if name == "agents":
            chain = _chainable([{"id": agent_id, "org_id": "org-1", "name": "Sales", "trained_model_id": "old"}])
            if not hasattr(table_side_effect, "updated"):
                table_side_effect.updated = True
                return chain
            return _chainable([updated])
        return _chainable()

    client = MagicMock()
    client.table.side_effect = table_side_effect
    with patch("app.services.agent_finetune_service.write_audit_event"):
        result = assign_trained_model_to_agent(
            client, org_id="org-1", agent_id=agent_id, trained_model_id=None, actor_id="user-1"
        )
    assert result["trained_model_id"] is None


@pytest.mark.asyncio
async def test_complete_for_agent_falls_back_to_base_model():
    agent = {"id": "agent-1", "model": "gpt-4.1-mini", "trained_model_id": "model-1"}
    router = MagicMock()
    base_response = ModelResponse(
        provider="openai",
        model="gpt-4.1-mini",
        content="fallback",
        parsed=None,
        input_tokens=10,
        output_tokens=5,
        latency_ms=100,
        cost_usd=0.001,
        cache_hit=False,
        model_call_id="call-2",
    )
    router.complete = AsyncMock(
        side_effect=[AllProvidersFailedError([("openai", "ft failed")]), base_response]
    )

    with (
        patch(
            "app.services.agent_finetune_service.resolve_agent_inference_model",
            return_value=SimpleNamespace(
                agent_id="agent-1",
                base_model="gpt-4.1-mini",
                trained_model_id="model-1",
                trained_model_version=1,
                fine_tuned_openai_id="ft:gpt-4.1:org:abc",
            ),
        ),
        patch("app.services.agent_finetune_service.write_audit_event") as audit,
    ):
        response = await complete_for_agent(
            router,
            task_type=TaskType.WORKFLOW_PLANNING,
            prompt="task",
            system_prompt="sys",
            response_format=None,
            org_id="org-1",
            agent=agent,
            client=MagicMock(),
            actor_id="user-1",
            run_id="run-1",
        )

    assert response.content == "fallback"
    assert router.complete.await_count == 2
    audit.assert_called_once()
    assert audit.call_args.kwargs["metadata"]["usedFallback"] is True
