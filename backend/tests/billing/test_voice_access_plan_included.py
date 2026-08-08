"""Voice is plan-included — org ON/OFF, not Meson purchase gate."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.billing.voice_access import assert_voice_org_enabled, load_voice_org_settings


class _FakeTable:
    def __init__(self, row: dict):
        self._row = row
        self.updates: list[dict] = []

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def upsert(self, payload, on_conflict=None):  # noqa: ARG002
        self.updates.append(payload)
        self._row = {**self._row, **payload}
        return self

    def update(self, payload):
        self.updates.append(payload)
        self._row = {**self._row, **payload}
        return self

    def execute(self):
        return type("R", (), {"data": [self._row]})()


class _FakeClient:
    def __init__(self, row: dict):
        self.table_obj = _FakeTable(row)

    def table(self, _name: str):
        return self.table_obj


def test_load_defaults_plan_included_on():
    client = _FakeClient({})
    voice = load_voice_org_settings(client, org_id="org-1")
    assert voice["voice_enabled"] is True
    assert voice["voice_minutes_prepaid"] == 0
    assert voice["voice_auto_topup_enabled"] is False


def test_assert_blocks_when_org_disabled():
    client = _FakeClient({"voice_enabled": False})
    with pytest.raises(HTTPException) as exc:
        assert_voice_org_enabled(client, org_id="org-1")
    assert exc.value.status_code == 403
    detail = exc.value.detail
    assert isinstance(detail, dict)
    nested = detail.get("details") if isinstance(detail.get("details"), dict) else {}
    assert nested.get("reason") == "voice_org_disabled"
    assert "turned off" in str(detail.get("error") or "").lower()


def test_assert_allows_when_enabled():
    client = _FakeClient({"voice_enabled": True, "voice_minutes_prepaid": 30})
    voice = assert_voice_org_enabled(client, org_id="org-1")
    assert voice["voice_minutes_prepaid"] == 30
