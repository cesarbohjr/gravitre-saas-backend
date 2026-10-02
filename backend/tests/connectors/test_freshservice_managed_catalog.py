from __future__ import annotations

from app.connectors.action_catalog.f1_read_slice import is_f1_read_action
from app.connectors.action_catalog.f1_write_slice import is_f1_write_action
from app.connectors.action_catalog.registry import get_action_spec, get_vendor_spec
from app.services.write_success_verification import resolve_success_verification


def test_freshservice_catalog_is_executable_and_governed() -> None:
    vendor = get_vendor_spec("freshservice")
    assert vendor is not None
    action_ids = {action.id for action in vendor.all_actions()}
    assert {
        "freshservice.tickets.list",
        "freshservice.tickets.get",
        "freshservice.tickets.activities",
        "freshservice.tickets.update_status",
    } <= action_ids

    assert is_f1_read_action("freshservice.tickets.list")
    assert is_f1_read_action("freshservice.tickets.get")
    assert is_f1_read_action("freshservice.tickets.activities")
    assert is_f1_write_action("freshservice.tickets.update_status")

    write_spec = get_action_spec("freshservice.tickets.update_status")
    assert write_spec is not None
    assert write_spec.kind == "write"
    assert write_spec.requires_approval is True
    assert write_spec.governance_classification == "write"
    assert {"ticket_id", "status"} <= set(write_spec.required_parameters)


def test_freshservice_status_write_requires_source_of_record_field_assert() -> None:
    verification = resolve_success_verification("freshservice.tickets.update_status")
    assert verification.mode == "follow_up_field_assert"
    assert verification.read_action == "freshservice.tickets.get"
    assert verification.assert_field == "status"
    assert verification.request_field == "status"
