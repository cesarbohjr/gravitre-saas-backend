"""Wave 5 — entity resolution store unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.entity_resolution_store import (
    normalize_alias,
    org_bindings_for_candidates,
    promote_from_session,
    upsert_resolution,
)


def test_normalize_alias():
    assert normalize_alias("  MSP Prospects! ") == "msp prospects"


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


def test_promote_from_session_writes_name_alias():
    client = MagicMock()
    # Force insert path
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    written = promote_from_session(
        client,
        org_id="org-1",
        session=MagicMock(active_entities={}),
        integration="apollo",
        entity_id="list-abc",
        structured={"name": "MSP Prospects", "list_id": "list-abc"},
    )
    assert written >= 1


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
    # Without integration filter chain — handle both query shapes
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
