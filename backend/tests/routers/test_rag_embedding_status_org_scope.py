"""/rag/embedding-status counts only the caller's org's embeddings."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.rag_admin import embedding_status_route


def test_embedding_counts_are_filtered_to_caller_org() -> None:
    client = MagicMock()
    builders: list[MagicMock] = []

    def table(name):
        assert name == "rag_embeddings"
        builder = MagicMock()
        chain = builder.select.return_value
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = SimpleNamespace(count=3)
        builders.append(chain)
        return builder

    client.table.side_effect = table
    settings = SimpleNamespace(
        openai_embedding_dimension=1536,
        voyage_api_key="",
        openai_api_key="sk",
        embedding_model="text-embedding-3-small",
    )
    with (
        patch("app.routers.rag_admin.shared_service_client", return_value=client),
        patch("app.routers.rag_admin._voyage_enabled", return_value=False),
    ):
        out = embedding_status_route(({"user_id": "u-1"}, "org-1"), settings)

    assert len(builders) == 2
    for chain in builders:
        chain.eq.assert_any_call("org_id", "org-1")
    assert out["primary_provider"] == "openai"
