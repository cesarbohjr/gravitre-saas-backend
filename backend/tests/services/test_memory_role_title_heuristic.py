"""STA-320 Option B — role/title heuristic (no embeddings)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.action_catalog.models import WorkflowFieldSpec
from app.services.entity_resolution_store import ResolutionHit
from app.services.memory_role_title_heuristic import (
    extract_role_title_cues,
    learn_role_aliases,
    match_by_role_cues,
)


def test_extract_cues_for_role_phrases():
    assert "ae" in extract_role_title_cues("the AE")
    assert "account executive" in extract_role_title_cues("Account Executive")
    assert "csm" in extract_role_title_cues("our CSM")
    assert "sales lead" in extract_role_title_cues("sales lead")
    assert "vp sales" in extract_role_title_cues("vp of sales")


def test_extract_cues_rejects_bare_person_name():
    assert extract_role_title_cues("Sarah") == []
    assert extract_role_title_cues("sarah") == []
    assert extract_role_title_cues("") == []


def test_match_unique_role_alias_binds():
    client = MagicMock()
    with patch(
        "app.services.memory_role_title_heuristic.lookup_resolutions",
        return_value=[
            ResolutionHit(
                alias_normalized="ae",
                entity_type="role",
                entity_id="gid-1",
                integration="asana",
                source="role_title_heuristic",
                confidence=0.9,
            )
        ],
    ):
        result = match_by_role_cues(
            client,
            org_id="org-1",
            integration="asana",
            cues=["ae", "account executive"],
        )
    assert result.status == "bound"
    assert result.entity_id == "gid-1"
    assert result.reason == "role_title_exact"


def test_match_two_entities_same_role_ambiguous():
    client = MagicMock()
    with patch(
        "app.services.memory_role_title_heuristic.lookup_resolutions",
        return_value=[
            ResolutionHit(
                alias_normalized="ae",
                entity_type="role",
                entity_id="gid-1",
                integration="asana",
                source="role_title_heuristic",
                confidence=0.9,
            ),
            ResolutionHit(
                alias_normalized="ae",
                entity_type="role",
                entity_id="gid-2",
                integration="asana",
                source="role_title_heuristic",
                confidence=0.8,
            ),
        ],
    ):
        result = match_by_role_cues(
            client,
            org_id="org-1",
            integration="asana",
            cues=["ae"],
        )
    assert result.status == "ambiguous"
    assert result.reason == "role_title_ambiguous"
    assert {eid for eid, _ in result.candidates} == {"gid-1", "gid-2"}
    # Clarify labels are role aliases, not person names/emails.
    assert all(label == "ae" for _eid, label in result.candidates)


def test_learn_role_aliases_upserts_role_entity_type():
    client = MagicMock()
    with patch(
        "app.services.memory_role_title_heuristic.upsert_resolution",
        return_value=True,
    ) as upsert:
        n = learn_role_aliases(
            client,
            org_id="org-1",
            integration="asana",
            entity_id="gid-1",
            mention="the AE",
        )
    assert n >= 1
    for call in upsert.call_args_list:
        assert call.kwargs["entity_type"] == "role"
        assert call.kwargs["entity_id"] == "gid-1"
        assert call.kwargs["source"] == "role_title_heuristic"


def test_learn_skips_bare_name():
    with patch(
        "app.services.memory_role_title_heuristic.upsert_resolution",
        return_value=True,
    ) as upsert:
        n = learn_role_aliases(
            MagicMock(),
            org_id="org-1",
            integration="asana",
            entity_id="gid-1",
            mention="Sarah",
        )
    assert n == 0
    upsert.assert_not_called()


@pytest.mark.asyncio
async def test_resolver_role_bind_with_memory_opt_in_off():
    """STA-320: exact+role run without Memory opt-in; no embed/search calls."""
    from app.services.memory_field_resolver import resolve_sensitive_field_mention

    client = MagicMock()
    # settings load for Memory path should not be reached when role binds.
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[{"settings": {}}])
    )
    field = WorkflowFieldSpec("Assignee", ("assignee_hint", "assignee"), sensitive=True)
    settings = SimpleNamespace(
        disable_ai=False, openai_api_key="sk-test", supabase_jwt_secret="sec"
    )

    with (
        patch(
            "app.services.memory_field_resolver.lookup_resolutions",
            return_value=[],
        ),
        patch(
            "app.services.memory_field_resolver.match_by_role_cues",
            return_value=SimpleNamespace(
                status="bound",
                entity_id="gid-ae",
                candidates=(("gid-ae", "ae"),),
                reason="role_title_exact",
            ),
        ) as role_match,
        patch(
            "app.services.memory_field_resolver.search_memory_by_mention",
            new_callable=MagicMock,
        ) as search,
        patch(
            "app.services.memory_field_resolver.load_memory_entity_embeddings_settings",
        ) as load_policy,
    ):
        result = await resolve_sensitive_field_mention(
            client=client,
            settings=settings,
            org_id="org-1",
            integration="asana",
            field=field,
            mention="the AE",
            entity_type="employee",
        )
        assert result.status == "bound"
        assert result.entity_id == "gid-ae"
        assert result.reason == "role_title_exact"
        role_match.assert_called_once()
        search.assert_not_called()
        load_policy.assert_not_called()


@pytest.mark.asyncio
async def test_resolver_bare_name_misses_without_memory_opt_in():
    """Bare names do not silent-guess via role heuristic when Memory is off."""
    from app.services.memory_field_resolver import resolve_sensitive_field_mention

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[{"settings": {}}])
    )
    field = WorkflowFieldSpec("Assignee", ("assignee_hint", "assignee"), sensitive=True)
    settings = SimpleNamespace(
        disable_ai=False, openai_api_key="sk-test", supabase_jwt_secret="sec"
    )

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
