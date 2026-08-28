"""follow_up_field_assert: prove the change applied, or say you can't.

The whole reason this mode exists is that an id read-back would have happily
"confirmed" a stage change that never happened, so the refusal cases carry the
weight here.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.field_assert_verify import (
    find_requested_value,
    find_stored_value,
    verify_field_assert,
)

ACTION = "hubspot.deals.update_stage"
READ = "hubspot.deals.get"


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.connector_id = "conn-1"
    return ctx


def _result(success: bool, data: dict) -> MagicMock:
    out = MagicMock()
    out.success = success
    out.data = data
    return out


def _run(invoke, *, result_data, request_params):
    with patch("app.services.tool_service.invoke_tool", invoke), patch(
        "app.services.tool_service.list_registered_actions", lambda: [READ, ACTION]
    ):
        return verify_field_assert(
            invoke_action=ACTION,
            result_data=result_data,
            request_params=request_params,
            ctx=_ctx(),
            settle=False,
        )


def _deal(stage: str) -> dict:
    """The real hubspot.deals.get shape: record under the resource key."""
    return {"deal": {"id": "42", "properties": {"dealname": "Acme", "dealstage": stage}}}


def test_finds_requested_and_stored_values_in_nested_payloads():
    assert find_requested_value({"deal_id": "42", "stage": "won"}, "stage", "dealstage") == "won"
    assert find_requested_value({"properties": {"dealstage": "won"}}, "stage", "dealstage") == "won"
    assert find_stored_value(_deal("won"), "dealstage") == "won"


def test_verified_when_stored_value_matches_the_request():
    invoke = MagicMock(return_value=_result(True, _deal("contractsent")))
    out = _run(
        invoke,
        result_data={"id": "42"},
        request_params={"deal_id": "42", "stage": "contractsent"},
    )
    assert out.verified is True
    assert out.effect == "updated"
    assert out.detail == "follow_up_field_assert_confirmed"
    assert out.expected == "contractsent"
    assert out.observed == "contractsent"


def test_not_verified_when_the_vendor_kept_the_old_value():
    """The case an id read-back would have wrongly called verified."""
    invoke = MagicMock(return_value=_result(True, _deal("appointmentscheduled")))
    out = _run(
        invoke,
        result_data={"id": "42"},
        request_params={"deal_id": "42", "stage": "closedwon"},
    )
    assert out.verified is False
    assert out.effect == "unknown"
    assert out.detail == "field_value_mismatch"
    assert out.expected == "closedwon"
    assert out.observed == "appointmentscheduled"


def test_stays_accepted_async_when_requested_value_is_unknown():
    """Asserting the field merely has some value would prove nothing."""
    invoke = MagicMock(return_value=_result(True, _deal("closedwon")))
    out = _run(invoke, result_data={"id": "42"}, request_params={"deal_id": "42"})
    assert out.verified is False
    assert out.detail == "requested_value_unavailable"
    invoke.assert_not_called()


def test_stays_accepted_async_when_field_missing_from_read_back():
    invoke = MagicMock(return_value=_result(True, {"deal": {"id": "42", "properties": {}}}))
    out = _run(
        invoke, result_data={"id": "42"}, request_params={"deal_id": "42", "stage": "closedwon"}
    )
    assert out.verified is False
    assert out.detail == "field_absent_from_read_back"


def test_stays_accepted_async_when_read_fails():
    invoke = MagicMock(side_effect=RuntimeError("vendor 503"))
    out = _run(
        invoke, result_data={"id": "42"}, request_params={"deal_id": "42", "stage": "closedwon"}
    )
    assert out.verified is False
    assert out.detail == "follow_up_read_failed"


def test_entity_get_action_is_not_claimed_as_field_assert():
    out = verify_field_assert(
        invoke_action="hubspot.contacts.create",
        result_data={"id": "1"},
        request_params={"properties": {"email": "a@b.c"}},
        ctx=_ctx(),
        settle=False,
    )
    assert out.verified is False
    assert out.detail == "not_field_assert_mode"


def test_catalog_declaration_is_wired_and_executable():
    from app.connectors.action_catalog.tool_aliases import resolve_registry_action
    from app.services.tool_service import list_registered_actions
    from app.services.write_success_verification import resolve_success_verification

    spec = resolve_success_verification(ACTION)
    assert spec.mode == "follow_up_field_assert"
    assert spec.read_action == READ
    assert spec.assert_field == "dealstage"
    assert spec.request_field == "stage"

    registered = set(list_registered_actions())
    assert resolve_registry_action(READ, registered) in registered


def test_scheduler_dispatches_field_assert_actions():
    from app.services import write_success_verification as wsv

    captured: dict = {}

    with patch.object(wsv, "_schedule_field_assert_verification", lambda **kw: captured.update(kw)):
        wsv.schedule_write_success_verification(
            client=MagicMock(),
            org_id="org-1",
            run_id="run-1",
            invoke_action=ACTION,
            result_data={"id": "42"},
            settings=MagicMock(),
            ctx=_ctx(),
            request_params={"deal_id": "42", "stage": "closedwon"},
        )

    assert captured.get("invoke_action") == ACTION
    assert captured.get("request_params") == {"deal_id": "42", "stage": "closedwon"}
