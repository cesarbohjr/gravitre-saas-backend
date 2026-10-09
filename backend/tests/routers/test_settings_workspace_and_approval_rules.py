"""v5 Settings: workspace defaults (accent, time zone) and approval rules persist in organizations.settings."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers.settings import (
    WorkspaceDefaultsUpdateRequest,
    get_approval_rules_route,
    get_workspace_defaults_route,
    update_approval_rules_route,
    update_workspace_defaults_route,
)

ADMIN = ({"user_id": "admin-1"}, "org-1")


class _Orgs:
    def __init__(self, settings: dict):
        self.settings = settings
        self.saved: list[dict] = []

    def table(self, _name):
        return self

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def update(self, payload):
        self.saved.append(payload["settings"])
        self.settings = payload["settings"]
        return self

    def execute(self):
        return MagicMock(data=[{"id": "org-1", "settings": self.settings}])


@pytest.fixture
def env():
    orgs = _Orgs({"timezone": "America/Vancouver"})
    with (
        patch("app.routers.settings.shared_service_client", return_value=orgs),
        patch("app.routers.settings.invalidate_org_state"),
        patch("app.routers.settings.write_audit_event") as audit,
    ):
        yield orgs, audit


def test_workspace_defaults_read_and_update(env):
    orgs, audit = env
    got = get_workspace_defaults_route({"user_id": "u"}, "org-1", MagicMock())
    assert got == {"workspace": {"accentColor": "#2E9E5B", "timeZone": "America/Vancouver"}}

    out = update_workspace_defaults_route(
        WorkspaceDefaultsUpdateRequest(accentColor="#5b5bd6", timeZone="Europe/London"), ADMIN, MagicMock()
    )
    assert out == {"workspace": {"accentColor": "#5B5BD6", "timeZone": "Europe/London"}}
    assert orgs.settings["timezone"] == "Europe/London"
    assert orgs.settings["enterprise"]["branding"]["primaryColor"] == "#5B5BD6"
    assert audit.call_args.kwargs["action"] == "settings.workspace_updated"


@pytest.mark.parametrize(
    "body",
    [WorkspaceDefaultsUpdateRequest(accentColor="green"), WorkspaceDefaultsUpdateRequest(timeZone="Mars/Base")],
)
def test_workspace_defaults_reject_bad_values(env, body):
    orgs, _ = env
    with pytest.raises(HTTPException) as exc:
        update_workspace_defaults_route(body, ADMIN, MagicMock())
    assert exc.value.status_code == 400
    assert orgs.saved == []


def test_approval_rules_round_trip(env):
    orgs, audit = env
    assert get_approval_rules_route({"user_id": "u"}, "org-1", MagicMock())["rules"]["sla"] == "4h"
    out = update_approval_rules_route({"escalatePastDue": True, "sla": "1bd"}, ADMIN, MagicMock())
    assert out["rules"]["escalatePastDue"] is True
    assert out["rules"]["slaMinutes"] == 1440
    assert orgs.settings["approvalRules"]["sla"] == "1bd"
    assert "slaMinutes" not in orgs.settings["approvalRules"]
    assert orgs.settings["timezone"] == "America/Vancouver"
    assert audit.call_args.kwargs["action"] == "settings.approval_rules_updated"
    again = get_approval_rules_route({"user_id": "u"}, "org-1", MagicMock())["rules"]
    assert again["escalatePastDue"] is True and again["customerEmailApproval"] is True


def test_approval_rules_reject_bad_sla(env):
    orgs, _ = env
    with pytest.raises(HTTPException) as exc:
        update_approval_rules_route({"sla": "2d"}, ADMIN, MagicMock())
    assert exc.value.status_code == 400
    assert orgs.saved == []
