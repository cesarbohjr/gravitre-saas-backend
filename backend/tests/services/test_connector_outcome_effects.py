"""Class-level guards: idempotent finds and multi-system enrich routing."""
from __future__ import annotations

from app.services.business_outcome.projector import project_business_outcome
from app.services.connector_chat_routing import should_run_connector_preflight
from app.services.connector_outcome_effects import (
    already_existed_list_summary,
    is_already_existed_effect,
    is_multi_system_enrich_or_sync_intent,
    prefers_single_list_create,
)


def test_is_already_existed_effect():
    assert is_already_existed_effect({"already_existed": True, "label": {"id": "1"}}) is True
    assert is_already_existed_effect({"label": {"id": "1"}}) is False
    assert is_already_existed_effect(None) is False


def test_already_existed_summary_is_honest():
    text = already_existed_list_summary(name="MSP Prospects", list_id="6a4d6a98")
    assert "Found existing" in text
    assert "MSP Prospects" in text
    assert "No contacts were added" in text
    assert "no HubSpot sync" in text


def test_multi_system_enrich_intent_detected():
    msg = (
        'Use Clay to enrich the existing Apollo contact list "MSP Prospects", '
        'then add those enriched contacts to the existing HubSpot static list "MSPs".'
    )
    assert is_multi_system_enrich_or_sync_intent(msg) is True
    assert prefers_single_list_create(msg) is False


def test_omit_name_apollo_list_create_still_prefers_connector():
    msg = "In Apollo, create a contact list."
    assert prefers_single_list_create(msg) is True
    assert (
        should_run_connector_preflight(
            {},
            message=msg,
            connected_integrations=["apollo", "hubspot", "clay"],
        )
        is False
    )


def test_enrich_sync_prompt_preflights_orchestration():
    msg = (
        'Use Clay to enrich the existing Apollo contact list "MSP Prospects", '
        'then add those enriched contacts to the existing HubSpot static list "MSPs".'
    )
    assert (
        should_run_connector_preflight(
            {},
            message=msg,
            connected_integrations=["apollo", "clay", "hubspot"],
        )
        is True
    )


def test_business_outcome_kind_found_existing_not_created():
    outcome = project_business_outcome(
        org_id="org-1",
        run={
            "id": "run-1",
            "status": "partial_success",
            "parameters": {
                "invoke_action": "apollo.lists.create",
                "already_existed": True,
                "outcome_effect": "already_existed",
                "source": "assistant_chat",
            },
        },
        execution_result={
            "success": True,
            "body": already_existed_list_summary(name="MSP Prospects", list_id="abc"),
            "integration": "apollo",
            "structured": {"already_existed": True, "outcome_effect": "already_existed"},
        },
        invoke_action="apollo.lists.create",
    )
    assert outcome.kind == "found_existing_record"
    assert outcome.status == "partial_success"
    assert outcome.sections.verification is not None
    assert outcome.sections.verification.method == "module_a_idempotent_find"
    assert "no net-new create" in (outcome.sections.verification.detail or "").lower()
