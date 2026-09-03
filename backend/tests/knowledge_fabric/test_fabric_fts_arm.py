"""Guards for the Knowledge Fabric keyword arm.

The keyword half of hybrid retrieval was dormant in production from the day it
was written. Three defects were stacked in one call, and the suite had 71 green
tests over this module the whole time, because every one of them used a mock
client that happily accepts any keyword argument. A mock that cannot reproduce
the real signature cannot prove a real call site -- Class B, the broken
instrument, applied to the test double itself.

These tests therefore assert against the *real* postgrest builder contract
rather than a permissive stand-in.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.knowledge_fabric import retrieval as retrieval_mod
from app.knowledge_fabric.retrieval import (
    FTS_NO_TERMS,
    FTS_OPTIONS,
    build_fts_query,
)

SOURCE = Path(retrieval_mod.__file__).read_text(encoding="utf-8")


def test_fts_options_match_the_real_postgrest_signature():
    """`text_search` takes a positional options dict, not a `config=` kwarg.

    The shipped call passed `config="english"`, which raised TypeError on every
    single invocation and was swallowed by a broad except.
    """
    from postgrest import SyncSelectRequestBuilder

    params = inspect.signature(SyncSelectRequestBuilder.text_search).parameters
    assert "config" not in params, (
        "postgrest grew a `config` kwarg; re-check the call site before relaxing this"
    )
    assert "options" in params


def test_call_site_passes_options_positionally_and_no_config_kwarg():
    """The guard for the actual shipped defect.

    Checking the postgrest signature alone is not enough: mutation testing showed
    that reinstating `config="english"` at the call site left the suite green,
    because no test looked at the call site. The one defect that really shipped
    was the one the guards did not cover.
    """
    tree = ast.parse(SOURCE)
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "text_search"
    ]
    assert calls, "no text_search call found — did the keyword arm get removed?"
    for node in calls:
        kwargs = {kw.arg for kw in node.keywords}
        assert "config" not in kwargs, (
            "text_search() takes no `config=` kwarg; this raises TypeError on every "
            "call and the surrounding except swallows it"
        )
        assert not kwargs, f"unexpected kwargs on text_search: {sorted(kwargs)}"
        assert len(node.args) == 3, (
            "text_search must be called as (column, query, options) with options "
            f"positional; got {len(node.args)} positional args"
        )


def test_fts_option_type_key_is_the_literal_the_builder_matches():
    """"websearch" is silently ignored; only "web_search" selects websearch_to_tsquery.

    A near-miss here does not raise. It falls through to a bare `fts`, which then
    hands the raw sentence to tsquery and fails on any multi-word query.
    """
    assert FTS_OPTIONS["type"] == "web_search"
    assert FTS_OPTIONS["config"] == "english"


def test_text_search_result_has_no_limit_so_limit_must_come_first():
    """Ordering guard: `.limit()` after `.text_search()` raises AttributeError."""
    from postgrest import SyncQueryRequestBuilder

    assert not hasattr(SyncQueryRequestBuilder, "limit")

    tree = ast.parse(SOURCE)
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "text_search"):
            continue
        found = True
        # Walk inward from .text_search(...) and require .limit() to appear
        # somewhere in the chain it is built on.
        inner = node.func.value
        chain: list[str] = []
        while isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
            chain.append(inner.func.attr)
            inner = inner.func.value
        assert "limit" in chain, (
            "`.limit()` must be applied before `.text_search()`; text_search returns "
            f"a builder with no .limit(). Chain seen: {chain}"
        )
    assert found, "no text_search call found — did the keyword arm get removed?"


@pytest.mark.parametrize(
    "query,expected_terms",
    [
        ("data retention requirements", ["data", "retention", "requirements"]),
        ("What are the breach notification deadlines?", ["breach", "notification", "deadlines"]),
    ],
)
def test_build_fts_query_ors_content_terms(query, expected_terms):
    """ANDed sentences matched 0 rows on the real corpus; ORed terms matched."""
    built = build_fts_query(query)
    assert " OR " in built
    for term in expected_terms:
        assert f'"{term}"' in built


def test_build_fts_query_drops_interrogatives():
    assert "what" not in build_fts_query("What is data retention?").lower()


def test_build_fts_query_returns_empty_when_nothing_usable_survives():
    """Empty is a third state, not a search that found nothing."""
    assert build_fts_query("What is the?") == ""
    assert build_fts_query("") == ""


def test_no_terms_is_distinct_from_ok_and_from_failed():
    """Class C: 'did not run' must never serialise the same as 'ran, found none'."""
    from app.knowledge_fabric.retrieval import FTS_FAILED, FTS_NOT_RUN, FTS_OK

    assert len({FTS_OK, FTS_NOT_RUN, FTS_FAILED, FTS_NO_TERMS}) == 4


def test_fts_failure_is_logged_with_the_cause_in_the_message():
    """The old line put the reason in `extra=`, which the formatter drops.

    Production printed `knowledge_fabric.fts_unavailable` with no cause attached
    on every turn for months.
    """
    tree = ast.parse(SOURCE)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)):
            continue
        if func.value.id != "logger":
            continue
        first = node.args[0] if node.args else None
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if "fts_unavailable" not in first.value and "vector_failed" not in first.value:
            continue
        assert func.attr == "warning", (
            f"{first.value} must log at warning; a dormant retrieval half is not INFO"
        )
        assert "%s" in first.value, (
            f"{first.value} must interpolate the cause into the message; "
            "`extra=` is not rendered by this formatter"
        )
        assert len(node.args) > 1, f"{first.value} logs no cause at all"


class TestHybridFusion:
    """The keyword arm running is not the same as the keyword arm counting.

    Fixing the three call defects made `fts=ok` while `retrieve_fts_matches`
    stayed 0 end-to-end: keyword hits entered the pool and were then thrown away
    by a dedup that kept whichever copy scored higher. Vector cosines sit well
    above the flat 0.55 a keyword hit carries, so agreement between the two arms
    -- the entire point of hybrid retrieval -- was discarded on every chunk.
    """

    @staticmethod
    def _fts(cid: str) -> dict:
        return {"id": cid, "match": "fts", "semantic_score": 0.55, "content": cid}

    @staticmethod
    def _vec(cid: str, score: float) -> dict:
        return {"id": cid, "match": "vector", "semantic_score": score, "content": cid}

    def test_co_matched_chunk_outranks_an_equal_vector_only_chunk(self):
        """The regression that mattered: agreement used to be worth nothing."""
        from app.knowledge_fabric.retrieval import fuse_hybrid_candidates

        fused = {
            r["id"]: r
            for r in fuse_hybrid_candidates(
                [self._vec("both", 0.80), self._fts("both"), self._vec("solo", 0.80)]
            )
        }
        assert fused["both"]["semantic_score"] > fused["solo"]["semantic_score"]
        assert fused["both"]["match"] == "hybrid"
        assert fused["solo"]["match"] == "vector"

    def test_vector_only_scores_are_untouched(self):
        """Conservative by design: only co-matched chunks may move."""
        from app.knowledge_fabric.retrieval import fuse_hybrid_candidates

        [row] = fuse_hybrid_candidates([self._vec("a", 0.83)])
        assert row["semantic_score"] == pytest.approx(0.83)

    def test_keyword_only_chunk_survives_as_recall(self):
        """A chunk the vector arm missed entirely must still reach the pool."""
        from app.knowledge_fabric.retrieval import FTS_ONLY_SCORE, fuse_hybrid_candidates

        [row] = fuse_hybrid_candidates([self._fts("kw")])
        assert row["semantic_score"] == pytest.approx(FTS_ONLY_SCORE)
        assert row["match"] == "fts"

    def test_matched_by_records_both_arms(self):
        from app.knowledge_fabric.retrieval import fuse_hybrid_candidates

        [row] = fuse_hybrid_candidates([self._vec("x", 0.6), self._fts("x")])
        assert row["matched_by"] == ["fts", "vector"]

    def test_fused_score_is_capped_at_one(self):
        from app.knowledge_fabric.retrieval import fuse_hybrid_candidates

        [row] = fuse_hybrid_candidates([self._vec("x", 0.99), self._fts("x")])
        assert row["semantic_score"] <= 1.0

    def test_fusion_is_not_rrf_because_the_keyword_arm_is_unranked(self):
        """Guard against a future 'upgrade' to RRF over an arbitrary row order.

        postgrest cannot order by ts_rank, so keyword rows arrive unordered.
        RRF over that order would manufacture a precision signal that does not
        exist. Reordering the keyword rows must therefore change nothing.
        """
        from app.knowledge_fabric.retrieval import fuse_hybrid_candidates

        forward = fuse_hybrid_candidates(
            [self._fts("a"), self._fts("b"), self._fts("c"), self._vec("a", 0.7)]
        )
        reverse = fuse_hybrid_candidates(
            [self._fts("c"), self._fts("b"), self._fts("a"), self._vec("a", 0.7)]
        )
        assert {r["id"]: r["semantic_score"] for r in forward} == {
            r["id"]: r["semantic_score"] for r in reverse
        }


def test_retrieval_health_is_reported_on_every_return_path():
    """A caller must never have to infer whether hybrid search actually ran."""
    tree = ast.parse(SOURCE)
    func = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "retrieve_knowledge_fabric"
    )
    returns = [n for n in ast.walk(func) if isinstance(n, ast.Return) and n.value is not None]
    assert returns
    for node in returns:
        rendered = ast.dump(node)
        assert "retrieval_health" in rendered or "_UNREACHED_HEALTH" in rendered, (
            "every return from retrieve_knowledge_fabric must carry retrieval_health"
        )
