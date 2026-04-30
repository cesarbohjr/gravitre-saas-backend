from app.services.rag_service import RAGService


def test_rrf_merge_and_rerank():
    service = RAGService.__new__(RAGService)
    semantic = [
        {"id": "a", "content": "lead scoring workflow", "score": 0.9},
        {"id": "b", "content": "email campaign", "score": 0.8},
    ]
    keyword = [
        {"id": "b", "content": "email campaign", "score": 0.4},
        {"id": "c", "content": "inactive leads", "score": 0.4},
    ]
    merged = service._rrf_merge(semantic, keyword, top_k=3)  # noqa: SLF001
    assert len(merged) == 3
    reranked = service._rerank("inactive leads campaign", merged, top_k=2)  # noqa: SLF001
    assert len(reranked) == 2
    assert reranked[0]["id"] in {"b", "c"}
