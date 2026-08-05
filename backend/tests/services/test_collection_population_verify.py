"""F5/F6 unit coverage — pack install gate + population verify."""
from __future__ import annotations

from unittest.mock import patch

from app.services.collection_population_verify import (
    apply_population_verify_to_status,
    verify_collection_population,
)
from app.services.retrieve_plan_gate import retrieve_plan_or_none


MSP_TRY = (
    'Use Clay to enrich the existing Apollo contact list "MSP Prospects", '
    'then add those enriched contacts to the existing HubSpot static list "MSPs".'
)


def test_f5_pack_not_installed_clarifies():
    with patch(
        "app.services.retrieve_plan_gate._org_has_pack",
        return_value=False,
    ):
        retrieved = retrieve_plan_or_none(
            MSP_TRY,
            org_id="org-1",
            connected_integrations=["apollo", "clay", "hubspot"],
            client=object(),
            require_pack_install=True,
        )
    assert retrieved is not None
    assert retrieved.kind == "clarify"
    assert "isn't installed" in retrieved.user_message.lower()


def test_f5_pack_installed_stages_enrich():
    with patch(
        "app.services.retrieve_plan_gate._org_has_pack",
        return_value=True,
    ):
        retrieved = retrieve_plan_or_none(
            MSP_TRY,
            org_id="org-1",
            connected_integrations=["apollo", "clay", "hubspot"],
            client=object(),
            require_pack_install=True,
        )
    assert retrieved is not None
    assert retrieved.kind == "pack_common_msp_enrich"


def test_f6_membership_proof_in_response_verifies():
    result = verify_collection_population(
        invoke_action="apollo.lists.add",
        result_data={"list_id": "L1", "added_count": 3, "success": True},
    )
    assert result.verified is True
    assert result.effect == "created"
    assert result.membership_count == 3


def test_f6_empty_membership_downgrades_status():
    status, effect, verify = apply_population_verify_to_status(
        status="completed",
        invoke_action="hubspot.lists.add_contact",
        result_data={"list_id": "L1", "success": True},
    )
    assert status == "partial_success"
    assert effect in {"accepted_async", "unknown"}
    assert verify is not None
    assert verify.verified is False


class _Ok:
    def __init__(self, data):
        self.success = True
        self.data = data
        self.error_message = None


def test_f6_apollo_follow_up_membership_confirmed():
    """Forced re-read path (no write proof) must use apollo.lists.list membership."""
    with patch("app.services.tool_service.invoke_tool") as inv:
        inv.return_value = _Ok(
            {
                "list_id": "L1",
                "contact_count": 2,
                "contacts": [{"id": "c1"}, {"id": "c2"}],
                "membership_source": "contacts.search_by_label",
            }
        )
        result = verify_collection_population(
            invoke_action="apollo.lists.add",
            result_data={"list_id": "L1", "success": True},
            ctx=object(),
        )
    assert result.verified is True
    assert result.follow_up_attempted is True
    assert result.detail == "follow_up_membership_confirmed"
    assert result.membership_count == 2
    inv.assert_called_once()
    assert inv.call_args.args[1] == "apollo.lists.list"


def test_f6_hubspot_follow_up_via_lists_get():
    with patch("app.services.tool_service.invoke_tool") as inv:
        inv.return_value = _Ok({"list_id": "34", "size": 1, "membershipCount": 1})
        result = verify_collection_population(
            invoke_action="hubspot.lists.add_contact",
            result_data={"list_id": "34", "success": True},
            ctx=object(),
        )
    assert result.verified is True
    assert result.follow_up_attempted is True
    assert result.detail == "follow_up_membership_confirmed"
    assert result.membership_count == 1
    assert inv.call_args.args[1] == "hubspot.lists.get"
