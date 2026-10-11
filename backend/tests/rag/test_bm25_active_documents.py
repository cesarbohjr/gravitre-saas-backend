"""Phase 1: the BM25/FTS arm only sees chunks of active document versions (like vector rag_search)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.rag import retrieval as rag_retrieval


class _Builder:
    def __init__(self, calls: list[tuple], rows: list[dict]):
        self.calls = calls
        self.rows = rows

    def __getattr__(self, name: str):
        def _call(*a: Any, **k: Any):
            self.calls.append((name, a))
            return self

        return _call

    def execute(self):
        return SimpleNamespace(data=list(self.rows))


class _Client:
    def __init__(self, rows: list[dict]):
        self.chunk_calls: list[tuple] = []
        self.rows = rows

    def table(self, name: str):
        if name == "rag_documents":
            return _Builder([], [{"id": "d-active", "title": "Current"}])
        return _Builder(self.chunk_calls, self.rows)


@pytest.mark.parametrize("query_text", ["payroll policy", ""])
def test_keyword_arm_filters_to_active_documents(monkeypatch, query_text):
    rows = [
        {"id": "c1", "content": "payroll policy v2", "document_id": "d-active", "rag_documents": {"is_active": True}},
        {"id": "c0", "content": "payroll policy v1", "document_id": "d-old", "rag_documents": {"is_active": False}},
    ]
    client = _Client(rows)
    monkeypatch.setattr(rag_retrieval, "create_client", lambda *a, **k: client)
    monkeypatch.setattr(rag_retrieval, "_resolve_source_ids_for_scope", lambda *a, **k: None)

    out, _reach = rag_retrieval.fetch_bm25_corpus(
        SimpleNamespace(supabase_url="u", supabase_service_role_key="k"), "org-1", query_text=query_text
    )

    select = next(a for name, a in client.chunk_calls if name == "select")
    assert "rag_documents!inner(is_active)" in select[0]
    assert ("eq", ("rag_documents.is_active", True)) in client.chunk_calls
    assert [r["id"] for r in out] == ["c1"]
