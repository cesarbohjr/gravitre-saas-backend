"""The replan loop: does it go back for more evidence, and does it ever run away.

The gap this closes was not "no code for reflection" — reflection existed and
already emitted a ``retrieve_more`` action. The gap was that nothing consumed it,
so an insufficient-evidence finding changed the wording of an answer and never
the evidence behind it. These tests hold the parts that make the difference:

  * the bar is not uniform (a regulatory question needs more than a casual one)
  * insufficiency triggers retrieval from a source NOT already tried
  * iteration is hard-bounded, and the shortfall is stated rather than hidden
  * a simple/spoken turn does not pay for any of it
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import unified_turn_knowledge_context as ctx_mod
from app.services.evidence_sufficiency_service import (
    BAR_BUSINESS,
    BAR_CASUAL,
    BAR_REGULATORY,
    SufficiencyBar,
    SufficiencyVerdict,
    assess_evidence_sufficiency,
    sufficiency_bar_for,
    summarize_evidence_process,
)


def _settings(**overrides: Any) -> Any:
    base = {
        "evidence_sufficiency_loop_enabled": True,
        "evidence_sufficiency_max_rounds": 2,
        "evidence_contradiction_check_enabled": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
# Phase 1 — the bar
# --------------------------------------------------------------------------


def test_regulatory_questions_get_a_higher_bar_than_business_questions() -> None:
    legal = sufficiency_bar_for(
        query="What notice period does Ontario employment law require?",
        route_departments=["legal"],
        route_jurisdictions=["CA-ON"],
    )
    business = sufficiency_bar_for(
        query="Which of our deals slipped last month and why?",
        route_departments=["sales"],
        route_jurisdictions=[],
    )
    assert legal.name == BAR_REGULATORY
    assert business.name == BAR_BUSINESS
    assert legal.min_sources > business.min_sources
    assert legal.require_citable_source and not business.require_citable_source
    assert legal.require_freshness_signal and not business.require_freshness_signal


def test_compliance_language_alone_raises_the_bar() -> None:
    """A sales-department question can still be a regulatory one."""
    bar = sufficiency_bar_for(
        query="Is our cold outreach sequence CCPA compliant?",
        route_departments=["sales"],
        route_jurisdictions=[],
    )
    assert bar.name == BAR_REGULATORY
    assert "compliance" in bar.reason


def test_conversational_depth_short_circuits_to_the_casual_bar() -> None:
    bar = sufficiency_bar_for(
        query="What notice period does Ontario employment law require?",
        route_departments=["legal"],
        route_jurisdictions=["CA-ON"],
        reasoning_depth="conversational",
    )
    assert bar.name == BAR_CASUAL
    assert bar.min_sources == 0


@pytest.mark.asyncio
async def test_casual_bar_never_calls_a_model() -> None:
    """The latency guard: the loop must cost nothing on a fast-path turn."""
    bar = sufficiency_bar_for(query="hey", reasoning_depth="conversational")
    verdict = await assess_evidence_sufficiency(
        query="hey", rows=[], bar=bar, settings=_settings()
    )
    assert verdict.sufficient is True
    assert verdict.assessor == "skipped_casual_bar"


@pytest.mark.asyncio
async def test_regulatory_bar_rejects_evidence_with_no_citable_source() -> None:
    """Two chunks of unattributed prose do not answer a legal question.

    This is the case the old thinness heuristic passed: source_count was fine.
    """
    bar = sufficiency_bar_for(
        query="What are the statutory breach notification deadlines?",
        route_departments=["legal"],
        route_jurisdictions=["US-federal"],
    )
    rows = [
        {"kind": "knowledge", "content": "Some general prose about breaches."},
        {"kind": "knowledge", "content": "More general prose about notifying people."},
    ]
    verdict = await assess_evidence_sufficiency(
        query="What are the statutory breach notification deadlines?",
        rows=rows,
        bar=bar,
        settings=_settings(),
    )
    assert verdict.sufficient is False
    assert verdict.assessor == "deterministic"
    assert verdict.gaps == ["no_citable_source"]
    # The reason has to read as a statement a human can act on.
    assert "requires an attributable source" in verdict.reason
    assert "has neither" not in verdict.reason


@pytest.mark.asyncio
async def test_undated_evidence_is_not_a_dead_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing freshness must reach the assessor, not veto before reasoning.

    Live traffic found this: web results carry no provider date, so treating a
    freshness signal as a hard structural requirement made every web-answered
    regulatory question fail the gate before any judgement happened, and the
    loop then spent its entire round budget on a bar that could not be met.
    """
    seen: dict[str, str] = {}

    class _Resp:
        content = '{"sufficient": true, "reason": "structural rule, currency not material", "gaps": [], "confidence": 0.7}'

    class _Router:
        async def complete(self, *a: Any, **kw: Any):
            seen["prompt"] = a[1] if len(a) > 1 else kw.get("prompt", "")
            return _Resp()

    import app.services.model_router as mr

    # Deliberately zero-arg, matching the real factory. A permissive
    # lambda *_a, **_k here is what let a get_model_router(settings) TypeError
    # reach production green: the mock accepted a call the real function rejects.
    monkeypatch.setattr(mr, "get_model_router", lambda: _Router())

    bar = sufficiency_bar_for(
        query="What does the ESA require for mass terminations?",
        route_departments=["legal"],
        route_jurisdictions=["CA-ON"],
    )
    # Cited, but undated — exactly the shape a Serper result arrives in.
    rows = [
        {"kind": "internet", "content": "ESA mass termination rules...", "url": "https://x", "last_updated": None},
        {"kind": "internet", "content": "Notice thresholds are 8, 12, 16 weeks", "url": "https://y", "last_updated": None},
    ]
    verdict = await assess_evidence_sufficiency(
        query="What does the ESA require for mass terminations?",
        rows=rows,
        bar=bar,
        settings=_settings(),
    )
    assert verdict.assessor == "llm", "undated evidence must still be reasoned about"
    assert verdict.sufficient is True
    # The assessor was told currency was unverifiable so it can weigh it.
    assert "effective date or last-updated signal" in seen["prompt"]


