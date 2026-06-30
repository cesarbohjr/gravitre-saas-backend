from __future__ import annotations

from types import SimpleNamespace

from app.services.assistant_availability import (
    apply_bounded_answer_if_needed,
    build_bounded_unavailable_answer,
    is_external_or_general_question,
    is_web_search_configured,
    rag_sources_effectively_empty,
    should_short_circuit_before_generation,
    web_search_failed_in_tool_results,
)
from app.services.assistant_tools import knowledge_base_output_from_retrieval


def test_knowledge_base_output_from_retrieval_shape():
    payload = knowledge_base_output_from_retrieval(
        [{"source": "Gravitre Platform Guide", "content": "Gravitre is an AI platform.", "score": 0.91}],
        {"embedding_method": "openai"},
        {"memories": [{"content": "User prefers concise answers", "score": 0.5}]},
    )
    assert payload["totalResults"] == 1
    assert payload["method"] == "openai"
    assert payload["results"][0]["title"] == "Gravitre Platform Guide"
    assert payload["memoryHitCount"] == 1


def test_should_short_circuit_when_web_unconfigured():
    settings = SimpleNamespace(tavily_api_key="")
    assert should_short_circuit_before_generation(
        query="What is happening in the AI industry today?",
        rag_sources=[],
        settings=settings,
        permitted_registry={"web_search", "knowledge_base"},
    )


def test_should_not_short_circuit_with_kb_hits():
    settings = SimpleNamespace(tavily_api_key="")
    assert not should_short_circuit_before_generation(
        query="What is Gravitre?",
        rag_sources=[{"content": "Gravitre is an automation platform."}],
        settings=settings,
        permitted_registry={"web_search"},
    )


def test_apply_bounded_answer_after_failed_web_search():
    settings = SimpleNamespace(tavily_api_key="tvly-test")
    bounded = apply_bounded_answer_if_needed(
        "Here is a long generic essay about AI industry trends..." * 20,
        query="What is happening in the AI industry today?",
        rag_sources=[],
        tool_results=[
            {
                "name": "searchWeb",
                "output": {"error": "Web search is not configured for this environment. Set TAVILY_API_KEY."},
            }
        ],
        settings=settings,
        connected_integrations=["platform"],
    )
    assert "verified information" in bounded.lower()
    assert "/connectors" in bounded


def test_web_search_failed_detection():
    assert web_search_failed_in_tool_results(
        [{"name": "searchWeb", "output": {"error": "unavailable"}}]
    )
    assert not web_search_failed_in_tool_results(
        [{"name": "searchWeb", "output": {"results": [{"title": "News"}], "totalResults": 1}}]
    )


def test_external_question_heuristics():
    assert is_external_or_general_question("What is Gravitre?")
    assert not is_external_or_general_question("What is our HubSpot pipeline this week?")


def test_build_bounded_answer_includes_connector_guidance():
    message = build_bounded_unavailable_answer(
        web_configured=False,
        web_attempted=False,
        connected_integrations=["platform"],
    )
    assert "/connectors" in message
    assert "TAVILY_API_KEY" in message


def test_rag_empty_detection():
    assert rag_sources_effectively_empty([])
    assert rag_sources_effectively_empty([{"content": ""}])
    assert not rag_sources_effectively_empty([{"content": "hello"}])
