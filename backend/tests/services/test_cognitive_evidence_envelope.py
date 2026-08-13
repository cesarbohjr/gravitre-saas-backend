"""Unit tests for uniform cognitive evidence envelope (Phase D item 6)."""
from __future__ import annotations

from app.services.cognitive_evidence_envelope import (
    attach_evidence_envelope,
    build_evidence_envelope,
)
from app.knowledge_fabric.temporal import (
    attach_temporal_aliases,
    document_is_currently_valid,
    resolve_temporal_fields,
)


def test_build_evidence_envelope_basic():
    env = build_evidence_envelope(
        recommendation="Do X",
        why="Because Y",
        sources=[{"citation": "NIST SP 800-53", "score": 0.9}],
        confidence=0.71,
        confidence_source="heuristic",
        confidence_is_estimate=True,
    )
    assert env["recommendation"] == "Do X"
    assert env["why"] == "Because Y"
    assert env["sources"][0]["citation"] == "NIST SP 800-53"
    assert env["confidence"] == 0.71
    assert env["confidence_is_estimate"] is True
    assert env["evidence_schema"] == "cognitive_evidence_v1"


def test_build_evidence_envelope_insufficient_confidence():
    env = build_evidence_envelope(recommendation="Hello", confidence=None)
    assert env["confidence"] is None
    assert env["confidence_source"] == "insufficient_data"


def test_attach_evidence_envelope_from_payload():
    out = attach_evidence_envelope(
        {
            "message": "Ship it",
            "answer_explanation": "LIVE path",
            "confidence": {"score": 0.4, "confidence_source": "heuristic"},
            "sources": ["doc-a"],
        }
    )
    assert "evidence" in out
    assert out["evidence"]["recommendation"] == "Ship it"
    assert out["evidence"]["why"] == "LIVE path"
    assert out["evidence"]["confidence"] == 0.4


def test_temporal_aliases_resolve_from_proposal_names():
    resolved = resolve_temporal_fields(
        valid_from="2024-01-01T00:00:00Z",
        valid_until="2025-01-01T00:00:00Z",
        superseded_by="doc-2",
    )
    assert resolved["effective_at"] == "2024-01-01T00:00:00Z"
    assert resolved["superseded_at"] == "2025-01-01T00:00:00Z"
    assert resolved["valid_from"] == "2024-01-01T00:00:00Z"
    assert resolved["valid_until"] == "2025-01-01T00:00:00Z"
    assert resolved["superseded_by"] == "doc-2"


def test_document_is_currently_valid_respects_valid_until():
    doc = attach_temporal_aliases(
        {
            "effective_at": "2020-01-01T00:00:00Z",
            "superseded_at": "2020-06-01T00:00:00Z",
        }
    )
    assert document_is_currently_valid(doc, now_iso="2024-01-01T00:00:00Z") is False
    assert document_is_currently_valid(doc, now_iso="2020-01-02T00:00:00Z") is True
