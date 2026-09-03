"""Three-way evidence classification, and what the loop does with it.

The loop already went back for more evidence when the verdict was insufficient.
What it could not do was tell apart two situations that a single bool collapses:

  * the evidence is about the wrong thing  -> keeping it is worse than nothing
  * the evidence is on-topic but thin      -> keeping it and adding a source is right

Both read as ``sufficient=False``, and the loop responded to both by *adding* to
the pile. Wrong evidence is not improved by keeping it, so these tests hold the
distinction and, more importantly, hold the actions that follow from it.

The one that matters most is `test_discard_removes_the_rendered_sections_too`.
Dropping the rows while leaving the rendered text in the prompt would satisfy
every count in the audit payload while the model still read the discarded
evidence -- a fix one layer below the thing that decides what the model sees.
"""
from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import unified_turn_knowledge_context as ctx_mod
from app.services.evidence_sufficiency_service import (
    ASSESSOR_DETERMINISTIC,
    ASSESSOR_ERROR,
    ASSESSOR_LLM,
    ASSESSOR_SKIPPED_CASUAL,
    BAR_CASUAL,
    DISCARD_STANCES,
    ESCALATE_STANCES,
    STANCE_AMBIGUOUS,
    STANCE_CORRECT,
    STANCE_INCORRECT,
    STANCE_UNKNOWN,
    STANCES,
    SufficiencyBar,
    SufficiencyVerdict,
    _parse_stance,
    substantive_rows,
)


def _bar(name: str = "regulatory") -> SufficiencyBar:
    return SufficiencyBar(
        name=name,
        min_sources=1,
        require_citable_source=False,
        require_freshness_signal=False,
    )


