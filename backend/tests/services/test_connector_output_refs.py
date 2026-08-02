"""Connector output refs — open completed work from step snapshots."""
from __future__ import annotations

from app.services.connector_output_refs import (
    collect_connector_output_refs,
    enrich_invoke_tool_snapshot,
    extract_step_output_ref,
    primary_vendor_url,
)


def test_extract_prefers_nested_output_snapshot_external_url():
    ref = extract_step_output_ref(
        {
            "step_name": "Create Apollo list",
            "status": "completed",
            "output_snapshot": {
                "invoke_action": "apollo.lists.create",
                "summary": "Created list MSP Prospects",
                "external_url": "https://app.apollo.io/#/lists/abc",
                "list_id": "abc",
                "outcome_effect": "created",
                "success": True,
            },
        }
    )
    assert ref is not None
    assert ref["external_url"] == "https://app.apollo.io/#/lists/abc"
    assert ref["invoke_action"] == "apollo.lists.create"
    assert ref["entity_id"] == "abc"


def test_collect_and_primary_vendor_url():
    refs = collect_connector_output_refs(
        [
            {
                "name": "Search",
                "status": "completed",
                "output_snapshot": {"summary": "found 3", "invoke_action": "apollo.people.search"},
            },
            {
                "name": "HubSpot list",
                "status": "completed",
                "output_snapshot": {
                    "invoke_action": "hubspot.lists.create",
                    "result_url": "https://app.hubspot.com/contacts/123/lists/9",
                    "outcome_effect": "created",
                },
            },
        ]
    )
    assert len(refs) == 2
    assert primary_vendor_url(refs) == "https://app.hubspot.com/contacts/123/lists/9"


def test_enrich_invoke_tool_snapshot_stamps_effect_and_integration():
    enriched = enrich_invoke_tool_snapshot(
        action="apollo.lists.create",
        data={
            "already_existed": True,
            "label": {"id": "6a4d"},
            "message": "Found existing contact list",
            "result_url": "https://app.apollo.io/#/lists/6a4d",
        },
        success=True,
    )
    assert enriched["integration"] == "apollo"
    assert enriched["invoke_action"] == "apollo.lists.create"
    assert enriched["external_url"] == "https://app.apollo.io/#/lists/6a4d"
    assert enriched["outcome_effect"] == "already_existed"
    assert enriched["already_existed"] is True