@pytest.mark.asyncio
async def test_a_broken_assessor_withholds_sufficiency_rather_than_granting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An assessor that cannot run means UNKNOWN, never "sufficient".

    A live prod run at tip f8dc5f64 returned final_sufficient=True for a
    regulatory question because the assessor raised a TypeError and the handler
    failed open. That told the rest of the turn the evidence had cleared its bar
    when nothing had judged it — the exact outcome this loop exists to prevent.
    """

    class _Boom:
        async def complete(self, *a: Any, **kw: Any):
            raise RuntimeError("model unavailable")

    import app.services.model_router as mr

    monkeypatch.setattr(mr, "get_model_router", lambda: _Boom())

    bar = sufficiency_bar_for(
        query="What is the SEC materiality standard for Item 1.05?",
        route_departments=["finance"],
    )
    rows = [
        {"kind": "knowledge_pack", "content": "Item 1.05 materiality...", "citation": "SEC", "last_updated": "2024-07-01"},
        {"kind": "knowledge_pack", "content": "Reasonable investor test...", "citation": "SEC", "last_updated": "2024-07-01"},
    ]
    verdict = await assess_evidence_sufficiency(
        query="What is the SEC materiality standard for Item 1.05?",
        rows=rows,
        bar=bar,
        settings=_settings(),
    )
    assert verdict.assessor == "assessor_error"
    assert verdict.sufficient is False, "a failed check must not certify evidence"
    assert "assessor_unavailable" in verdict.gaps


@pytest.mark.asyncio
async def test_sufficiency_verdict_carries_module_c_labels() -> None:
    bar = sufficiency_bar_for(query="x " * 10, route_departments=["sales"])
    verdict = await assess_evidence_sufficiency(
        query="x " * 10, rows=[], bar=bar, settings=_settings()
    )
    payload = verdict.to_dict()
    # A sufficiency judgement is an estimate; Module C requires it be labelled.
    assert "assessment_confidence" in payload
    assert payload["confidence_source"] == "insufficient_data"
    assert payload["confidence_is_estimate"] is False


# --------------------------------------------------------------------------
# Phase 2 — the bounded loop
# --------------------------------------------------------------------------


@pytest.fixture
def stub_sources(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Replace every real retriever; record which ones the loop reaches for."""
    calls: dict[str, list[str]] = {"order": []}

    async def packs(**kwargs: Any):
        calls["order"].append("knowledge_pack")
        return ("PACKS", {"fabric_hit_count": 1}, [{"kind": "knowledge_pack", "content": "pack text"}])

    async def org_rag(**kwargs: Any):
        calls["order"].append("org_rag")
        return ("RAG", {"org_rag_chunk_count": 1}, [{"kind": "knowledge", "content": "rag text"}])

    async def internet(**kwargs: Any):
        calls["order"].append("internet")
        return ("WEB", {"internet_hit_count": 2}, [{"kind": "internet", "content": "web text"}])

    async def graph(**kwargs: Any):
        calls["order"].append("business_graph")
        return ("GRAPH", {"business_graph_status": "ok"}, [{"kind": "graph", "content": "graph text"}])

    monkeypatch.setattr(ctx_mod, "_retrieve_knowledge_packs", packs)
    monkeypatch.setattr(ctx_mod, "_retrieve_org_rag", org_rag)
    monkeypatch.setattr(ctx_mod, "_run_internet_prefetch", internet)
    monkeypatch.setattr(ctx_mod, "_retrieve_business_graph", graph)

    import app.services.adaptive_research_cascade as cascade

    monkeypatch.setattr(cascade, "assess_internal_retrieval_thinness", lambda **_: False)
    monkeypatch.setattr(cascade, "should_run_internet_research", lambda *a, **k: False)
    return calls


