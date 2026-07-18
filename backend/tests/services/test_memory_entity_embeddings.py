"""STA-316 — Memory Option B: opaque tokens, opt-in, WorkflowFieldSpec resolver."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.action_catalog.models import WorkflowFieldSpec
from app.services.memory_entity_embeddings_settings import (
    DEFAULT_MEMORY_ENTITY_EMBEDDINGS,
    memory_embeddings_enabled_for,
    normalize_memory_entity_embeddings,
)
from app.services.memory_opaque_tokens import (
    MemoryOpaqueTokenError,
    assert_provider_safe_token,
    looks_like_raw_pii,
    opaque_alias_token,
    opaque_entity_token,
    redact_mention_for_digest,
)


def test_default_opt_in_is_off():
    assert DEFAULT_MEMORY_ENTITY_EMBEDDINGS["enabled"] is False
    normalized = normalize_memory_entity_embeddings(None)
    assert normalized["enabled"] is False
    assert memory_embeddings_enabled_for(normalized, integration="asana") is False


def test_enabled_requires_explicit_true():
    assert normalize_memory_entity_embeddings({"enabled": "yes"})["enabled"] is False
    assert normalize_memory_entity_embeddings({"enabled": True})["enabled"] is True


def test_connector_allowlist():
    policy = normalize_memory_entity_embeddings(
        {"enabled": True, "connectors": ["asana", "slack"]}
    )
    assert memory_embeddings_enabled_for(policy, integration="asana") is True
    assert memory_embeddings_enabled_for(policy, integration="hubspot") is False


def test_opaque_tokens_are_provider_safe():
    token = opaque_entity_token(
        org_id="org-1",
        entity_type="employee",
        entity_id="123",
        secret="test-secret",
    )
    assert token.startswith("mem:v1:")
    assert assert_provider_safe_token(token) == token
    assert looks_like_raw_pii(token) is False


def test_alias_token_never_contains_raw_pii():
    alias = redact_mention_for_digest("Sarah smith sarah@acme.com")
    assert "@" not in alias
    token = opaque_alias_token(org_id="org-1", alias_normalized=alias, secret="test-secret")
    assert token.startswith("mem:alias:v1:")
    assert "sarah" not in token
    assert "@" not in token


def test_assert_provider_safe_rejects_raw_email_and_names():
    with pytest.raises(MemoryOpaqueTokenError):
        assert_provider_safe_token("sarah@acme.com")
    with pytest.raises(MemoryOpaqueTokenError):
        assert_provider_safe_token("Sarah Smith")
    with pytest.raises(MemoryOpaqueTokenError):
        assert_provider_safe_token("mem:v1:not-a-hex-digest")


@pytest.mark.asyncio
async def test_resolver_skips_memory_when_org_opt_in_off():
    """Memory opaque path stays gated; exact+role still run (STA-320)."""
    from app.services.memory_field_resolver import resolve_sensitive_field_mention

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[{"settings": {}}]
    )
    field = WorkflowFieldSpec("Assignee", ("assignee_hint", "assignee"), sensitive=True)
    settings = SimpleNamespace(disable_ai=False, openai_api_key="sk-test", supabase_jwt_secret="sec")

    with (
        patch(
            "app.services.memory_field_resolver.lookup_resolutions",
            return_value=[],
        ),
        patch(
            "app.services.memory_field_resolver.search_memory_by_mention",
            new_callable=MagicMock,
        ) as search,
    ):
        result = await resolve_sensitive_field_mention(
            client=client,
            settings=settings,
            org_id="org-1",
            integration="asana",
            field=field,
            mention="Sarah",
            entity_type="employee",
        )
        assert result.status == "miss"
        assert result.reason == "memory_opt_in_off"
        search.assert_not_called()


@pytest.mark.asyncio
async def test_resolver_skips_non_sensitive_field():
    from app.services.memory_field_resolver import resolve_sensitive_field_mention

    field = WorkflowFieldSpec("project", ("project",), sensitive=False)
    result = await resolve_sensitive_field_mention(
        client=MagicMock(),
        settings=SimpleNamespace(disable_ai=False),
        org_id="org-1",
        integration="asana",
        field=field,
        mention="Sarah",
    )
    assert result.status == "skipped"
    assert result.reason == "field_not_sensitive"


@pytest.mark.asyncio
async def test_embed_opaque_token_never_calls_provider_with_raw_pii():
    from app.services.memory_entity_embeddings_service import embed_opaque_token

    settings = SimpleNamespace(openai_api_key="sk-test")
    with patch(
        "app.services.providers.openai_adapter.OpenAIAdapter.embed",
        return_value=[0.0] * 1536,
    ) as embed_mock:
        with pytest.raises(MemoryOpaqueTokenError):
            embed_opaque_token("sarah@acme.com", settings)
        embed_mock.assert_not_called()

        with pytest.raises(MemoryOpaqueTokenError):
            embed_opaque_token("Sarah Smith", settings)
        embed_mock.assert_not_called()


@pytest.mark.asyncio
async def test_embed_opaque_token_accepts_opaque_only():
    from app.services.memory_entity_embeddings_service import embed_opaque_token
    from app.services.memory_opaque_tokens import opaque_alias_token

    settings = SimpleNamespace(openai_api_key="sk-test")
    token = opaque_alias_token(org_id="org-1", alias_normalized="sarah", secret="sec")
    with (
        patch(
            "app.services.providers.openai_adapter.OpenAIAdapter.embed",
            return_value=[0.1] * 1536,
        ) as embed_mock,
        patch("app.rag.embedding.record_embedding_cost"),
    ):
        vector = embed_opaque_token(token, settings, org_id="org-1")
        assert len(vector) == 1536
        embed_mock.assert_called_once()
        sent = embed_mock.call_args.args[0] if embed_mock.call_args.args else embed_mock.call_args.kwargs.get("text")
        # First positional after self is text
        if embed_mock.call_args.args:
            sent = embed_mock.call_args.args[0]
        else:
            sent = embed_mock.call_args.kwargs.get("text")
        assert str(sent).startswith("mem:")
        assert "sarah" not in str(sent).lower() or str(sent).startswith("mem:")
