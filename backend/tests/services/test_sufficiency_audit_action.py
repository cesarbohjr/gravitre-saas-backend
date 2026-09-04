"""The sufficiency gate must have a queryable audit action, and a real actor.

Before this, the verdict existed only as nested metadata inside
`latency_breakdown.unifiedTurnKnowledge` on `unified_turn.*` events. Phase 0 of
the CRAG audit measured `evidence.sufficiency.assessed` at zero events over 30
days, because no such action was ever emitted.

The tests that matter here are not "does it write a row". They are the two
failure modes this program has already paid for:

  * `write_audit_event` silently drops the insert when actor_id or resource_id
    is not a UUID. Three instruments were written with `actor_id=None` during
    the dormant-call audit, read zero events in production, and two of those
    zeroes were read as "this code path is never reached" -- very nearly the
    basis for retiring live code. A missing actor must be loud.
  * `assessorRan` must be computed against the module constants. The grounding
    validator compared its confidence source against a literal "model" when the
    real value was "loaded_model_artifact", so the field read False on every
    event and was interpreted as a validator that always failed open.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import unified_turn_knowledge_context as ctx_mod
from app.services.evidence_sufficiency_service import (
    ASSESSOR_DETERMINISTIC,
    ASSESSOR_ERROR,
    ASSESSOR_LLM,
    MODEL_ASSESSORS,
    SufficiencyVerdict,
    sufficiency_bar_for,
)

ORG = "11111111-1111-4111-8111-111111111111"
ACTOR = "22222222-2222-4222-8222-222222222222"
CONVO = "33333333-3333-4333-8333-333333333333"


def _settings(**overrides: Any) -> Any:
    base = {
        "evidence_sufficiency_loop_enabled": True,
        "evidence_sufficiency_max_rounds": 2,
        "evidence_contradiction_check_enabled": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def captured_audits(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture write_audit_event calls positionally, as the real signature is."""
    calls: list[dict[str, Any]] = []

    def _write(client, org_id, actor_id, action, resource_type, resource_id, metadata=None):
        calls.append(
            {
                "org_id": org_id,
                "actor_id": actor_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "metadata": metadata or {},
            }
        )

    import app.workflows.audit as audit_mod

    monkeypatch.setattr(audit_mod, "write_audit_event", _write)
    return calls


