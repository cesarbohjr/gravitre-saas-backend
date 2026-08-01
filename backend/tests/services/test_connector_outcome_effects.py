"""Class-level guards: idempotent finds, OutcomeEffect gate, multi-system enrich routing."""
from __future__ import annotations

from app.services.business_outcome.projector import project_business_outcome
from app.services.connector_chat_routing import should_run_connector_preflight
from app.services.connector_outcome_effects import (
    already_existed_list_summary,
    classify_write_effect,
    coerce_terminal_status_for_effect,
    has_effect_proof,
    is_already_existed_effect,
    is_multi_system_enrich_or_sync_intent,
    is_mutating_action,
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


def test_classify_hubspot_lists_create_with_id_is_created():
    assert is_mutating_action("hubspot.lists.create") is True
    effect = classify_write_effect(
        invoke_action="hubspot.lists.create",
        result_data={"id": "list-99", "name": "MSPs"},
        success=True,
    )
    assert effect == "created"
    assert has_effect_proof({"list_id": "abc"}) is True


def test_classify_hubspot_lists_create_without_proof_is_unknown():
    effect = classify_write_effect(
        invoke_action="hubspot.lists.create",
        result_data={"message": "ok"},
        success=True,
    )
    assert effect == "unknown"
    assert (
        coerce_terminal_status_for_effect(
            status="completed",
            effect=effect,
            invoke_action="hubspot.lists.create",
        )
        == "partial_success"
    )


def test_classify_clay_leads_push_accepted_async():
    effect = classify_write_effect(
        invoke_action="clay.leads.push",
        result_data={"status": "queued", "job_id": "job-1"},
        success=True,
    )
    assert effect == "accepted_async"
    assert (
        coerce_terminal_status_for_effect(
            status="completed",
            effect="accepted_async",
            invoke_action="clay.leads.push",
        )
        == "partial_success"
    )


def test_classify_noop_and_already_existed():
    assert (
        classify_write_effect(
            invoke_action="apollo.lists.create",
            result_data={"already_existed": True, "label": {"id": "1"}},
            success=True,
        )
        == "already_existed"
    )
    assert (
        classify_write_effect(
            invoke_action="hubspot.lists.update",
            result_data={"noop": True, "status": "unchanged"},
            success=True,
        )
        == "noop"
    )
    assert (
        coerce_terminal_status_for_effect(
            status="completed",
            effect="noop",
            invoke_action="hubspot.lists.update",
        )
        == "partial_success"
    )


def test_classify_non_mutating_is_read():
    assert (
        classify_write_effect(
            invoke_action="hubspot.contacts.get",
            result_data={"id": "c1"},
            success=True,
        )
        == "read"
    )
    assert (
        coerce_terminal_status_for_effect(
            status="completed",
            effect="read",
            invoke_action="hubspot.contacts.get",
        )
        == "completed"
    )


def test_business_outcome_unknown_mutating_not_created_record():
    outcome = project_business_outcome(
        org_id="org-1",
        run={
            "id": "run-2",
            "status": "partial_success",
            "parameters": {
                "invoke_action": "hubspot.lists.create",
                "outcome_effect": "unknown",
                "source": "assistant_chat",
            },
        },
        execution_result={
            "success": True,
            "body": "List create returned without an id.",
            "integration": "hubspot",
            "structured": {"outcome_effect": "unknown"},
        },
        invoke_action="hubspot.lists.create",
    )
    assert outcome.kind != "created_record"
    assert outcome.sections.verification is not None
    assert outcome.sections.verification.method == "module_a_effect_unproven"
