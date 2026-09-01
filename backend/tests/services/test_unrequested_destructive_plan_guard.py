"""Guard: never invent arguments for a destructive action nobody asked for.

Pins the fix for a reproduced defect (4/4 live at tip `db928881`, see
docs/delivery/readonly-destructive-proposal.md). A read-only question reached
ReAct, which selected `hubspot_lists_create`; pack defaults then filled every
argument and the turn arrived as "I still have Create list waiting for approval.
Say yes to run it." `APPROVAL_ACTION_MISMATCH` cannot catch this, because the
approved and executed actions are identical — the proposal itself is fabricated.

The hard part is not blocking the fabrication, it is blocking it without breaking
legitimate omit-name creates, which are also fully default-filled. Both
directions are asserted here.
"""
from __future__ import annotations

import pytest

from app.marketplace.workflows.msp_prospecting_list_workflow import (
    DEFAULT_HUBSPOT_LIST_NAME,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.pack_common_intent_defaults import (
    apply_pack_common_defaults,
    is_unrequested_destructive_plan,
)

# The exact message that reproduces, from the live artifact.
READ_ONLY = (
    "Show me the most recent deals in our HubSpot pipeline with their amounts and close dates."
)
REQUESTED = "Create a HubSpot static list"


def _hubspot_list_create(*, destructive: bool, **args: object) -> ConnectorActionPlan:
    return ConnectorActionPlan(
        tool_name="hubspot_lists_create",
        invoke_action="hubspot.lists.create",
        integration="hubspot",
        kind="write",
        label="Create list",
        args=dict(args),
        requires_approval=True,
        destructive=destructive,
    )


def test_read_only_message_gets_no_invented_args_for_destructive_create() -> None:
    """The defect itself: no create intent, so no arguments may be conjured."""
    out = apply_pack_common_defaults(
        _hubspot_list_create(destructive=True), message=READ_ONLY
    )
    assert not out.args.get("name"), (
        "a read-only question was given a fabricated list name; a trusting 'yes' "
        "would create a HubSpot list the user never requested"
    )
    assert not out.args.get("object_type_id")
    assert not out.args.get("processing_type")


def test_a_real_create_request_still_gets_its_defaults() -> None:
    """The regression this guard must not cause."""
    out = apply_pack_common_defaults(
        _hubspot_list_create(destructive=True), message=REQUESTED
    )
    assert out.args.get("name") == DEFAULT_HUBSPOT_LIST_NAME
    assert out.args.get("processing_type") == "MANUAL"
    assert out.args.get("object_type_id") == "0-1"


def test_non_destructive_actions_are_untouched_by_the_guard() -> None:
    """Only `destructive` gates this, so approval-only actions keep their defaults."""
    out = apply_pack_common_defaults(
        _hubspot_list_create(destructive=False), message=READ_ONLY
    )
    assert out.args.get("name") == DEFAULT_HUBSPOT_LIST_NAME


def test_predicate_flags_the_fully_fabricated_plan() -> None:
    fabricated = ConnectorActionPlan(
        tool_name="hubspot_lists_create",
        invoke_action="hubspot.lists.create",
        integration="hubspot",
        kind="write",
        label="Create list",
        args={"name": "MSPs", "object_type_id": "0-1", "processing_type": "MANUAL"},
        inferred_fields=("name", "object_type_id", "processing_type"),
        inference_sources={
            "name": "pack_common_default",
            "object_type_id": "pack_common_default",
            "processing_type": "pack_common_default",
        },
        requires_approval=True,
        destructive=True,
    )
    assert is_unrequested_destructive_plan(fabricated, READ_ONLY) is True
    # Same plan, but the user actually asked for it.
    assert is_unrequested_destructive_plan(fabricated, REQUESTED) is False


def test_an_empty_destructive_plan_is_not_approvable() -> None:
    """The live tail of the defect: no invented args, but still staged for yes.

    Withholding pack defaults emptied the arguments, yet schema validation still
    passed (each slot is individually optional) and the turn reached production
    as "I still have Create list waiting for approval. Say yes to run it." with
    args {}. There is nothing for a yes to mean here.
    """
    from app.services.connector_action_workflows import missing_params_stage_patch

    staged = missing_params_stage_patch(
        _hubspot_list_create(destructive=True), READ_ONLY, task_state={}
    )
    assert staged is not None, (
        "a destructive plan with zero arguments was allowed straight to "
        "awaiting_confirm; one 'yes' would fire an action with no subject"
    )
    clarification, patch = staged
    assert clarification.dialogue_mode == "clarify"
    assert (patch.get("pending_task") or {}).get("status") != "awaiting_confirm"


def test_a_destructive_plan_with_real_args_still_reaches_approval() -> None:
    """The refusal must not block genuine, fully-specified writes."""
    from app.services.connector_action_workflows import missing_params_stage_patch

    complete = _hubspot_list_create(
        destructive=True, name="Northeast Renewals", object_type_id="0-1", processing_type="MANUAL"
    )
    assert missing_params_stage_patch(complete, REQUESTED, task_state={}) is None


READ_SHAPED = [
    READ_ONLY,
    "What contact lists do we have in HubSpot?",
    "Show me our pipeline.",
    "How many deals closed last quarter?",
    "Can you summarize the pipeline for me?",
]

# Must NOT be blocked: real write requests, and mixed asks where the user does
# want something to happen. Wrongly refusing a genuine write is the worse failure.
WRITE_SHAPED = [
    REQUESTED,
    "Create a HubSpot list called Northeast Renewals",
    "Show me the deals, then create a list for them",
    "Make a static list of our MSP prospects",
    "Set up a contact list in Apollo",
]


@pytest.mark.parametrize("message", READ_SHAPED)
def test_read_shaped_asks_do_not_stage_a_destructive_action(message: str) -> None:
    from app.services.connector_action_workflows import missing_params_stage_patch

    plan = _hubspot_list_create(
        destructive=True, name="MSPs", object_type_id="0-1", processing_type="MANUAL"
    )
    staged = missing_params_stage_patch(plan, message, task_state={})
    assert staged is not None, f"read-shaped ask staged a destructive write: {message!r}"
    clarification, patch = staged
    assert clarification.dialogue_mode == "clarify"
    assert patch.get("pending_task") is None


@pytest.mark.parametrize("message", WRITE_SHAPED)
def test_genuine_write_requests_are_not_blocked(message: str) -> None:
    from app.services.connector_action_workflows import (
        is_read_only_request_for_destructive_plan,
    )

    plan = _hubspot_list_create(
        destructive=True, name="Northeast Renewals", object_type_id="0-1"
    )
    assert is_read_only_request_for_destructive_plan(plan, message) is False, (
        f"a real write request was treated as read-only: {message!r}"
    )


def test_the_gate_only_applies_to_destructive_plans() -> None:
    from app.services.connector_action_workflows import (
        is_read_only_request_for_destructive_plan,
    )

    benign = _hubspot_list_create(destructive=False, name="MSPs")
    assert is_read_only_request_for_destructive_plan(benign, READ_ONLY) is False


def test_predicate_ignores_plans_with_a_user_supplied_arg() -> None:
    """One genuinely user-derived value is enough to clear the fabrication test."""
    partly_real = ConnectorActionPlan(
        tool_name="hubspot_lists_create",
        invoke_action="hubspot.lists.create",
        integration="hubspot",
        kind="write",
        label="Create list",
        args={"name": "Northeast Renewals", "object_type_id": "0-1"},
        inferred_fields=("object_type_id",),
        inference_sources={
            "name": "message",
            "object_type_id": "pack_common_default",
        },
        requires_approval=True,
        destructive=True,
    )
    assert is_unrequested_destructive_plan(partly_real, READ_ONLY) is False
