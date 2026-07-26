"""Wave 5 — entity resolution store unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.entity_resolution_store import (
    _fuzzy_alias_matches,
    first_name_aliases,
    lookup_fuzzy_resolutions,
    normalize_alias,
    org_bindings_for_candidates,
    promote_from_session,
    upsert_resolution,
)


def test_normalize_alias():
    assert normalize_alias("  MSP Prospects! ") == "msp prospects"


def test_fuzzy_alias_matches_first_name():
    assert _fuzzy_alias_matches(["sarah"], "sarah smith") is True
    assert _fuzzy_alias_matches(["sarah"], "sarah") is False
    assert _fuzzy_alias_matches(["sarah", "smith"], "sarah smith") is False


def test_first_name_aliases():
    assert first_name_aliases("Sarah Smith") == ["sarah"]
    assert first_name_aliases("Sarah") == []


def test_upsert_inserts_when_missing():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    ok = upsert_resolution(
        client,
        org_id="org-1",
        alias="MSP Prospects",
        entity_type="list",
        entity_id="list-123",
        integration="apollo",
        source="tool_output",
        confidence=0.9,
    )
    assert ok is True
    client.table.return_value.insert.assert_called()


def test_upsert_updates_when_present():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "row-1", "evidence_count": 2, "confidence": 0.5}]
    )
    ok = upsert_resolution(
        client,
        org_id="org-1",
        alias="MSP Prospects",
        entity_type="list",
        entity_id="list-123",
        integration="apollo",
    )
    assert ok is True
    client.table.return_value.update.assert_called()


def test_promote_from_session_writes_name_and_first_name_aliases():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    written = promote_from_session(
        client,
        org_id="org-1",
        session=MagicMock(active_entities={}),
        integration="hubspot",
        entity_id="contact-abc",
        structured={"name": "Sarah Smith", "contact_id": "contact-abc"},
    )
    assert written >= 2
    insert_calls = client.table.return_value.insert.call_args_list
    aliases = {call.args[0]["alias_normalized"] for call in insert_calls}
    assert "sarah smith" in aliases
    assert "sarah" in aliases


def test_lookup_fuzzy_resolutions_filters_non_matches():
    client = MagicMock()
    rows = MagicMock(
        data=[
            {
                "alias_normalized": "sarah smith",
                "entity_type": "contact",
                "entity_id": "contact-1",
                "integration": "hubspot",
                "source": "tool_output_first_name",
                "confidence": 0.78,
            },
            {
                "alias_normalized": "sandra lee",
                "entity_type": "contact",
                "entity_id": "contact-2",
                "integration": "hubspot",
                "source": "tool_output",
                "confidence": 0.9,
            },
        ]
    )
    limit_chain = MagicMock()
    limit_chain.eq.return_value.execute.return_value = rows
    client.table.return_value.select.return_value.eq.return_value.or_.return_value.order.return_value.limit.return_value = (
        limit_chain
    )
    hits = lookup_fuzzy_resolutions(client, "org-1", "Sarah", integration="hubspot")
    assert len(hits) == 1
    assert hits[0].entity_id == "contact-1"


def test_org_bindings_for_candidates():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {
                "alias_normalized": "msp prospects",
                "entity_type": "list",
                "entity_id": "list-abc",
                "integration": "apollo",
                "source": "tool_output",
                "confidence": 0.9,
            }
        ]
    )
    client.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "alias_normalized": "msp prospects",
                "entity_type": "list",
                "entity_id": "list-abc",
                "integration": "apollo",
                "source": "tool_output",
                "confidence": 0.9,
            }
        ]
    )
    bindings = org_bindings_for_candidates(
        client,
        "org-1",
        integration="apollo",
        candidates_by_arg={"list_id": ("list_id",)},
        hint_aliases=["MSP Prospects"],
    )
    assert bindings.get("list_id") == ("list-abc", "org entity cache")
