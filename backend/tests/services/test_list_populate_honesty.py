"""Intent-scoped list populate honesty — create-only vs populate-required."""
from __future__ import annotations

from app.services.list_populate_honesty import (
    EMPTY_LIST_PARTIAL_REASON,
    apply_connector_run_honesty,
    assess_list_populate_honesty,
    has_list_membership_proof,
    membership_contact_count,
    run_expects_list_population,
)


def test_create_only_prospecting_pack_does_not_expect_population():
    """Prospecting Pack creates lists and defers membership — must stay create-complete."""
    steps = [
        {
            "name": "Create Apollo List",
            "status": "completed",
            "output_snapshot": {
                "invoke_action": "apollo.lists.create",
                "list_id": "abc",
                "outcome_effect": "created",
                "external_url": "https://app.apollo.io/#/lists/abc",
                "success": True,
            },
        },
        {
            "name": "Agent: Summarize scout results",
            "type": "agent",
            "metadata": {
                "task": (
                    "Summarize companies/contacts found and list IDs created. "
                    "Notify the operator with next membership steps."
                ),
            },
        },
    ]
    assert run_expects_list_population(step_rows=steps, output_refs=[]) is False
    status, reason = assess_list_populate_honesty(
        status="completed",
        step_rows=steps,
        output_refs=[
            {
                "invoke_action": "apollo.lists.create",
                "outcome_effect": "created",
                "entity_id": "abc",
                "success": True,
            }
        ],
    )
    assert status == "completed"
    assert reason is None


def test_msp_populate_agent_task_expects_population_without_add_proof():
    steps = [
        {
            "name": "Create Apollo List",
            "status": "completed",
            "output_snapshot": {
                "invoke_action": "apollo.lists.create",
                "list_id": "shell1",
                "outcome_effect": "created",
                "success": True,
                "external_url": "https://app.apollo.io/#/lists/shell1",
            },
        },
        {
            "name": "Populate Apollo list",
            "type": "agent",
            "metadata": {
                "task": (
                    "If the list is empty, call apollo.lists.add with entity_ids + "
                    'label_names=["MSP Prospects"] (modality=contacts).'
                ),
            },
        },
    ]
    refs = [
        {
            "invoke_action": "apollo.lists.create",
            "outcome_effect": "created",
            "entity_id": "shell1",
            "success": True,
            "external_url": "https://app.apollo.io/#/lists/shell1",
        }
    ]
    assert run_expects_list_population(step_rows=steps, output_refs=refs) is True
    status, reason = assess_list_populate_honesty(
        status="completed",
        step_rows=steps,
        output_refs=refs,
        workflow_slug="msp-prospecting-list-builder",
    )
    assert status == "partial_success"
    assert reason == EMPTY_LIST_PARTIAL_REASON


def test_populate_with_add_proof_stays_completed():
    steps = [
        {
            "name": "Create",
            "status": "completed",
            "output_snapshot": {
                "invoke_action": "apollo.lists.create",
                "list_id": "L1",
                "outcome_effect": "created",
                "success": True,
            },
        },
        {
            "name": "Add",
            "status": "completed",
            "output_snapshot": {
                "invoke_action": "apollo.lists.add",
                "added_count": 3,
                "contact_count": 3,
                "entity_ids": ["c1", "c2", "c3"],
                "outcome_effect": "created",
                "success": True,
            },
        },
    ]
    refs = [
        {"invoke_action": "apollo.lists.create", "outcome_effect": "created", "success": True},
        {
            "invoke_action": "apollo.lists.add",
            "added_count": 3,
            "contact_count": 3,
            "entity_ids": ["c1", "c2", "c3"],
            "outcome_effect": "created",
            "success": True,
        },
    ]
    status, reason = assess_list_populate_honesty(
        status="completed",
        step_rows=steps,
        output_refs=refs,
        parameters={"expects_list_population": True},
    )
    assert status == "completed"
    assert reason is None
    assert has_list_membership_proof(refs[1]) is True
    assert membership_contact_count(refs[1]) == 3


def test_add_with_zero_count_is_not_proof():
    assert (
        has_list_membership_proof(
            {
                "invoke_action": "apollo.lists.add",
                "added_count": 0,
                "entity_ids": [],
                "success": True,
            }
        )
        is False
    )


def test_hubspot_add_contact_id_counts_as_proof():
    assert (
        has_list_membership_proof(
            {
                "invoke_action": "hubspot.lists.add_contact",
                "contact_id": "99",
                "added_count": 1,
                "success": True,
            }
        )
        is True
    )


def test_apply_honesty_prefers_empty_list_reason_over_unproven():
    refs = [
        {
            "invoke_action": "apollo.lists.create",
            "outcome_effect": "created",
            "entity_id": "x",
            "success": True,
        }
    ]
    steps = [
        {
            "metadata": {"task": "call apollo.lists.add with entity_ids"},
            "type": "agent",
        }
    ]
    status, reason = apply_connector_run_honesty(
        status="completed",
        step_rows=steps,
        output_refs=refs,
        workflow_slug="msp-prospecting-list-builder",
    )
    assert status == "partial_success"
    assert reason == EMPTY_LIST_PARTIAL_REASON


def test_nl_populate_intent_without_create_only_wording():
    assert (
        run_expects_list_population(
            step_rows=[],
            parameters={
                "message": "Populate the Apollo list MSP Prospects with researched contacts",
            },
        )
        is True
    )
    assert (
        run_expects_list_population(
            step_rows=[],
            parameters={"message": "In Apollo, create a contact list named Scout Shell."},
        )
        is False
    )
