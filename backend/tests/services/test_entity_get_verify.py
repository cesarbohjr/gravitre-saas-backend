"""follow_up_entity_get adapter: confirm writes, and stay honest when you can't.

The failure cases matter more than the happy path here. The bug this closes was
75 catalog declarations that never executed while their outcomes were still
reported at full confidence, so an adapter that guesses is worse than none.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.entity_get_verify import (
    EntityGetVerifyResult,
    extract_entity_id,
    id_param_candidates,
    read_confirms_entity_id,
    verify_entity_get,
)

WRITE_ACTION = "hubspot.contacts.create"
READ_ACTION = "hubspot.contacts.get"


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.connector_id = "conn-1"
    return ctx


def _result(success: bool, data: dict) -> MagicMock:
    out = MagicMock()
    out.success = success
    out.data = data
    return out


def _patch_registry(invoke):
    return (
        patch("app.services.tool_service.invoke_tool", invoke),
        patch(
            "app.services.tool_service.list_registered_actions",
            lambda: [READ_ACTION, WRITE_ACTION],
        ),
    )


def _run(invoke, *, result_data, action=WRITE_ACTION):
    p1, p2 = _patch_registry(invoke)
    with p1, p2:
        return verify_entity_get(
            invoke_action=action, result_data=result_data, ctx=_ctx(), settle=False
        )


def test_extract_entity_id_searches_nested_envelopes():
    assert extract_entity_id({"id": "123"}) == "123"
    assert extract_entity_id({"data": {"id": "456"}}) == "456"
    assert extract_entity_id({"result": {"contactId": "789"}}, "contact_id") == "789"


def test_verified_against_the_real_hubspot_read_shape():
    """The live shape that broke this adapter: the id is under the resource key.

    hubspot.contacts.get returns {"contact": {"id": ...}}. The first cut searched
    a fixed envelope list (data/result/record/...), missed it, and reported a
    successful write as unverified — mocks returning a flat {"id": ...} hid it.
    """
    live_read = {
        "contact": {
            "id": "273899549679",
            "properties": {
                "email": "f6.dbg@gravitre-smoke.example.com",
                "hs_object_id": "273899549679",
                "lastname": "Debug",
            },
            "archived": False,
            "url": "https://app-na3.hubspot.com/contacts/343328749/record/0-1/273899549679",
        }
    }
    assert read_confirms_entity_id(live_read, "273899549679") is True
    assert extract_entity_id(live_read) == "273899549679"

    invoke = MagicMock(return_value=_result(True, live_read))
    out = _run(invoke, result_data={"id": "273899549679", "contact": live_read["contact"]})
    assert out.verified is True
    assert out.detail == "follow_up_entity_get_confirmed"


def test_read_confirms_only_the_written_id_not_a_neighbouring_one():
    """Walking the payload must not let an unrelated nested id confirm the write."""
    payload = {"contact": {"id": "111"}, "owner": {"id": "999"}}
    assert read_confirms_entity_id(payload, "111") is True
    assert read_confirms_entity_id(payload, "222") is False

    invoke = MagicMock(return_value=_result(True, payload))
    out = _run(invoke, result_data={"id": "222"})
    assert out.verified is False


def test_extract_entity_id_rejects_sentinels():
    """A bare success flag must never be mistaken for an entity id."""
    assert extract_entity_id({"id": True}) is None
    assert extract_entity_id({"id": "none"}) is None
    assert extract_entity_id({"id": ""}) is None
    assert extract_entity_id(None) is None


def test_id_param_candidates_are_convention_derived():
    assert id_param_candidates("hubspot.contacts.get")[0] == "contact_id"
    assert "id" in id_param_candidates("hubspot.contacts.get")
    assert id_param_candidates("hubspot.companies.get")[0] == "company_id"


def test_verified_when_read_returns_the_written_id():
    invoke = MagicMock(return_value=_result(True, {"id": "42"}))
    out = _run(invoke, result_data={"id": "42"})
    assert out.verified is True
    assert out.effect == "created"
    assert out.detail == "follow_up_entity_get_confirmed"
    assert out.entity_id == "42"


def test_not_verified_when_read_returns_a_different_id():
    invoke = MagicMock(return_value=_result(True, {"id": "99"}))
    out = _run(invoke, result_data={"id": "42"})
    assert out.verified is False
    assert out.effect == "unknown"
    assert "entity_id_mismatch" in out.detail


def test_stays_accepted_async_when_write_response_has_no_id():
    invoke = MagicMock(return_value=_result(True, {"id": "42"}))
    out = _run(invoke, result_data={"status": "queued"})
    assert out.verified is False
    assert out.effect == "accepted_async"
    assert out.detail == "entity_id_absent_from_write_response"
    invoke.assert_not_called()


def test_stays_accepted_async_when_read_raises():
    invoke = MagicMock(side_effect=RuntimeError("vendor 503"))
    out = _run(invoke, result_data={"id": "42"})
    assert out.verified is False
    assert out.effect == "accepted_async"
    assert out.detail == "follow_up_read_failed"


def test_stays_accepted_async_when_read_action_unregistered():
    with patch("app.services.tool_service.invoke_tool", MagicMock()), patch(
        "app.services.tool_service.list_registered_actions", lambda: []
    ):
        out = verify_entity_get(
            invoke_action=WRITE_ACTION, result_data={"id": "42"}, ctx=_ctx(), settle=False
        )
    assert out.verified is False
    assert out.detail == "read_action_not_registered"


def test_stays_accepted_async_without_tool_context():
    p1, p2 = _patch_registry(MagicMock())
    with p1, p2:
        out = verify_entity_get(
            invoke_action=WRITE_ACTION, result_data={"id": "42"}, ctx=None, settle=False
        )
    assert out.verified is False
    assert out.detail == "no_tool_context"


def test_accepted_async_action_is_not_claimed_as_entity_get():
    out = verify_entity_get(
        invoke_action="hubspot.contacts.get", result_data={"id": "1"}, ctx=_ctx(), settle=False
    )
    assert out.verified is False
    assert out.detail == "not_entity_get_mode"


def test_scheduler_no_longer_skips_entity_get_actions():
    """The regression: entity_get declarations used to be dropped on the floor."""
    from app.services import write_success_verification as wsv

    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)

    with patch.object(wsv, "_schedule_entity_get_verification", _capture):
        wsv.schedule_write_success_verification(
            client=MagicMock(),
            org_id="org-1",
            run_id="run-1",
            invoke_action=WRITE_ACTION,
            result_data={"id": "42"},
            settings=MagicMock(),
            ctx=_ctx(),
        )

    assert captured.get("invoke_action") == WRITE_ACTION
    assert captured.get("run_id") == "run-1"


def test_scheduler_still_ignores_actions_with_no_declared_read():
    from app.services import write_success_verification as wsv

    called = False

    def _capture(**kwargs):
        nonlocal called
        called = True

    with patch.object(wsv, "_schedule_entity_get_verification", _capture):
        wsv.schedule_write_success_verification(
            client=MagicMock(),
            org_id="org-1",
            run_id="run-1",
            invoke_action="slack.post_message",
            result_data={"ok": True},
            settings=MagicMock(),
            ctx=_ctx(),
        )

    from app.services.write_success_verification import resolve_success_verification

    if resolve_success_verification("slack.post_message").mode == "accepted_async":
        assert called is False


def test_every_declared_entity_get_read_is_actually_executable():
    """Catalog-wide: a declared sibling GET that cannot run is a silent dead end.

    Pins the alias bug this adapter shipped with — the executability gate checked
    raw registry membership while invoke_tool resolves aliases first, so the five
    Google reads (google_drive.files.get -> drive.files.get) were being reported
    read_action_not_registered even though they execute fine.
    """
    import json
    import pathlib

    from app.connectors.action_catalog.tool_aliases import resolve_registry_action
    from app.services.tool_service import list_registered_actions

    catalog = json.loads(
        pathlib.Path(
            "app/connectors/action_catalog/data/success_verification_catalog.json"
        ).read_text(encoding="utf-8")
    )["actions"]
    registered = set(list_registered_actions())

    dead = sorted(
        f"{action} -> {spec.get('read_action')}"
        for action, spec in catalog.items()
        if spec.get("mode") == "follow_up_entity_get"
        and resolve_registry_action(str(spec.get("read_action") or ""), registered)
        not in registered
    )
    assert not dead, f"entity_get declarations whose read cannot execute: {dead}"
