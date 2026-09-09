"""Regression: org RAG source type accepted for agent assignments."""
from app.services.knowledge_source_types import validate_source_type


def test_rag_source_type_is_valid() -> None:
    assert validate_source_type("rag_source") == "rag_source"