@pytest.fixture
def stub_sources(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    calls: dict[str, list[str]] = {"order": []}

    async def packs(**kwargs: Any):
        calls["order"].append("knowledge_pack")
        return ("PACKS", {"fabric_hit_count": 1}, [{"kind": "knowledge_pack", "content": "pack text"}])

    async def org_rag(**kwargs: Any):
        calls["order"].append("org_rag")
        return ("RAG", {"org_rag_chunk_count": 2}, [{"kind": "knowledge", "content": "rag text"}])

    async def internet(**kwargs: Any):
        calls["order"].append("internet")
        return ("WEB", {"internet_hit_count": 4}, [{"kind": "internet", "content": "web text"}])

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


def _verdict(sufficient: bool, assessor: str) -> Any:
    async def _assess(*, query, rows, bar, settings=None, org_id=None, routing_tier="multi_step", sources_tried=None):
        return SufficiencyVerdict(
            sufficient=sufficient,
            bar=bar,
            assessor=assessor,
            reason="stubbed reason",
            gaps=[] if sufficient else ["does_not_address_question"],
            confidence=0.5,
        )

    return _assess


async def _build(**overrides: Any) -> tuple[str, dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "org_id": ORG,
        "query": "What are the statutory breach notification deadlines in Ontario?",
        "client": object(),
        "settings": _settings(),
        "classification": {"department": "legal"},
        "knowledge_assignments": [
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
        "actor_id": ACTOR,
        "conversation_id": CONVO,
    }
    kwargs.update(overrides)
    return await ctx_mod.build_unified_turn_knowledge_context(**kwargs)


# ---------------------------------------------------------------------------
# the action exists and is queryable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_loop_run_emits_a_named_audit_action(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_LLM))

    _, meta = await _build()

    assert len(captured_audits) == 1, "the gate must emit exactly one event per turn"
    event = captured_audits[0]
    assert event["action"] == "evidence.sufficiency.assessed"
    assert event["action"] == ctx_mod.AUDIT_ACTION_SUFFICIENCY
    assert event["org_id"] == ORG
    assert event["resource_type"] == "conversation"
    assert meta["evidenceSufficiency"]["audit_emitted"] is True


@pytest.mark.asyncio
async def test_the_event_carries_the_verdict_a_query_would_ask_for(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_LLM))

    await _build()
    payload = captured_audits[0]["metadata"]

    assert payload["bar"] == "regulatory"
    assert payload["finalSufficient"] is False
    assert payload["finalGaps"] == ["does_not_address_question"]
    assert payload["stoppedBecause"] in {"no_untried_source", "max_rounds_reached"}
    assert payload["additionalRoundsUsed"] >= 1
    assert payload["maxAdditionalRounds"] == 2
    assert "internet" in payload["sourcesTried"]
    # The evidence actually behind the verdict, not just the verdict.
    assert payload["evidenceCounts"]["orgRag"] == 2
    assert payload["evidenceCounts"]["internet"] == 4


# ---------------------------------------------------------------------------
# a real actor, or a loud skip -- never a silent one
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_missing_actor_is_recorded_and_logged_not_swallowed(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits, caplog
) -> None:
    """The actor_id=None failure mode, made impossible to repeat quietly."""
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_LLM))

    with caplog.at_level("WARNING"):
        _, meta = await _build(actor_id=None)

    assert captured_audits == [], "must not attempt an insert that would be dropped"
    assert meta["evidenceSufficiency"]["audit_skipped"] == "non_uuid_actor_or_resource"
    assert "sufficiency_audit_skipped" in caplog.text
    assert "audit_emitted" not in meta["evidenceSufficiency"]


@pytest.mark.asyncio
async def test_a_non_uuid_actor_is_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    """`write_audit_event` drops non-UUID actors too, not only None."""
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_LLM))

    _, meta = await _build(actor_id="system")

    assert captured_audits == []
    assert meta["evidenceSufficiency"]["audit_skipped"] == "non_uuid_actor_or_resource"


@pytest.mark.asyncio
async def test_a_missing_conversation_is_also_caught(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    """resource_id is uuid NOT NULL as well; a real actor alone is not enough."""
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_LLM))

    _, meta = await _build(conversation_id=None)

    assert captured_audits == []
    assert meta["evidenceSufficiency"]["audit_skipped"] == "non_uuid_actor_or_resource"


@pytest.mark.asyncio
async def test_an_audit_failure_never_breaks_the_turn(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    import app.services.evidence_sufficiency_service as suff
    import app.workflows.audit as audit_mod

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_LLM))

    def _boom(*a: Any, **k: Any):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(audit_mod, "write_audit_event", _boom)

    block, meta = await _build()

    assert block, "the turn must still produce its knowledge block"
    assert meta["evidenceSufficiency"]["audit_skipped"].startswith("write_failed:")


# ---------------------------------------------------------------------------
# assessorRan, computed against constants rather than a literal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assessor_ran_is_true_when_a_model_judged(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_LLM))

    await _build()
    payload = captured_audits[0]["metadata"]

    assert payload["assessorRan"] is True
    assert payload["assessorUnavailable"] is False
    # The raw values are kept so assessorRan is cross-checkable, not just trusted.
    assert payload["assessors"] and set(payload["assessors"]) == {ASSESSOR_LLM}


@pytest.mark.asyncio
async def test_a_deterministic_verdict_did_not_involve_a_model(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    """A structural short-circuit is a real verdict but not a reasoned one."""
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(
        suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_DETERMINISTIC)
    )

    await _build()
    payload = captured_audits[0]["metadata"]

    assert payload["assessorRan"] is False
    assert payload["assessorUnavailable"] is False
    assert set(payload["assessors"]) == {ASSESSOR_DETERMINISTIC}


