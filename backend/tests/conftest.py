from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        anthropic_api_key="sk-test-anthropic",
        google_api_key="test-google-key",
    )


@pytest.fixture(autouse=True)
def _set_required_env_vars():
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    os.environ.setdefault("SUPABASE_JWT_SECRET", "jwt-secret-test")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai")
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-anthropic")
    os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
    os.environ.setdefault("BLOB_READ_WRITE_TOKEN", "blob_test_token")
    yield


@pytest.fixture(autouse=True)
def _reset_singletons():
    import app.services.model_router as model_router_module
    import app.services.decision_service as decision_service_module
    import app.services.goal_service as goal_service_module
    import app.services.council_service as council_service_module
    import app.services.execution_service as execution_service_module
    import app.services.rag_service as rag_service_module
    import app.services.optimization_service as optimization_service_module
    import app.ml.registry as ml_registry_module
    import app.ml.inference as ml_inference_module
    import app.ml.classifiers as ml_classifiers_module
    import app.ml.anomaly as ml_anomaly_module

    model_router_module._model_router_singleton = None
    decision_service_module._decision_service_singleton = None
    goal_service_module._goal_service_singleton = None
    council_service_module._council_service_singleton = None
    execution_service_module._execution_service_singleton = None
    rag_service_module._rag_service_singleton = None
    optimization_service_module._optimization_service_singleton = None
    ml_registry_module._registry = None
    ml_inference_module._inference = None
    ml_classifiers_module._classifier_cache = {}
    ml_anomaly_module._anomaly_detector = None
    yield


@pytest.fixture
def mock_openai_response() -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"result":"test"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


@pytest.fixture
def mock_anthropic_response() -> dict[str, Any]:
    return {
        "id": "msg-test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": '{"result":"test"}'}],
        "model": "claude-3-5-sonnet-20241022",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


@pytest.fixture
def mock_embedding_response() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": [0.1] * 1536}],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "test-id"}]
    client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "test-id"}]
    return client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_workflow_nodes() -> list[dict[str, Any]]:
    return [
        {"id": "node_1", "node_type": "trigger", "name": "Start", "config": {"trigger_type": "manual"}, "order_index": 0},
        {"id": "node_2", "node_type": "action", "name": "Process Data", "config": {"action": "transform"}, "order_index": 1},
        {
            "id": "node_3",
            "node_type": "decision",
            "name": "Check Result",
            "config": {"paths": [{"id": "success", "label": "Success"}, {"id": "failure", "label": "Failure"}]},
            "order_index": 2,
        },
        {"id": "node_4", "node_type": "end", "name": "Complete", "config": {}, "order_index": 3},
    ]