def _settings(**overrides: Any) -> Any:
    base = {
        "evidence_sufficiency_loop_enabled": True,
        "evidence_sufficiency_max_rounds": 2,
        "evidence_contradiction_check_enabled": False,
        "cross_source_context_engine_shadow_enabled": False,
        "cross_source_context_engine_enabled": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
# Phase 1 — the classification itself
# --------------------------------------------------------------------------


class TestStanceIsAuthoritative:
    """`sufficient` and `stance` encode one judgement, so they cannot disagree.

    Two fields for the same fact, free to drift, is how `assessorRan` read False
    for weeks while the assessor was running perfectly well.
    """

    def test_sufficient_is_derived_from_stance_not_from_the_argument(self):
        v = SufficiencyVerdict(
            sufficient=True,  # deliberately contradicts the stance
            bar=_bar(),
            assessor=ASSESSOR_LLM,
            reason="r",
            stance=STANCE_AMBIGUOUS,
        )
        assert v.sufficient is False
        assert v.stance == STANCE_AMBIGUOUS

    def test_correct_is_the_only_stance_that_certifies_evidence(self):
        for stance in STANCES:
            v = SufficiencyVerdict(
                sufficient=False, bar=_bar(), assessor=ASSESSOR_LLM, reason="r", stance=stance
            )
            assert v.sufficient is (stance == STANCE_CORRECT)

    def test_an_unknown_stance_string_does_not_certify_evidence(self):
        v = SufficiencyVerdict(
            sufficient=True, bar=_bar(), assessor=ASSESSOR_LLM, reason="r", stance="banana"
        )
        assert v.stance == STANCE_UNKNOWN
        assert v.sufficient is False
        assert v.stance_inferred is True


class TestStanceDefaults:
    def test_a_legacy_true_bool_becomes_correct_and_is_flagged_inferred(self):
        v = SufficiencyVerdict(sufficient=True, bar=_bar(), assessor=ASSESSOR_LLM, reason="r")
        assert v.stance == STANCE_CORRECT
        assert v.stance_inferred is True

    def test_a_legacy_false_bool_becomes_ambiguous_never_incorrect(self):
        """INCORRECT discards evidence, so a default must never reach it."""
        v = SufficiencyVerdict(sufficient=False, bar=_bar(), assessor=ASSESSOR_LLM, reason="r")
        assert v.stance == STANCE_AMBIGUOUS
        assert v.should_discard_evidence is False

    def test_a_failed_assessor_is_unknown_not_a_reasoned_shortfall(self):
        v = SufficiencyVerdict(
            sufficient=False, bar=_bar(), assessor=ASSESSOR_ERROR, reason="boom"
        )
        assert v.stance == STANCE_UNKNOWN
        assert v.should_discard_evidence is False

    @pytest.mark.asyncio
    async def test_the_real_error_path_returns_unknown_and_never_discards(self):
        """Not the same claim as the dataclass default.

        Mutation testing caught this: changing the error path's stance to
        INCORRECT left the whole suite green, because the loop happens to break
        on ASSESSOR_ERROR before reaching the discard. That ordering is the only
        thing standing between a fast-model hiccup and every retrieved excerpt
        being thrown away, and nothing was holding it. A broken assessor must
        never authorise destroying evidence.
        """
        import app.services.evidence_sufficiency_service as suff
        import app.services.model_router as mr

        def _boom():
            raise RuntimeError("model down")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(mr, "get_model_router", _boom)
            v = await suff.assess_evidence_sufficiency(
                query="q",
                rows=[
                    {"content": "x", "citation": "c"},
                    {"content": "y", "citation": "c"},
                ],
                bar=_bar(),
                settings=_settings(),
            )
        assert v.assessor == ASSESSOR_ERROR
        assert v.stance == STANCE_UNKNOWN
        assert v.should_discard_evidence is False
        assert v.sufficient is False
        assert v.should_escalate is False

    def test_an_explicit_stance_is_not_marked_inferred(self):
        v = SufficiencyVerdict(
            sufficient=False,
            bar=_bar(),
            assessor=ASSESSOR_LLM,
            reason="r",
            stance=STANCE_INCORRECT,
        )
        assert v.stance_inferred is False


class TestParseStance:
    def test_reads_an_explicit_stance(self):
        assert _parse_stance({"stance": "INCORRECT"}) == (STANCE_INCORRECT, False)
        assert _parse_stance({"stance": " ambiguous "}) == (STANCE_AMBIGUOUS, False)

    def test_an_unrecognised_stance_falls_to_ambiguous_not_correct(self):
        stance, inferred = _parse_stance({"stance": "probably fine"})
        assert stance == STANCE_AMBIGUOUS
        assert inferred is True

    def test_nothing_can_produce_incorrect_by_default(self):
        """The destructive branch must require the model to actually say so."""
        for payload in ({}, {"sufficient": False}, {"sufficient": True}, {"stance": "?"}):
            stance, _ = _parse_stance(payload)
            assert stance != STANCE_INCORRECT

    def test_the_model_cannot_smuggle_unknown_in_as_a_classification(self):
        """UNKNOWN means 'never judged'. A model claiming it would be lying."""
        stance, inferred = _parse_stance({"stance": "unknown"})
        assert stance == STANCE_AMBIGUOUS
        assert inferred is True


class TestDeterministicShortCircuitStances:
    @pytest.mark.asyncio
    async def test_casual_bar_is_correct_and_skips(self):
        from app.services.evidence_sufficiency_service import assess_evidence_sufficiency

        v = await assess_evidence_sufficiency(query="hi", rows=[], bar=_bar(BAR_CASUAL))
        assert v.stance == STANCE_CORRECT
        assert v.assessor == ASSESSOR_SKIPPED_CASUAL

    @pytest.mark.asyncio
    async def test_no_evidence_at_all_is_incorrect(self):
        """Nothing to preserve, so discarding is a no-op and escalating is right."""
        from app.services.evidence_sufficiency_service import assess_evidence_sufficiency

        v = await assess_evidence_sufficiency(query="q", rows=[], bar=_bar())
        assert v.stance == STANCE_INCORRECT
        assert v.assessor == ASSESSOR_DETERMINISTIC

    @pytest.mark.asyncio
    async def test_missing_citation_is_ambiguous_not_incorrect(self):
        """On-topic excerpts must not be destroyed over a metadata gap."""
        from app.services.evidence_sufficiency_service import assess_evidence_sufficiency

        bar = SufficiencyBar(
            name="regulatory",
            min_sources=1,
            require_citable_source=True,
            require_freshness_signal=False,
        )
        v = await assess_evidence_sufficiency(
            query="q", rows=[{"content": "relevant but unattributed"}], bar=bar
        )
        assert v.stance == STANCE_AMBIGUOUS
        assert v.should_discard_evidence is False


def test_substantive_rows_is_the_single_index_basis():
    """`keep_indices` is 0-based against this list and nothing else.

    If the assessor and the caller disagree about which rows are in scope,
    refinement keeps the wrong excerpts and the answer is built from evidence
    that was never endorsed.
    """
    rows = [{"content": "a"}, {"content": "   "}, "not a dict", {"content": "b"}, {}]
    assert substantive_rows(rows) == [{"content": "a"}, {"content": "b"}]


def test_stance_action_sets_are_coherent():
    assert DISCARD_STANCES == {STANCE_INCORRECT}
    assert DISCARD_STANCES <= ESCALATE_STANCES
    assert STANCE_CORRECT not in ESCALATE_STANCES
    # UNKNOWN must not escalate: more evidence cannot repair a broken assessor.
    assert STANCE_UNKNOWN not in ESCALATE_STANCES


# --------------------------------------------------------------------------
# Phase 2 — what the loop does about it
# --------------------------------------------------------------------------


@pytest.fixture()
def stub_sources(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    calls: dict[str, list[str]] = {"order": []}

    async def packs(**kwargs: Any):
        calls["order"].append("knowledge_pack")
        return (
            "PACKS_SECTION",
            {"fabric_hit_count": 1},
            [{"kind": "knowledge_pack", "content": "pack text"}],
        )

    async def org_rag(**kwargs: Any):
        calls["order"].append("org_rag")
        return (
            "RAG_SECTION",
            {"org_rag_chunk_count": 1},
            [{"kind": "knowledge", "content": "rag text"}],
        )

    async def internet(**kwargs: Any):
        calls["order"].append("internet")
        return (
            "WEB_SECTION",
            {"internet_hit_count": 1},
            [{"kind": "internet", "content": "web text"}],
        )

    async def graph(**kwargs: Any):
        calls["order"].append("business_graph")
        return (
            "GRAPH_SECTION",
            {"business_graph_status": "ok"},
            [{"kind": "graph", "content": "graph text"}],
        )

    monkeypatch.setattr(ctx_mod, "_retrieve_knowledge_packs", packs)
    monkeypatch.setattr(ctx_mod, "_retrieve_org_rag", org_rag)
    monkeypatch.setattr(ctx_mod, "_run_internet_prefetch", internet)
    monkeypatch.setattr(ctx_mod, "_retrieve_business_graph", graph)

    import app.services.adaptive_research_cascade as cascade

    monkeypatch.setattr(cascade, "assess_internal_retrieval_thinness", lambda **_: False)
    monkeypatch.setattr(cascade, "should_run_internet_research", lambda *a, **k: False)
    return calls


def _stances(*sequence: str, keep: list[int] | None = None) -> Any:
    """An assessor returning a scripted stance per round."""
    seq = list(sequence)
    state = {"i": 0}

    async def _assess(
        *,
        query,
        rows,
        bar,
        settings=None,
        org_id=None,
        routing_tier="multi_step",
        sources_tried=None,
    ):
        stance = seq[min(state["i"], len(seq) - 1)]
        state["i"] += 1
        return SufficiencyVerdict(
            sufficient=stance == STANCE_CORRECT,
            bar=bar,
            assessor=ASSESSOR_LLM,
            reason="scripted",
            gaps=[] if stance == STANCE_CORRECT else ["does_not_address_question"],
            confidence=0.5,
            stance=stance,
            keep_indices=list(keep or []) if stance == STANCE_CORRECT else [],
        )

    return _assess


async def _run(monkeypatch, assessor, **kwargs) -> tuple[str, dict[str, Any]]:
    import app.services.evidence_sufficiency_service as suff

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", assessor)
    return await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What are the statutory breach notification deadlines in Ontario?",
        client=object(),
        settings=_settings(**kwargs),
        classification={"department": "legal"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
    )


@pytest.mark.asyncio
async def test_discard_removes_the_rendered_sections_too(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """THE test. Dropping rows but keeping the text is not a discard.

    Every count in the audit payload would say the evidence was gone while the
    model still read it in the prompt.
    """
    block, meta = await _run(monkeypatch, _stances(STANCE_INCORRECT, STANCE_CORRECT))
    loop = meta["evidenceSufficiency"]

    assert loop["discards"] >= 1
    assert loop["discarded_rows"] >= 1
    # The round-1 evidence must be gone from the actual prompt text.
    assert "PACKS_SECTION" not in block
    assert "RAG_SECTION" not in block
    # ...and the replacement evidence must be present.
    assert "WEB_SECTION" in block


@pytest.mark.asyncio
async def test_ambiguous_keeps_the_evidence_and_adds_a_source(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """The non-destructive branch: partially useful evidence survives."""
    block, meta = await _run(monkeypatch, _stances(STANCE_AMBIGUOUS, STANCE_CORRECT))
    loop = meta["evidenceSufficiency"]

    assert loop["discards"] == 0
    assert "PACKS_SECTION" in block
    assert "WEB_SECTION" in block


@pytest.mark.asyncio
async def test_correct_on_the_first_pass_spends_no_extra_round(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    _, meta = await _run(monkeypatch, _stances(STANCE_CORRECT))
    loop = meta["evidenceSufficiency"]
    assert loop["additional_rounds_used"] == 0
    assert loop["final_stance"] == STANCE_CORRECT
    assert "internet" not in stub_sources["order"]


@pytest.mark.asyncio
async def test_refinement_keeps_only_the_load_bearing_excerpt(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """CORRECT plus a named subset must actually shrink what reaches the model."""
    block, meta = await _run(monkeypatch, _stances(STANCE_CORRECT, keep=[0]))
    loop = meta["evidenceSufficiency"]

    assert loop["refined"] is True
    assert loop["refined_from"] == 2
    assert loop["refined_to"] == 1
    assert "REFINED EVIDENCE" in block
    # Round 1 produced two rows: "pack text" then "rag text". Keeping index 0
    # must drop the second.
    assert "pack text" in block
    assert "rag text" not in block


@pytest.mark.asyncio
async def test_refinement_never_empties_the_evidence(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """Out-of-range indices must not be read as 'keep nothing'."""
    block, meta = await _run(monkeypatch, _stances(STANCE_CORRECT, keep=[99]))
    loop = meta["evidenceSufficiency"]
    assert loop["refined"] is False
    assert "pack text" in block or "PACKS_SECTION" in block


@pytest.mark.asyncio
async def test_refinement_does_not_fire_when_the_subset_is_everything(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    _, meta = await _run(monkeypatch, _stances(STANCE_CORRECT, keep=[0, 1]))
    assert meta["evidenceSufficiency"]["refined"] is False


@pytest.mark.asyncio
async def test_refinement_ignores_keep_indices_on_a_non_correct_stance(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """Refinement must be gated on the stance, not merely on keep being present.

    Mutation testing caught this as a hole: dropping the CORRECT check left the
    suite green, because today only the CORRECT branch of the parser populates
    `keep`. That makes the gate load-bearing but untested -- one future assessor
    returning `keep` alongside AMBIGUOUS would start deleting evidence nobody
    endorsed, and the tests would not notice.
    """
    import app.services.evidence_sufficiency_service as suff

    calls = {"n": 0}

    async def _ambiguous_with_keep(**kwargs):
        calls["n"] += 1
        # Deliberately malformed: a stance that does not certify, carrying a
        # refinement instruction anyway.
        return SufficiencyVerdict(
            sufficient=False,
            bar=kwargs["bar"],
            assessor=ASSESSOR_LLM,
            reason="partially useful",
            gaps=["partial_coverage"],
            stance=STANCE_AMBIGUOUS,
            keep_indices=[0],
        )

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _ambiguous_with_keep)

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
    assert calls["n"] > 0
    assert meta["evidenceSufficiency"]["refined"] is False
    assert "REFINED EVIDENCE" not in block
    # Nothing was endorsed, so nothing may be deleted.
    assert "rag text" in block or "RAG_SECTION" in block


@pytest.mark.asyncio
async def test_refinement_indexes_the_same_rows_the_assessor_was_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The index basis must be `substantive_rows`, not the raw row list.

    Mutation testing caught this too: swapping `substantive_rows(...)` for
    `list(...)` left the suite green, because every stubbed row happened to have
    content and the two lists were identical. Add one empty-content row and the
    bases diverge, at which point `keep=[1]` selects a different excerpt than
    the assessor pointed at -- and the answer gets built from evidence the
    assessor never endorsed, with the audit payload reporting a clean refinement.
    """
    import app.services.evidence_sufficiency_service as suff

    async def packs(**kwargs: Any):
        return (
            "PACKS_SECTION",
            {"fabric_hit_count": 3},
            [
                # A blank row first: present in the raw list, absent from the
                # basis the assessor was shown. This is the offset that makes the
                # two indexings disagree.
                {"kind": "knowledge_pack", "content": "   "},
                {"kind": "knowledge_pack", "content": "FIRST_REAL_EXCERPT"},
                {"kind": "knowledge_pack", "content": "SECOND_REAL_EXCERPT"},
            ],
        )

    async def _empty(**kwargs: Any):
        return ("", {}, [])

    monkeypatch.setattr(ctx_mod, "_retrieve_knowledge_packs", packs)
    monkeypatch.setattr(ctx_mod, "_retrieve_org_rag", _empty)
    monkeypatch.setattr(ctx_mod, "_run_internet_prefetch", _empty)
    monkeypatch.setattr(ctx_mod, "_retrieve_business_graph", _empty)

    import app.services.adaptive_research_cascade as cascade

    monkeypatch.setattr(cascade, "assess_internal_retrieval_thinness", lambda **_: False)
    monkeypatch.setattr(cascade, "should_run_internet_research", lambda *a, **k: False)

    async def _correct_keep_second(**kwargs):
        # Index 1 of the substantive rows == SECOND_REAL_EXCERPT.
        return SufficiencyVerdict(
            sufficient=True,
            bar=kwargs["bar"],
            assessor=ASSESSOR_LLM,
            reason="second excerpt carries it",
            stance=STANCE_CORRECT,
            keep_indices=[1],
        )

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _correct_keep_second)

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
    assert loop["refined"] is True
    assert loop["refined_from"] == 2, "blank rows must not count toward the basis"
    assert loop["refined_to"] == 1
    assert "SECOND_REAL_EXCERPT" in block
    assert "FIRST_REAL_EXCERPT" not in block


@pytest.mark.asyncio
async def test_iteration_stays_hard_bounded_across_stances(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """A stance that always escalates must still stop at the cap."""
    _, meta = await _run(monkeypatch, _stances(STANCE_INCORRECT))
    loop = meta["evidenceSufficiency"]
    assert loop["additional_rounds_used"] <= loop["max_additional_rounds"]
    assert loop["stopped_because"] in {"max_rounds_reached", "no_untried_source"}


@pytest.mark.asyncio
async def test_discarding_everything_says_so_instead_of_inviting_a_guess(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """"Answer only what the excerpts support" is wrong when there are none.

    That instruction, with an empty evidence set, is an invitation to answer from
    general knowledge while sounding sourced.
    """
    import app.services.evidence_sufficiency_service as suff

    async def _always_incorrect(**kwargs):
        return SufficiencyVerdict(
            sufficient=False,
            bar=kwargs["bar"],
            assessor=ASSESSOR_LLM,
            reason="off target",
            gaps=["does_not_address_question"],
            stance=STANCE_INCORRECT,
        )

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _always_incorrect)

    async def _empty(**kwargs: Any):
        return ("", {}, [])

    monkeypatch.setattr(ctx_mod, "_run_internet_prefetch", _empty)
    monkeypatch.setattr(ctx_mod, "_retrieve_business_graph", _empty)

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
    if block:
        assert "NO USABLE EVIDENCE" in block
        assert "do not substitute general knowledge" in block
    else:
        assert meta.get("skipped") == "no_hits"


@pytest.mark.asyncio
async def test_a_conversational_turn_pays_for_none_of_this(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """Latency tiering: the fast path must not acquire a classification step."""
    import app.services.evidence_sufficiency_service as suff

    called = {"n": 0}

    async def _counting(**kwargs):
        called["n"] += 1
        return SufficiencyVerdict(
            sufficient=True, bar=kwargs["bar"], assessor=ASSESSOR_LLM, reason="r"
        )

    monkeypatch.setattr(suff, "assess_evidence_sufficiency", _counting)

    _, meta = await ctx_mod.build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What did we agree on in the last call about the pricing change?",
        client=object(),
        settings=_settings(),
        classification={"department": "sales"},
        reasoning_depth="conversational",
    )
    assert meta["evidenceSufficiency"]["skipped"] == "casual_bar"
    assert called["n"] == 0
    assert meta["evidenceSufficiency"]["discards"] == 0


# --------------------------------------------------------------------------
# Phase 4 — composition with the existing contradiction check
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contradiction_check_sees_the_surviving_evidence_not_the_discarded(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    """Conflicts must be judged over what actually reaches the model.

    Detecting a contradiction between two excerpts, one of which was thrown out
    as off-target, invents a conflict that no longer exists and warns the user
    about it. Ordering is what prevents that, so it is held here rather than
    assumed from a code read.
    """
    import app.services.evidence_contradiction_service as conflict_mod

    seen: dict[str, Any] = {}

    async def _detect(*, query, rows, settings=None, org_id=None, routing_tier="multi_step"):
        seen["contents"] = [str(r.get("content") or "") for r in rows]
        return []

    monkeypatch.setattr(conflict_mod, "detect_contradictions", _detect)
    monkeypatch.setattr(conflict_mod, "format_contradiction_section", lambda c: "")

    # The check needs two rows of two distinct kinds. After a discard only the
    # replacement source remains, so it has to supply both on its own -- else the
    # check simply never runs and the test proves nothing.
    async def internet(**kwargs: Any):
        return (
            "WEB_SECTION",
            {"internet_hit_count": 2},
            [
                {"kind": "internet", "content": "web text"},
                {"kind": "internet_secondary", "content": "web text two"},
            ],
        )

    monkeypatch.setattr(ctx_mod, "_run_internet_prefetch", internet)

    await _run(
        monkeypatch,
        _stances(STANCE_INCORRECT, STANCE_CORRECT),
        evidence_contradiction_check_enabled=True,
    )

    assert "contents" in seen, "contradiction check did not run"
    # Round-1 evidence was discarded; it must not be in the conflict input.
    assert "pack text" not in seen["contents"]
    assert "rag text" not in seen["contents"]
    assert "web text" in seen["contents"]


@pytest.mark.asyncio
async def test_contradiction_check_sees_only_the_refined_subset(
    monkeypatch: pytest.MonkeyPatch, stub_sources
) -> None:
    import app.services.evidence_contradiction_service as conflict_mod

    seen: dict[str, Any] = {}

    async def _detect(*, query, rows, settings=None, org_id=None, routing_tier="multi_step"):
        seen["contents"] = [str(r.get("content") or "") for r in rows]
        return []

    monkeypatch.setattr(conflict_mod, "detect_contradictions", _detect)
    monkeypatch.setattr(conflict_mod, "format_contradiction_section", lambda c: "")

    _, meta = await _run(
        monkeypatch,
        _stances(STANCE_CORRECT, keep=[0]),
        evidence_contradiction_check_enabled=True,
    )

    assert meta["evidenceSufficiency"]["refined"] is True
    # Refined down to one row, so the two-distinct-kinds precondition no longer
    # holds and the check correctly does not run. Either it did not run, or it
    # ran over the refined set only -- never over the dropped excerpt.
    assert "rag text" not in seen.get("contents", [])


# --------------------------------------------------------------------------
# The audit surface — the loop must not act invisibly
# --------------------------------------------------------------------------


def test_audit_payload_carries_the_stance_and_the_actions():
    """Class C: an action nobody can query is indistinguishable from no action."""
    source = inspect.getsource(ctx_mod._emit_sufficiency_audit)
    for key in (
        "finalStance",
        "finalStanceInferred",
        "stances",
        "discards",
        "discardedRows",
        "refined",
    ):
        assert f'"{key}"' in source, f"{key} missing from the sufficiency audit payload"


def test_discard_clears_rows_and_sections_in_the_same_branch():
    """Structural guard against the two drifting apart.

    A future edit that clears `rag_source_rows` without clearing
    `evidence_sections` restores the exact defect
    `test_discard_removes_the_rendered_sections_too` exists to catch, and would
    do so in a way that keeps every audit count looking correct.
    """
    tree = ast.parse(inspect.getsource(ctx_mod.build_unified_turn_knowledge_context))
    # There is more than one `should_discard_evidence` branch: the one that
    # performs the discard, and the one that picks the advisory wording. Only the
    # former is under test here, identified by the fact that it touches the rows.
    clearing_branches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if "should_discard_evidence" not in ast.dump(node.test):
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        if "rag_source_rows" in body:
            clearing_branches.append(body)

    assert clearing_branches, (
        "no should_discard_evidence branch clears rag_source_rows; the discard is "
        "not actually happening"
    )
    for body in clearing_branches:
        assert "evidence_sections" in body, (
            "discard branch clears the rows but not the rendered sections; the "
            "discarded evidence would still reach the model while every audit "
            "count claimed it was gone"
        )
