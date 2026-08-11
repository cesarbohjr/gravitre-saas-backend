"""Tests for adaptive research cascade."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.adaptive_research_cascade import (
    ResearchScope,
    assess_internal_retrieval_thinness,
    build_research_policy_extension,
    build_research_scope_options,
    evaluate_research_cascade,
    resolve_active_stages,
)


def _settings(*, internet_enabled: bool = False, tavily: str = "", gemini: str = "") -> SimpleNamespace:
    key = gemini or ("test-gemini-key" if internet_enabled and not tavily else "")
    return SimpleNamespace(
        internet_research_enabled=internet_enabled,
        tavily_api_key=tavily,
        gemini_api_key=key,
        web_research_provider="tavily" if tavily and not key else "google",
        web_research_fallback_tavily=True,
        google_genai_use_vertexai=False,
        google_cloud_project="",
        google_cloud_location="us-central1",
    )


def test_assess_thinness_when_no_sources():
    assert assess_internal_retrieval_thinness(
        retrieval_effectiveness={"source_count": 0, "retrieval_score": None},
        rag_sources=[],
        memory_context={},
        graph_context={},
    )


def test_assess_not_thin_with_strong_scores():
    assert not assess_internal_retrieval_thinness(
        retrieval_effectiveness={"source_count": 5, "retrieval_score": 0.82},
        rag_sources=[{"content": "Policy handbook section 4", "score": 0.9}],
    )


def test_internet_option_disabled_when_flag_off():
    options = build_research_scope_options(_settings(internet_enabled=False))
    internet = next(row for row in options if row["scope"] == ResearchScope.INTERNET_RESEARCH.value)
    assert internet["enabled"] is False
    assert internet["disabled_reason"]


def test_internet_option_enabled_by_default_when_provider_configured():
    options = build_research_scope_options(_settings(internet_enabled=True, tavily="tvly-test"))
    internet = next(row for row in options if row["scope"] == ResearchScope.INTERNET_RESEARCH.value)
    assert internet["enabled"] is True


def test_evaluate_research_cascade_auto_internet_when_thin():
    state = evaluate_research_cascade(
        retrieval_effectiveness={"source_count": 0, "retrieval_score": None},
        rag_sources=[],
        settings=_settings(internet_enabled=True, tavily="tvly-test"),
    )
    assert state["internal_thin"] is True
    assert state["suggest_broaden"] is False
    assert state["prompt_message"] is None
    assert state["options"] == []
    assert state["auto_internet_when_thin"] is True
    assert "internet_research" in state["active_stages"]


def test_evaluate_research_cascade_no_prompt_when_scope_selected():
    state = evaluate_research_cascade(
        retrieval_effectiveness={"source_count": 0, "retrieval_score": None},
        rag_sources=[],
        research_scope=ResearchScope.INTELLIGENCE_PACKS.value,
        settings=_settings(),
    )
    assert state["suggest_broaden"] is False
    assert state["options"] == []


def test_resolve_active_stages_everything_without_internet_when_gated():
    stages = resolve_active_stages(ResearchScope.EVERYTHING.value, settings=_settings())
    assert "intelligence_packs" in stages
    assert "internet_research" not in stages


def test_build_research_policy_extension_for_thin_retrieval():
    section = build_research_policy_extension(
        research_scope=None,
        cascade_state={
            "internal_thin": True,
            "active_stages": ["internal_rag", "internet_research"],
            "internet_research": {"ran": True, "result_count": 2},
        },
    )
    assert "automatically" in section.lower()
    assert "internet research" in section.lower()


def test_normalize_internet_results():
    from app.services.adaptive_research_cascade import normalize_internet_results

    rows = normalize_internet_results(
        {
            "totalResults": 1,
            "results": [{"title": "Example", "url": "https://example.com", "snippet": "Hello world"}],
        }
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == "internet"
    assert rows[0]["url"] == "https://example.com"


def test_should_run_internet_research_when_governance_allows():
    from app.services.adaptive_research_cascade import should_run_internet_research

    assert should_run_internet_research(
        ResearchScope.INTERNET_RESEARCH.value,
        settings=_settings(internet_enabled=True, tavily="tvly-test"),
    )
    assert should_run_internet_research(
        ResearchScope.INTERNAL_ONLY.value,
        settings=_settings(internet_enabled=True, tavily="tvly-test"),
        internal_thin=True,
    )
    assert not should_run_internet_research(
        ResearchScope.INTERNAL_ONLY.value,
        settings=_settings(internet_enabled=True, tavily="tvly-test"),
        internal_thin=False,
    )
    assert not should_run_internet_research(
        ResearchScope.INTERNET_RESEARCH.value,
        settings=_settings(),
    )


def test_should_run_intelligence_packs_stage():
    from app.services.adaptive_research_cascade import should_run_intelligence_packs_stage

    assignment = {"metadata": {"intelligence_pack_id": "executive-intelligence-pack"}}
    assert should_run_intelligence_packs_stage(
        ResearchScope.INTELLIGENCE_PACKS.value,
        settings=_settings(),
        knowledge_assignments=[assignment],
    )
    assert not should_run_intelligence_packs_stage(
        ResearchScope.INTERNAL_ONLY.value,
        settings=_settings(),
        knowledge_assignments=[assignment],
    )


def test_build_research_policy_extension_mentions_pack_sources():
    section = build_research_policy_extension(
        research_scope=ResearchScope.INTELLIGENCE_PACKS.value,
        cascade_state={
            "internal_thin": False,
            "active_stages": ["intelligence_packs"],
            "intelligence_packs": {"ran": True, "result_count": 2},
        },
    )
    assert "Intelligence pack sources" in section


def test_enrich_research_cascade_exposed_in_evaluate_flow():
    from app.services.adaptive_research_cascade import enrich_research_cascade

    enriched = enrich_research_cascade(
        evaluate_research_cascade(
            retrieval_effectiveness={"source_count": 1, "retrieval_score": 0.5, "top_sources": []},
            rag_sources=[{"content": "x"}],
            settings=_settings(),
        ),
        retrieval_effectiveness={"source_count": 1, "retrieval_score": 0.5, "top_sources": []},
        sources=[{"kind": "knowledge"}],
    )
    assert enriched["confidence_band"] == "medium"


def test_attach_internet_research_to_cascade():
    from app.services.adaptive_research_cascade import attach_internet_research_to_cascade

    merged = attach_internet_research_to_cascade(
        {"internal_thin": True},
        payload={"totalResults": 2, "results": [{}, {}]},
        ran=True,
    )
    assert merged["internet_research"]["ran"] is True
    assert merged["internet_research"]["result_count"] == 2
