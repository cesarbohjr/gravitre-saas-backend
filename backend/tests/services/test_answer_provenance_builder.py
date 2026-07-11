"""Wave 5 — answer provenance / calibrated uncertainty labels."""
from __future__ import annotations

from app.services.answer_provenance_builder import (
    assumption_strings,
    claim_breakdown,
    collect_claims_from_sources,
    format_assumption_prefix,
)


def test_collect_facts_from_rag_sources():
    claims = collect_claims_from_sources(
        sources=[{"source": "Platform Guide", "content": "..."}],
        tool_results=[],
    )
    assert any(c["kind"] == "fact" for c in claims)


def test_collect_inferences_from_plan():
    claims = collect_claims_from_sources(
        sources=[],
        inferred_fields=["list_id"],
        inference_sources={"list_id": "org entity cache"},
        answer_has_content=True,
    )
    assert any(c["kind"] == "inference" for c in claims)
    assert "org entity cache" in claims[0]["text"]


def test_assumption_when_ungrounded_answer():
    claims = collect_claims_from_sources(sources=[], tool_results=[], answer_has_content=True)
    assert any(c["kind"] == "assumption" for c in claims)


def test_format_assumption_prefix():
    claims = [
        {"text": "Inferred list_id from org entity cache", "kind": "inference"},
        {"text": "Parts of this answer may be model inference", "kind": "assumption"},
    ]
    prefix = format_assumption_prefix(claims)
    assert "I inferred" in prefix
    assert "Note:" in prefix


def test_claim_breakdown_and_assumption_strings():
    claims = collect_claims_from_sources(
        sources=[{"title": "Doc A"}],
        inferred_fields=["email"],
        inference_sources={"email": "session entity cache"},
    )
    breakdown = claim_breakdown(claims)
    assert breakdown["facts"]
    assert breakdown["inferences"]
    assert assumption_strings(claims)
