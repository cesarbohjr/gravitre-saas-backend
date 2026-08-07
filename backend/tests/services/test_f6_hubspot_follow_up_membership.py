"""Standing F6 regression — population follow-up must use HubSpot settle pattern.

Catches the eventual-consistency / empty-membership false-fail class that
regressed after the original F6 close. Apollo + Marketo must share HubSpot's
long backoff + final settle read (G.5.9).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.collection_population_verify import (
    _SETTLE_BACKOFF_S,
    _SETTLE_FINAL_SLEEP_S,
    verify_collection_population,
)


def test_hubspot_follow_up_membership_retries_until_non_empty():
    """First get returns 0 members; later get returns >0 → confirmed."""
    calls = {"n": 0}

    def fake_invoke(_ctx, action, params):
        assert action == "hubspot.lists.get"
        assert params.get("list_id") == "42"
        calls["n"] += 1
        size = 0 if calls["n"] < 3 else 2
        return SimpleNamespace(
            success=True,
            data={
                "list_id": "42",
                "size": size,
                "membershipCount": size,
                "memberships": [{"recordId": "1"}, {"recordId": "2"}] if size else [],
            },
        )

    with patch("app.services.tool_service.invoke_tool", side_effect=fake_invoke), patch(
        "app.services.collection_population_verify.time.sleep", return_value=None
    ):
        result = verify_collection_population(
            invoke_action="hubspot.lists.add_contact",
            # No membership_count / contact_count — force follow-up path (live F6 strip).
            result_data={"list_id": "42", "success": True},
            client=MagicMock(),
            org_id="org",
            settings=MagicMock(),
            environment_name="test",
            ctx=MagicMock(),
        )

    assert result.follow_up_attempted is True
    assert result.verified is True
    assert result.detail == "follow_up_membership_confirmed"
    assert result.membership_count >= 1
    assert calls["n"] >= 2


def test_hubspot_follow_up_empty_after_retries_stays_unverified():
    def fake_invoke(_ctx, action, params):
        return SimpleNamespace(
            success=True,
            data={"list_id": "7", "size": 0, "membershipCount": 0, "memberships": []},
        )

    with patch("app.services.tool_service.invoke_tool", side_effect=fake_invoke), patch(
        "app.services.collection_population_verify.time.sleep", return_value=None
    ):
        result = verify_collection_population(
            invoke_action="hubspot.lists.add_contact",
            result_data={"list_id": "7"},
            client=MagicMock(),
            org_id="org",
            settings=MagicMock(),
            environment_name="test",
            ctx=MagicMock(),
        )

    assert result.verified is False
    assert result.detail == "follow_up_empty_membership"


def test_apollo_follow_up_membership_retries_until_non_empty():
    calls = {"n": 0}

    def fake_invoke(_ctx, action, params):
        assert action == "apollo.lists.list"
        calls["n"] += 1
        n = 0 if calls["n"] < 3 else 1
        return SimpleNamespace(
            success=True,
            data={"list_id": "lab1", "contact_count": n, "contacts": [{"id": "c1"}] if n else []},
        )

    with patch("app.services.tool_service.invoke_tool", side_effect=fake_invoke), patch(
        "app.services.collection_population_verify.time.sleep", return_value=None
    ):
        result = verify_collection_population(
            invoke_action="apollo.lists.add",
            result_data={"list_id": "lab1", "success": True},
            client=MagicMock(),
            org_id="org",
            settings=MagicMock(),
            environment_name="test",
            ctx=MagicMock(),
        )

    assert result.follow_up_attempted is True
    assert result.verified is True
    assert result.detail == "follow_up_membership_confirmed"
    assert calls["n"] >= 2


def test_apollo_follow_up_uses_hubspot_settle_window_and_final_read():
    """G.5.9 — Apollo must not use a shorter backoff / skip settle read."""
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_invoke(_ctx, action, params):
        assert action == "apollo.lists.list"
        calls["n"] += 1
        # Stay empty through the full backoff loop; confirm on settle read.
        n = 1 if calls["n"] > len(_SETTLE_BACKOFF_S) else 0
        return SimpleNamespace(
            success=True,
            data={"list_id": "lab1", "contact_count": n, "contacts": [{"id": "c1"}] if n else []},
        )

    def fake_sleep(seconds: float):
        sleeps.append(float(seconds))

    with patch("app.services.tool_service.invoke_tool", side_effect=fake_invoke), patch(
        "app.services.collection_population_verify.time.sleep", side_effect=fake_sleep
    ):
        result = verify_collection_population(
            invoke_action="apollo.lists.add",
            result_data={"list_id": "lab1", "success": True},
            client=MagicMock(),
            org_id="org",
            settings=MagicMock(),
            environment_name="test",
            ctx=MagicMock(),
        )

    assert result.detail == "follow_up_membership_confirmed"
    assert calls["n"] == len(_SETTLE_BACKOFF_S) + 1  # loop + settle
    assert _SETTLE_FINAL_SLEEP_S in sleeps
    # Backoff delays from the shared HubSpot window (not the old 2/3/5/8/8 set).
    for delay in _SETTLE_BACKOFF_S[:-1]:
        assert delay in sleeps


def test_marketo_follow_up_membership_retries_until_non_empty():
    calls = {"n": 0}

    def fake_invoke(_ctx, action, params):
        assert action == "marketo.lists.get_leads"
        assert params.get("list_id") == "1001"
        calls["n"] += 1
        n = 0 if calls["n"] < 3 else 1
        return SimpleNamespace(
            success=True,
            data={
                "list_id": "1001",
                "member_count": n,
                "result": [{"id": 9}] if n else [],
            },
        )

    with patch("app.services.tool_service.invoke_tool", side_effect=fake_invoke), patch(
        "app.services.collection_population_verify.time.sleep", return_value=None
    ):
        result = verify_collection_population(
            invoke_action="marketo.lists.add_to_static_list",
            result_data={"list_id": "1001", "success": True},
            client=MagicMock(),
            org_id="org",
            settings=MagicMock(),
            environment_name="test",
            ctx=MagicMock(),
        )

    assert result.follow_up_attempted is True
    assert result.verified is True
    assert result.detail == "follow_up_membership_confirmed"
    assert result.membership_count >= 1
    assert calls["n"] >= 2


def test_marketo_follow_up_uses_hubspot_settle_window_and_final_read():
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_invoke(_ctx, action, params):
        assert action == "marketo.lists.get_leads"
        calls["n"] += 1
        n = 1 if calls["n"] > len(_SETTLE_BACKOFF_S) else 0
        return SimpleNamespace(
            success=True,
            data={"list_id": "1001", "member_count": n, "result": [{"id": 1}] if n else []},
        )

    def fake_sleep(seconds: float):
        sleeps.append(float(seconds))

    with patch("app.services.tool_service.invoke_tool", side_effect=fake_invoke), patch(
        "app.services.collection_population_verify.time.sleep", side_effect=fake_sleep
    ):
        result = verify_collection_population(
            invoke_action="marketo.lists.add_to_static_list",
            result_data={"list_id": "1001", "success": True},
            client=MagicMock(),
            org_id="org",
            settings=MagicMock(),
            environment_name="test",
            ctx=MagicMock(),
        )

    assert result.detail == "follow_up_membership_confirmed"
    assert calls["n"] == len(_SETTLE_BACKOFF_S) + 1
    assert _SETTLE_FINAL_SLEEP_S in sleeps