@pytest.mark.asyncio
async def test_fail_closed_announces_itself_in_the_event(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    """An unjudged turn must not look like one that genuinely fell short."""
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _verdict(False, ASSESSOR_ERROR))

    await _build()
    payload = captured_audits[0]["metadata"]

    assert payload["assessorUnavailable"] is True
    assert payload["assessorRan"] is False
    assert payload["stoppedBecause"] == "assessor_unavailable"
    # finalSufficient=False here means UNKNOWN, and the pair of fields is what
    # makes the two cases distinguishable at query time.
    assert payload["finalSufficient"] is False


@pytest.mark.asyncio
async def test_assessor_ran_does_not_compare_against_a_string_literal() -> None:
    """Pin the constants themselves, so a rename cannot silently zero the field.

    The grounding validator's assessorRan bug was exactly this: a literal that
    stopped matching the real value, with nothing to catch it.
    """
    assert ASSESSOR_LLM in MODEL_ASSESSORS
    assert ASSESSOR_DETERMINISTIC not in MODEL_ASSESSORS
    assert ASSESSOR_ERROR not in MODEL_ASSESSORS


# ---------------------------------------------------------------------------
# the fast path must not pay for any of this
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_conversational_turn_writes_no_audit_row(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    """A row per skipped turn would add a write to the conversational fast path."""
    import app.services.evidence_sufficiency_service as suff

    async def _never(**kwargs: Any):
        raise AssertionError("assessor must not run on a casual turn")

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _never)

    _, meta = await _build(reasoning_depth="conversational")

    assert meta.get("skipped") == "conversational_depth"
    assert meta["evidenceSufficiency"]["skipped"] == "conversational_depth"
    assert captured_audits == []


@pytest.mark.asyncio
async def test_a_disabled_loop_writes_no_audit_row(
    monkeypatch: pytest.MonkeyPatch, stub_sources, captured_audits
) -> None:
    _, meta = await _build(settings=_settings(evidence_sufficiency_loop_enabled=False))

    assert meta["evidenceSufficiency"]["skipped"] == "flag_disabled"
    assert captured_audits == []


# ---------------------------------------------------------------------------
# the call site -- the "one layer too low" check
# ---------------------------------------------------------------------------


def test_the_production_call_site_actually_threads_an_actor() -> None:
    """A correct emitter that is never given an actor still records nothing.

    Five times in this program a fix was right and applied one layer below what
    decides user impact. Everything above proves `_emit_sufficiency_audit`
    behaves; none of it proves the real caller supplies the actor, and without
    that the insert is dropped in production exactly as before. So the call site
    itself is pinned.
    """
    import ast
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "unified_turn_reasoning_service.py"
    )
    tree = ast.parse(src.read_text(encoding="utf-8"))

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "build_unified_turn_knowledge_context"
    ]
    assert calls, "the production call site vanished; this guard is now blind"

    for call in calls:
        kwargs = {kw.arg for kw in call.keywords}
        assert "actor_id" in kwargs, (
            f"build_unified_turn_knowledge_context at line {call.lineno} does not "
            "pass actor_id, so the sufficiency audit insert is silently dropped"
        )
        assert "conversation_id" in kwargs, (
            f"build_unified_turn_knowledge_context at line {call.lineno} does not "
            "pass conversation_id; resource_id is uuid NOT NULL"
        )
        # And they must be real values, not None placeholders.
        for kw in call.keywords:
            if kw.arg in {"actor_id", "conversation_id"}:
                assert not (
                    isinstance(kw.value, ast.Constant) and kw.value.value is None
                ), f"{kw.arg} is hardcoded None at line {call.lineno}"


def test_the_bar_helper_still_reports_casual_for_conversational() -> None:
    """Guards the precondition the fast-path test depends on."""
    bar = sufficiency_bar_for(
        query="What notice period does Ontario employment law require?",
        route_departments=["legal"],
        reasoning_depth="conversational",
    )
    assert bar.name == "casual"