def _always(sufficient: bool) -> Any:
    async def _assess(*, query, rows, bar, settings=None, org_id=None, routing_tier="multi_step", sources_tried=None):
        return SufficiencyVerdict(
            sufficient=sufficient,
            bar=bar,
            assessor="stub",
            reason="stubbed",
            gaps=[] if sufficient else ["does_not_address_question"],
            confidence=0.5,
        )

    return _assess


@pytest.mark.asyncio
async def test_sufficient_evidence_does_not_trigger_extra_retrieval(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _always(True))

    block, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="Which competitors did we lose deals to last quarter and why?",
        client=object(),
        settings=_settings(),
        classification={"department": "sales"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    loop = meta["evidenceSufficiency"]
    assert loop["additional_rounds_used"] == 0
    assert "internet" not in stub_sources["order"]
    assert "business_graph" not in stub_sources["order"]
    assert block


@pytest.mark.asyncio
async def test_insufficient_evidence_escalates_to_a_source_not_yet_tried(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _always(False))

    block, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(),
        classification={"department": "legal"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    loop = meta["evidenceSufficiency"]
    # Escalated to both untried sources, in the Router's own order.
    assert stub_sources["order"] == [
        "knowledge_pack",
        "org_rag",
        "internet",
        "business_graph",
    ]
    assert loop["additional_rounds_used"] == 2
    assert loop["sources_tried"][-2:] == ["internet", "business_graph"]
    assert "WEB" in block and "GRAPH" in block


@pytest.mark.asyncio
async def test_a_broken_assessor_stops_the_loop_instead_of_burning_the_budget(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    """Withholding sufficiency must not turn every turn into a full escalation.

    Once a failed assessor reports sufficient=False (correctly, since nothing
    judged the evidence), a naive loop would escalate through every remaining
    source on every turn whenever the fast model hiccups. More evidence cannot
    fix an assessor that is not running, so the loop stops and says so.
    """
    import app.services.evidence_sufficiency_service as suff

    async def _errored(*, query, rows, bar, settings=None, org_id=None, routing_tier="multi_step", sources_tried=None):
        return SufficiencyVerdict(
            sufficient=False,
            bar=bar,
            assessor="assessor_error",
            reason="sufficiency assessor unavailable: boom",
            gaps=["assessor_unavailable"],
            confidence=None,
        )

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _errored)

    block, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(),
        classification={"department": "legal"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    loop = meta["evidenceSufficiency"]
    assert loop["additional_rounds_used"] == 0
    assert loop["stopped_because"] == "assessor_unavailable"
    assert "internet" not in stub_sources["order"]
    # And the model is told the check did not run, not that evidence fell short.
    assert "EVIDENCE SUFFICIENCY UNVERIFIED" in block
    assert "EVIDENCE SUFFICIENCY WARNING" not in block


@pytest.mark.asyncio
async def test_iteration_is_hard_bounded_and_the_shortfall_is_stated(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    """Never-sufficient evidence must stop at the cap and say so honestly."""
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _always(False))

    block, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What will the Ontario statutory notice period be in 2031?",
        client=object(),
        settings=_settings(evidence_sufficiency_max_rounds=2),
        classification={"department": "legal"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    loop = meta["evidenceSufficiency"]
    assert loop["additional_rounds_used"] == 2
    assert loop["additional_rounds_used"] <= loop["max_additional_rounds"]
    assert loop["final_sufficient"] is False
    assert loop["stopped_because"] in {"max_rounds_reached", "no_untried_source"}
    # The prompt must carry the honest warning, not silently answer at full confidence.
    assert "EVIDENCE SUFFICIENCY WARNING" in block
    assert "does not meet the regulatory standard" in block


@pytest.mark.asyncio
async def test_active_ranking_runs_after_all_rounds_and_preserves_warning(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _always(False))
    block, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(
            cross_source_context_engine_shadow_enabled=True,
            cross_source_context_engine_enabled=True,
            cross_source_context_token_budget=2000,
        ),
        classification={"department": "legal", "intent": "knowledge_lookup"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )

    ranking = meta["contextRanking"]
    assert ranking["mode"] == "active"
    assert ranking["candidateCount"] == 4
    assert ranking["selectedCount"] == 4
    assert ranking["selectedByKind"] == {
        "knowledge_fabric": 1,
        "rag": 1,
        "internet": 1,
        "graph": 1,
    }
    assert "EVIDENCE SUFFICIENCY WARNING" in block


@pytest.mark.asyncio
async def test_the_cap_binds_even_when_more_sources_remain_untried(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    """The cap must bound iteration on its own, not by accident.

    Mutation testing caught this: with only two escalation sources, running out
    of sources stopped the loop, so deleting the cap entirely changed nothing
    and every "bounded" assertion still passed. Adding a third source later
    would have quietly removed the only real bound. Here the escalation list is
    longer than the cap, so the cap is the sole thing that can stop it.
    """
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _always(False))
    monkeypatch.setattr(
        ctx_mod,
        "ESCALATION_ORDER",
        ("internet", "business_graph", "internet_again", "graph_again", "and_another"),
    )

    _, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(evidence_sufficiency_max_rounds=2),
        classification={"department": "legal"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    loop = meta["evidenceSufficiency"]
    assert loop["additional_rounds_used"] == 2, "cap did not bound the loop"
    assert loop["stopped_because"] == "max_rounds_reached"
    # Sources beyond the cap were never reached.
    assert "and_another" not in loop["sources_tried"]


@pytest.mark.asyncio
async def test_max_rounds_is_clamped_to_the_ceiling(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    """A misconfigured env var must not produce unbounded retrieval."""
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _always(False))

    _, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(evidence_sufficiency_max_rounds=9999),
        classification={"department": "legal"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    loop = meta["evidenceSufficiency"]
    assert loop["max_additional_rounds"] == ctx_mod.MAX_ADDITIONAL_ROUNDS_CEILING
    # Only two escalation sources exist, so it stops for lack of an untried one
    # rather than spinning.
    assert loop["stopped_because"] == "no_untried_source"
    assert loop["additional_rounds_used"] <= ctx_mod.MAX_ADDITIONAL_ROUNDS_CEILING


@pytest.mark.asyncio
async def test_conversational_turn_pays_nothing_for_the_loop(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    """Latency composition: the fast path must not gain a model call."""
    import app.services.evidence_sufficiency_service as suff

    called = {"n": 0}

    async def _assess(**kwargs: Any):
        called["n"] += 1
        raise AssertionError("sufficiency assessor must not run on a casual turn")

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _assess)

    _, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(),
        classification={"department": "legal"},
        reasoning_depth="conversational",
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    assert called["n"] == 0
    loop = meta["evidenceSufficiency"]
    assert loop["skipped"] == "casual_bar"
    assert loop["additional_rounds_used"] == 0
    assert "internet" not in stub_sources["order"]


@pytest.mark.asyncio
async def test_kill_switch_restores_single_pass_behaviour(
    monkeypatch: pytest.MonkeyPatch, stub_sources: dict[str, list[str]]
) -> None:
    import app.services.evidence_sufficiency_service as suff

    async def _assess(**kwargs: Any):
        raise AssertionError("assessor must not run when the flag is off")

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _assess)

    _, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(evidence_sufficiency_loop_enabled=False),
        classification={"department": "legal"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )
    assert meta["evidenceSufficiency"]["skipped"] == "flag_disabled"
    assert stub_sources["order"] == ["knowledge_pack", "org_rag"]


# --------------------------------------------------------------------------
# Phase 4 — transparency only when it matters
# --------------------------------------------------------------------------


def test_clean_single_pass_produces_no_process_noise() -> None:
    assert (
        summarize_evidence_process(
            {
                "evidenceSufficiency": {
                    "additional_rounds_used": 0,
                    "final_sufficient": True,
                    "sources_tried": ["knowledge_pack", "org_rag"],
                },
                "evidenceConflicts": {"count": 0},
            }
        )
        is None
    )


def test_process_summary_appears_when_iteration_happened() -> None:
    summary = summarize_evidence_process(
        {
            "evidenceSufficiency": {
                "additional_rounds_used": 2,
                "final_sufficient": False,
                "final_gaps": ["stale_evidence"],
                "final_reason": "sources predate the amendment",
                "stopped_because": "max_rounds_reached",
                "bar": "regulatory",
                "sources_tried": ["knowledge_pack", "org_rag", "internet", "business_graph"],
            }
        }
    )
    assert summary is not None
    assert summary["retrieval_rounds"] == 3
    assert summary["additional_rounds_triggered"] == 2
    assert summary["evidence_met_standard"] is False
    assert summary["shortfall"] == ["stale_evidence"]
    assert "provisional" in summary["confidence_note"]


def test_unresolved_conflict_forces_a_confidence_note() -> None:
    summary = summarize_evidence_process(
        {
            "evidenceSufficiency": {
                "additional_rounds_used": 0,
                "final_sufficient": True,
                "sources_tried": ["knowledge_pack", "org_rag"],
            },
            "evidenceConflicts": {
                "count": 1,
                "resolved": 0,
                "unresolved": 1,
                "details": [
                    {
                        "subject": "notice period",
                        "resolution": "unresolved",
                        "rationale": "no dating",
                    }
                ],
            },
        }
    )
    assert summary is not None
    assert summary["source_conflicts"]["unresolved"] == 1
    assert "disagree" in summary["confidence_note"]
