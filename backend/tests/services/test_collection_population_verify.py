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
