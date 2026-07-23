"""Embedding tool retrieval for task-shaped unified turns."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.unified_turn_tool_retrieval import (
    embed_narrow_tools_for_turn,
    is_task_shaped_for_retrieval,
    warm_tool_document_embeddings,
)


def _tool(name: str, desc: str, write: bool = False) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": {}},
        },
        "capability_tier": "write" if write else "read",
        "requires_approval": write,
    }


def test_is_task_shaped_for_retrieval_social_vs_task():
    use_embed, label, _q = is_task_shaped_for_retrieval("Hey")
    assert use_embed is False
    assert label == "conversational"

    use_embed, label, q = is_task_shaped_for_retrieval(
        "Create an Apollo contact list named Demo"
    )
    assert use_embed is True
    assert label == "task_shaped"
    assert "Apollo" in q or "apollo" in q.lower() or "list" in q.lower()

    use_embed, label, q = is_task_shaped_for_retrieval(
        "hey — also create an Apollo contact list named X"
    )
    assert use_embed is True
    assert label == "mixed"
    assert "create" in q.lower() or "Apollo" in q or "apollo" in q.lower()


def test_embed_narrow_ranks_relevant_tools():
    tools = [
        _tool("assistant_connector_status", "Platform connector status"),
        _tool("apollo_lists_create", "Create a contact list in Apollo", write=True),
        _tool("apollo_people_search", "Search people in Apollo"),
        _tool("slack_post_message", "Post a message to Slack", write=True),
        _tool("gmail_messages_send", "Send an email via Gmail", write=True),
    ]

    def fake_embed(text, settings, org_id=None):
        t = (text or "").lower()
        if "create an apollo contact list" in t:
            return [1.0, 0.0, 0.0]
        if "apollo_lists_create" in t or "create a contact list in apollo" in t:
            return [0.98, 0.05, 0.0]
        if "apollo_people_search" in t or "search people in apollo" in t:
            return [0.55, 0.4, 0.0]
        if "slack" in t:
            return [0.0, 1.0, 0.0]
        if "gmail" in t:
            return [0.0, 0.0, 1.0]
        return [0.05, 0.05, 0.05]

    settings = MagicMock(embedding_model="text-embedding-3-small")
    with patch.dict("app.services.unified_turn_tool_retrieval._TOOL_EMBED_CACHE", {}, clear=True), patch(
        "app.rag.embedding.get_embedding",
        side_effect=fake_embed,
    ):
        # Clear module cache explicitly
        from app.services import unified_turn_tool_retrieval as mod

        mod._TOOL_EMBED_CACHE.clear()
        visible, stats = embed_narrow_tools_for_turn(
            tools,
            query="Create an Apollo contact list named Demo",
            settings=settings,
            org_id="org",
            connected_integrations=["apollo", "slack", "gmail"],
            requires_action=True,
            max_tools=8,
        )
    names = {row["function"]["name"] for row in visible}
    assert stats["embeddingToolRetrieval"] is True
    assert stats["retrievalMethod"] == "embedding_narrow_tools_for_turn"
    assert "apollo_lists_create" in names
    assert "slack_post_message" not in names


def test_embed_narrow_falls_back_to_keyword_on_error():
    tools = [
        _tool("apollo_lists_create", "Create a contact list in Apollo", write=True),
        _tool("gmail_messages_send", "Send an email via Gmail", write=True),
    ]
    settings = MagicMock(embedding_model="text-embedding-3-small")
    with patch(
        "app.rag.embedding.get_embedding",
        side_effect=RuntimeError("no provider"),
    ):
        visible, stats = embed_narrow_tools_for_turn(
            tools,
            query="Create an Apollo contact list named Demo",
            settings=settings,
            connected_integrations=["apollo", "gmail"],
            requires_action=True,
            max_tools=8,
        )
    assert stats.get("embeddingToolRetrieval") is False
    assert stats.get("retrievalMethod") == "keyword_narrow_tools_for_turn"
    assert stats.get("embeddingFallbackReason")
    assert any(t["function"]["name"] == "apollo_lists_create" for t in visible)


def test_warm_tool_document_embeddings_noop_when_disabled():
    settings = MagicMock(unified_turn_embedding_tool_retrieval=False, openai_api_key="sk-test")
    assert warm_tool_document_embeddings(settings=settings) == 0
