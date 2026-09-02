"""Connector health events must carry a real, named actor.

`connector.auth.failed` and `connector.connected` passed actor_id=None, and
write_audit_event silently drops those rows (the column is NOT NULL with an FK
to users). So a connector dropping into auth failure left no audit trail at
all, while the code looked like it was recording one.

The sweep has no request user, but the event does have a real owner:
connectors.created_by, or the org's owner/admin when that is blank (13 of 19
status-changeable production connectors have no created_by, measured in
backend/scripts/scratch_connector_actor_coverage.py).
"""
from __future__ import annotations

from typing import Any

import pytest

from app.connectors import health_monitor_service as hms

CREATOR = "11111111-1111-4111-8111-111111111111"
OWNER = "22222222-2222-4222-8222-222222222222"
ADMIN = "33333333-3333-4333-8333-333333333333"
ORG = "44444444-4444-4444-8444-444444444444"


class _FakeQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def select(self, *_a: Any, **_k: Any) -> "_FakeQuery":
        return self

    def eq(self, *_a: Any, **_k: Any) -> "_FakeQuery":
        return self

    def limit(self, *_a: Any, **_k: Any) -> "_FakeQuery":
        return self

    def execute(self) -> Any:
        return type("R", (), {"data": list(self._rows)})()


class _FakeClient:
    def __init__(self, members: list[dict[str, Any]]) -> None:
        self._members = members
        self.member_lookups = 0

    def table(self, name: str) -> _FakeQuery:
        if name == "organization_members":
            self.member_lookups += 1
            return _FakeQuery(self._members)
        raise AssertionError(f"unexpected table {name}")


def test_connector_creator_is_preferred() -> None:
    client = _FakeClient([{"user_id": OWNER, "role": "owner"}])

    actor = hms.resolve_connector_audit_actor(client, ORG, {"created_by": CREATOR})

    assert actor == CREATOR
    assert client.member_lookups == 0, "no need to query members when created_by exists"


def test_falls_back_to_org_owner_when_creator_is_missing() -> None:
    client = _FakeClient(
        [
            {"user_id": ADMIN, "role": "admin"},
            {"user_id": OWNER, "role": "owner"},
        ]
    )

    actor = hms.resolve_connector_audit_actor(client, ORG, {"created_by": None})

    assert actor == OWNER, "owner outranks admin"


def test_falls_back_to_admin_when_there_is_no_owner() -> None:
    client = _FakeClient([{"user_id": ADMIN, "role": "admin"}])

    assert hms.resolve_connector_audit_actor(client, ORG, {}) == ADMIN


def test_blank_created_by_is_treated_as_missing() -> None:
    client = _FakeClient([{"user_id": OWNER, "role": "owner"}])

    assert hms.resolve_connector_audit_actor(client, ORG, {"created_by": "   "}) == OWNER


def test_returns_none_when_org_has_no_members() -> None:
    """Caller must log loudly; writing None would be silently discarded."""
    client = _FakeClient([])

    assert hms.resolve_connector_audit_actor(client, ORG, {}) is None


def test_member_lookup_is_cached_across_connectors() -> None:
    """A sweep touches many connectors per org; it must not re-query each time."""
    client = _FakeClient([{"user_id": OWNER, "role": "owner"}])
    cache: dict[str, str | None] = {}

    for _ in range(4):
        assert hms.resolve_connector_audit_actor(client, ORG, {}, cache=cache) == OWNER

    assert client.member_lookups == 1


def test_lookup_failure_does_not_raise_into_the_sweep() -> None:
    class _Boom:
        def table(self, _name: str) -> Any:
            raise RuntimeError("db down")

    assert hms.resolve_connector_audit_actor(_Boom(), ORG, {}) is None


@pytest.mark.parametrize(
    "status,previous,expect_action",
    [
        ("error", "healthy", "connector.auth.failed"),
        ("healthy", "error", "connector.connected"),
        ("active", "pending_auth", "connector.connected"),
    ],
)
def test_status_change_writes_event_with_real_actor(
    monkeypatch, status: str, previous: str, expect_action: str
) -> None:
    written: list[dict[str, Any]] = []

    monkeypatch.setattr(
        hms,
        "write_audit_event",
        lambda _c, **kw: written.append(kw),
    )

    class _UpdateClient(_FakeClient):
        def table(self, name: str) -> Any:
            if name == "connectors":
                return type(
                    "U",
                    (),
                    {
                        "update": lambda _s, _p: type(
                            "E",
                            (),
                            {
                                "eq": lambda _s2, *_a, **_k: type(
                                    "E2",
                                    (),
                                    {
                                        "eq": lambda _s3, *_a2, **_k2: type(
                                            "E3", (), {"execute": lambda _s4: None}
                                        )()
                                    },
                                )()
                            },
                        )()
                    },
                )()
            return super().table(name)

    client = _UpdateClient([{"user_id": OWNER, "role": "owner"}])
    row = {"id": "c-1", "org_id": ORG, "config": {}, "created_by": None}
    result = {
        "skipped": False,
        "connector_id": "c-1",
        "org_id": ORG,
        "status": status,
        "previous_status": previous,
        "changed": True,
        "latency_ms": 12,
        "auth_status": "invalid" if status == "error" else "valid",
        "vendor": "hubspot",
        "environment": "production",
    }

    hms._persist_health_result(client, row, result)

    assert len(written) == 1, "the status change must produce exactly one audit event"
    assert written[0]["action"] == expect_action
    assert written[0]["actor_id"] == OWNER
    assert written[0]["actor_id"] is not None
    assert written[0]["metadata"]["actorSource"] == "org_owner_or_admin"


def test_no_event_is_written_when_no_actor_can_be_resolved(monkeypatch) -> None:
    written: list[dict[str, Any]] = []
    monkeypatch.setattr(hms, "write_audit_event", lambda _c, **kw: written.append(kw))

    class _UpdateClient(_FakeClient):
        def table(self, name: str) -> Any:
            if name == "connectors":
                return type(
                    "U",
                    (),
                    {
                        "update": lambda _s, _p: type(
                            "E",
                            (),
                            {
                                "eq": lambda _s2, *_a, **_k: type(
                                    "E2",
                                    (),
                                    {
                                        "eq": lambda _s3, *_a2, **_k2: type(
                                            "E3", (), {"execute": lambda _s4: None}
                                        )()
                                    },
                                )()
                            },
                        )()
                    },
                )()
            return super().table(name)

    client = _UpdateClient([])
    hms._persist_health_result(
        client,
        {"id": "c-1", "org_id": ORG, "config": {}, "created_by": None},
        {
            "skipped": False,
            "connector_id": "c-1",
            "org_id": ORG,
            "status": "error",
            "previous_status": "healthy",
            "changed": True,
            "latency_ms": 1,
            "auth_status": "invalid",
            "vendor": "hubspot",
            "environment": "production",
        },
    )

    assert written == [], "an actorless event would be silently dropped; skip loudly instead"
