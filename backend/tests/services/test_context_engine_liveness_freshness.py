"""Liveness (CROSS_SOURCE_CONTEXT_LIVENESS_V1) and freshness (CROSS_SOURCE_CONTEXT_FRESHNESS_V1)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.context_prioritization_engine import (
    ContextSource,
    apply_source_freshness,
    get_context_prioritization_engine,
    render_context_sources,
)
from app.services.unified_turn_knowledge_context import (
    _retrieve_org_rag,
    keep_live_document_rows,
)
from tests.context_engine.harness import ORG_A, ORG_B, FakeClient, FakeRagService

NOW = datetime.now(UTC)


def _iso(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _src(sid: str, content: str, **md) -> ContextSource:
    return ContextSource(sid, "rag", sid, 0.5, content, metadata=md)


# --- liveness ----------------------------------------------------------------


def _docs(*rows):
    return FakeClient({"rag_documents": list(rows)})


def test_rows_of_deleted_inactive_or_foreign_documents_are_dropped():
    client = _docs(
        {"id": "d1", "org_id": ORG_A, "is_active": True, "updated_at": _iso(5), "metadata": {}},
        {"id": "d2", "org_id": ORG_A, "is_active": False, "updated_at": _iso(1), "metadata": {}},
        {"id": "d4", "org_id": ORG_B, "is_active": True, "updated_at": _iso(1), "metadata": {}},
    )
    rows = [{"document_id": d, "content": d} for d in ("d1", "d2", "d3", "d4")]
    kept, meta = keep_live_document_rows(client, ORG_A, rows)
    assert [r["document_id"] for r in kept] == ["d1"]
    assert meta["org_rag_liveness_excluded"] == 3
    assert kept[0]["last_updated"] == client.tables["rag_documents"][0]["updated_at"]


def test_document_dates_from_metadata_win_and_validity_is_carried():
    client = _docs({"id": "d1", "org_id": ORG_A, "is_active": True, "updated_at": _iso(1),
                    "metadata": {"source_updated_at": _iso(40), "valid_until": _iso(-10)}})
    kept, _ = keep_live_document_rows(client, ORG_A, [{"document_id": "d1", "content": "x"}])
    assert kept[0]["last_updated"] == client.tables["rag_documents"][0]["metadata"]["source_updated_at"]
    assert kept[0]["valid_until"]


def test_liveness_fails_closed():
    class Broken:
        def table(self, _name):
            raise RuntimeError("down")

    kept, meta = keep_live_document_rows(Broken(), ORG_A, [{"document_id": "d1", "content": "x"}])
    assert kept == [] and meta["org_rag_liveness_reason"] == "read_failed"
    kept, meta = keep_live_document_rows(None, ORG_A, [{"document_id": "d1", "content": "x"}])
    assert kept == [] and meta["org_rag_liveness_reason"] == "no_client"
    kept, meta = keep_live_document_rows(_docs(), ORG_A, [{"content": "no id"}])
    assert kept == [] and meta["org_rag_liveness_reason"] == "no_document_ids"


@pytest.mark.asyncio
async def test_org_rag_uses_liveness_only_when_flagged(monkeypatch):
    from tests.context_engine.harness import TABLES

    monkeypatch.setattr("app.services.rag_service.get_rag_service", lambda: FakeRagService())
    client = FakeClient(TABLES)
    query = "How much discount can reps give without approval?"
    off = SimpleNamespace(retrieved_content_guard_enabled=True)
    section, meta, rows = await _retrieve_org_rag(org_id=ORG_A, query=query, agent=None, settings=off, client=client)
    assert "40%" in section and client.reads == []
    on = SimpleNamespace(retrieved_content_guard_enabled=True, cross_source_context_liveness_v1=True)
    section, meta, rows = await _retrieve_org_rag(org_id=ORG_A, query=query, agent=None, settings=on, client=client)
    assert "40%" not in section and meta["org_rag_liveness_excluded"] == 1
    assert client.reads == ["rag_documents"]
    assert all(r.get("document_id") and r.get("last_updated") for r in rows)


# --- freshness ---------------------------------------------------------------


def test_superseded_and_expired_sources_are_left_out():
    kept, excluded = apply_source_freshness(
        [
            _src("old", "a", superseded_at=_iso(3)),
            _src("expired", "b", valid_until=_iso(1)),
            _src("future_supersede", "c", superseded_at=_iso(-3)),
            _src("undated", "d"),
        ],
        now=NOW,
    )
    assert [s.source_id for s in kept] == ["future_supersede", "undated"]
    assert {e["reason"] for e in excluded} == {"superseded", "expired"}
    assert "freshness_as_of" not in kept[1].metadata  # undated stays untouched


def test_newer_evidence_outranks_older_with_better_retrieval_score():
    engine = get_context_prioritization_engine()
    sources = [
        ContextSource("old", "rag", "old", 0.0, "price is $50", metadata={"retrieval_score": 0.95, "last_updated": _iso(700)}),
        ContextSource("new", "rag", "new", 0.0, "price is $65", metadata={"retrieval_score": 0.80, "last_updated": _iso(20)}),
    ]
    plain = engine.build_context_profile(raw_sources=sources, classification={}, token_budget=4000)
    assert [s.source_id for s in plain.ranked_sources] == ["old", "new"]
    fresh, _ = apply_source_freshness(sources, now=NOW)
    ranked = engine.build_context_profile(raw_sources=fresh, classification={}, token_budget=4000)
    assert [s.source_id for s in ranked.ranked_sources] == ["new", "old"]
    rendered = render_context_sources(ranked.ranked_sources)
    assert 'label="new" as_of="' in rendered


def test_freshness_adjustment_is_bounded():
    fresh, _ = apply_source_freshness([_src("x", "y", last_updated=_iso(5000))], now=NOW)
    assert -0.06 <= fresh[0].metadata["freshness_adjustment"] < 0


def test_near_duplicates_only_with_the_flag():
    engine = get_context_prioritization_engine()
    base = "Support SLA: priority-one tickets get a first response within 1 hour."
    sources = [
        ContextSource("long", "rag", "kb", 0.0, base + " (Synced from HubSpot.)", metadata={"retrieval_score": 0.9}),
        ContextSource("short", "rag", "doc", 0.0, base.upper(), metadata={"retrieval_score": 0.5}),
        ContextSource("tiny", "rag", "doc2", 0.0, "within 1 hour", metadata={"retrieval_score": 0.4}),
    ]
    plain = engine.build_context_profile(raw_sources=sources, classification={}, token_budget=4000)
    assert plain.duplicate_count == 0
    near = engine.build_context_profile(raw_sources=sources, classification={}, token_budget=4000, near_duplicates=True)
    assert [s.source_id for s in near.ranked_sources] == ["long", "tiny"]  # short excerpts (< 40 chars) are kept
    assert near.excluded_sources[0] == {"id": "short", "type": "rag", "reason": "near_duplicate", "duplicateOf": "long"}


def test_render_without_freshness_metadata_is_unchanged():
    s = ContextSource("rag:1", "rag", "Doc", 0.5, "text", metadata={"as_of": "2026-01-01", "last_updated": _iso(1)})
    assert render_context_sources([s]) == (
        'ORG PRIVATE KNOWLEDGE:\n<context_source id="rag:1" type="rag" label="Doc">\nSource: Doc\ntext\n</context_source>'
    )
