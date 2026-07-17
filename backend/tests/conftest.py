from __future__ import annotations

import asyncio
import os
from contextlib import ExitStack, contextmanager
from typing import Any, AsyncGenerator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

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
        ai_moderation_enabled=False,
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
def _disable_api_rate_limits():
    import app.core.rate_limiter as rate_limiter_module

    rate_limiter_module._memory._events.clear()
    noop = AsyncMock(return_value=None)
    with patch("app.core.rate_limiter.enforce_rate_limit", noop), patch(
        "app.middleware.api_rate_limit.enforce_rate_limit", noop
    ):
        yield
    rate_limiter_module._memory._events.clear()


@pytest.fixture(autouse=True)
def _clear_assistant_tool_caches():
    import app.services.assistant_tools as assistant_tools_module
    from app.services.connector_snapshot_cache import clear_connector_snapshot_cache
    from app.services.read_action_result_cache import clear_read_action_result_cache

    assistant_tools_module._CONNECTOR_STATUS_CACHE.clear()
    assistant_tools_module._ANALYTICS_CACHE.clear()
    clear_connector_snapshot_cache()
    clear_read_action_result_cache()
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
        "model": "gpt-5.4-mini",
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
        "model": "claude-sonnet-4-6",
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


_DEFAULT_DIALOGUE_SETTINGS = {
    "clarification_threshold": 0.65,
    "escalation_threshold": 0.40,
    "proactive_suggestions_enabled": True,
    "max_suggestions_per_response": 2,
    "consensus_enabled": True,
    "sentiment_detection_enabled": True,
    "memory_retention_days": 90,
    "default_persona": "friendly_assistant",
}


@contextmanager
def patch_agent_streaming_dialogue_pipeline() -> Iterator[None]:
    """Stub conversational pipeline deps added to execute_task_streaming()."""
    mock_load = AsyncMock(return_value=_DEFAULT_DIALOGUE_SETTINGS)
    patch_targets = (
        "app.services.chat_dialogue_settings.load_chat_dialogue_settings",
        "app.services.persona_service.load_chat_dialogue_settings",
        "app.services.proactive_guidance_service.load_chat_dialogue_settings",
        "app.services.conversational_consensus_service.load_chat_dialogue_settings",
        "app.services.intelligence_router.load_chat_dialogue_settings",
    )
    import app.services.persona_service as persona_module

    with ExitStack() as stack:
        for target in patch_targets:
            stack.enter_context(patch(target, mock_load))
        stack.enter_context(
            patch(
                "app.services.persona_service.PersonaService._load_user_preference",
                AsyncMock(return_value=None),
            )
        )
        persona_module._persona_service = None
        mock_retrieval = MagicMock()
        mock_retrieval.rag_sources = []
        mock_retrieval.rag_section = ""
        mock_retrieval.memory_section = ""
        mock_retrieval.org_context = {"connectedIntegrations": ["hubspot"]}
        mock_turn = MagicMock()
        mock_turn.agent = {"id": "assistant", "name": "Assistant"}
        mock_turn.retrieval = mock_retrieval
        mock_turn.connected_integrations = ["hubspot"]
        mock_turn.org_context_block = ""
        mock_turn.memory_block = ""
        mock_turn.company_block = ""
        mock_turn.entity_block = ""
        mock_turn.task_state_section = ""
        mock_turn.context_explanation = "Org and knowledge context were considered."
        mock_turn.context_profile = {"sourcesUsed": []}
        mock_turn.pre_execution_confidence = {"risk_level": "low"}
        mock_turn.business_signals = []
        mock_turn.strategic_plan = None
        mock_turn.knowledge_assignments = []
        mock_turn.assigned_sources_used = []
        mock_turn.knowledge_gap_message = None
        mock_turn.missing_assignment_labels = []
        mock_turn.memory_conflicts = []
        mock_turn.specialist_modifier = ""
        mock_orchestrator = MagicMock()
        mock_orchestrator.prepare_assistant_turn = AsyncMock(return_value=mock_turn)
        mock_orchestrator.finalize_confidence = MagicMock(
            return_value={"score": 0.82, "band": "high", "needs_clarification": False}
        )
        stack.enter_context(
            patch(
                "app.services.intelligence_orchestrator.get_intelligence_orchestrator",
                return_value=mock_orchestrator,
            )
        )
        stack.enter_context(
            patch(
                "app.operators.agent_intelligence.validate_grounded_answer",
                AsyncMock(return_value={"is_valid": True, "confidence": 0.9}),
            )
        )
        mock_facade = MagicMock()
        mock_facade.enrich_classification = AsyncMock(side_effect=lambda classification, org_id, query_text: classification)
        mock_facade.run_router_enrichments = AsyncMock(return_value={})
        mock_facade.simulate_action_if_required = AsyncMock(return_value=None)
        mock_facade.resolve_chat_model = AsyncMock(return_value=("gpt-test", {"source": "test"}))
        mock_facade.build_route_metadata = MagicMock(
            return_value={"strategy_key": "test", "segment_key": "test", "model_selection": {}},
        )
        mock_facade.build_trust_metadata = MagicMock(return_value={"trust_envelope": {}})
        stack.enter_context(
            patch(
                "app.services.chat_intelligence_facade.get_chat_intelligence_facade",
                return_value=mock_facade,
            )
        )
        yield


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
