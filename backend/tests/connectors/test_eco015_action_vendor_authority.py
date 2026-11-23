"""ECO-015 reproduction: global action registration is not connector ownership.

Exercise actual availability evaluation and the chat plan readiness caller.
Only connector/OAuth storage and auth health are synthetic; no provider calls.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.connectors.connector_availability_service import (
    _registered_action_matches_vendor, evaluate_connector_availability,
)
from app.services.chat_connector_execution_service import ChatConnectorExecutionService
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.tool_service import list_registered_actions


@pytest.mark.parametrize("action,kind", [
    ("gmail.messages.list", "read"),
    ("gmail.messages.send", "write"),
    ("hubspot.contacts.search", "read"),
])
def test_action_readiness_is_bound_to_the_connector_vendor(action, kind):
    assert action in list_registered_actions(), "exercise a genuinely registered action"
    settings = Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test", supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    row = {
        "id": "synthetic-hubspot", "vendor": "hubspot", "type": "hubspot",
        "status": "healthy", "environment": "production", "org_id": "org-1",
    }
    with (
        patch("app.connectors.connector_availability_service.list_connectors", return_value=[row]),
        patch("app.connectors.connector_availability_service.resolve_connector_auth_status", return_value="connected"),
        patch("app.connectors.connector_availability_service._hubspot_oauth_configured", return_value=True),
        patch("app.connectors.connector_availability_service.load_oauth_tokens", return_value={
            "access_token": "synthetic", "scopes": ["crm.objects.contacts.read"],
        }),
    ):
        availability = evaluate_connector_availability(
            MagicMock(), "org-1", row, settings, action_key=action,
        )
        plan = ConnectorActionPlan(
            tool_name=action.replace(".", "_"), invoke_action=action,
            integration="hubspot", kind=kind, label="Synthetic action",
            requires_approval=(kind == "write"),
        )
        denial = ChatConnectorExecutionService(settings)._verify_plan_executable(
            MagicMock(), "org-1", plan,
        )
    expected = action.startswith("hubspot.")
    assert availability["connected"] is True, "account connection is distinct from action readiness"
    assert (availability["execution_available"], denial is None) == (expected, expected)
    if expected:
        assert denial is None
    else:
        assert availability["read_available"] is False
        assert availability["write_available"] is False
        assert availability["blocking_reason"] == "unsupported_action"
        assert denial is not None


@pytest.mark.parametrize("vendor,action,expected", [
    ("google_drive", "drive.files.list", True),
    ("google_ads", "googleads.campaigns.list", True),
    ("googleads", "googleads.campaigns.list", True),
    ("HubSpot-CRM", "hubspot.contacts.search", True),
    ("outlook", "microsoft365.mail.messages.list", True),
    ("outlook", "microsoft365.calendar.events.list", False),
    ("google_drive", "gmail.messages.list", False),
    ("hubspot", "gmail.messages.send", False),
    ("hubspot", "hubspot.contacts.nonexistent", False),
])
def test_registered_aliases_preserve_owned_actions_without_cross_vendor_permission(vendor, action, expected):
    if expected or not action.endswith("nonexistent"):
        assert action in list_registered_actions()
    assert _registered_action_matches_vendor(vendor, action) is expected


def test_all_registered_catalog_ownership_pairs_remain_available():
    from app.services.connector_execution_matrix import build_connector_execution_matrix

    registered = set(list_registered_actions())
    pairs = {
        (entry.connector_id, entry.registry_key)
        for entry in build_connector_execution_matrix()
        if entry.registry_key in registered
    }
    assert len(pairs) > 100, "exercise the actual catalog, including aliases"
    rejected = [(vendor, action) for vendor, action in sorted(pairs)
                if not _registered_action_matches_vendor(vendor, action)]
    assert rejected == []
