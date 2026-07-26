"""Fuzzy entity resolution in sensitive-field mention resolver."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.action_catalog.models import WorkflowFieldSpec
from app.services.entity_resolution_store import ResolutionHit
from app.services.memory_field_resolver import resolve_sensitive_field_mention


@pytest.mark.asyncio
async def test_fuzzy_first_name_binds_when_exact_misses(mock_settings):
    client = MagicMock()
    field = WorkflowFieldSpec(
        label="Assignee",
        arg_keys=("assignee_id",),
        sensitive=True,
        inferrable=True,
    )
    fuzzy_hit = ResolutionHit(
        alias_normalized="sarah smith",
        entity_type="contact",
        entity_id="contact-42",
        integration="hubspot",
        source="tool_output_first_name",
        confidence=0.78,
    )

    with patch(
        "app.services.memory_field_resolver.lookup_resolutions",
        return_value=[],
    ), patch(
        "app.services.memory_field_resolver.lookup_fuzzy_resolutions",
        return_value=[fuzzy_hit],
    ), patch(
        "app.services.memory_field_resolver.search_memory_by_mention",
        new_callable=AsyncMock,
    ):
        result = await resolve_sensitive_field_mention(
            client=client,
            settings=mock_settings,
            org_id="org-1",
            integration="hubspot",
            field=field,
            mention="Sarah",
            entity_type="contact",
        )

    assert result.status == "bound"
    assert result.entity_id == "contact-42"
    assert result.reason == "entity_resolution_fuzzy"
