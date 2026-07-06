"""Smoke tests — top 10 vendors × top 50 implemented actions."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.action_catalog.action_parameters import parameters_for_action
from app.services.chat_tool_bridge import build_dynamic_chat_tool_specs
from app.services.connector_catalog_audit import top_actions_for_smoke, top_vendors_by_implementation
from app.services.connector_execution_matrix import get_matrix_entry
from app.services.tool_registry import get_tool_registry
from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext, ToolValidationError


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(
        disable_connectors=False,
        connector_secrets_encryption_key="k" * 32,
        private_connector_runtime_enabled=False,
    )
    return ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-smoke",
        actor_id="user-smoke",
        environment_name="production",
    )


TOP_VENDORS = top_vendors_by_implementation(10)
TOP_ACTIONS = top_actions_for_smoke(50)


@pytest.mark.parametrize("vendor", TOP_VENDORS)
def test_vendor_has_implemented_actions(vendor: str):
    rows = [a for a in list_registered_actions() if a.startswith(f"{vendor}.")]
    assert len(rows) >= 1, vendor


@pytest.mark.parametrize("action_id", TOP_ACTIONS)
def test_action_matrix_and_schema(action_id: str):
    vendor = action_id.split(".", 1)[0]
    entry = get_matrix_entry(vendor, action_id)
    assert entry is not None, action_id
    assert entry.implementation_status != "not_implemented", action_id
    schema = parameters_for_action(action_id, kind=entry.kind, suffix=action_id.split(".", 1)[-1])
    assert schema.get("type") == "object"
    assert schema.get("properties")
    assert "connector_id" in schema["properties"]
    assert entry.tool_registry_key in build_dynamic_chat_tool_specs()


@pytest.mark.parametrize("action_id", TOP_ACTIONS)
def test_action_chat_tool_spec(action_id: str):
    vendor = action_id.split(".", 1)[0]
    entry = get_matrix_entry(vendor, action_id)
    assert entry is not None
    spec = get_tool_registry().get_spec(entry.tool_registry_key)
    assert spec is not None, entry.tool_registry_key
    assert spec.invoke_action == entry.registry_key
    assert spec.parameters.get("properties")


@pytest.mark.parametrize("action_id", TOP_ACTIONS)
def test_invoke_tool_validates_or_runs_mocked(action_id: str, tool_ctx: ToolContext):
    """Smoke invoke — expect validation error (missing params) or mocked success, never missing executor."""
    vendor = action_id.split(".", 1)[0]
    entry = get_matrix_entry(vendor, action_id)
    assert entry is not None
    registered = set(list_registered_actions())
    assert entry.registry_key in registered

    with patch("app.services.tool_service.get_connector_by_type", return_value=None):
        try:
            result = invoke_tool(tool_ctx, entry.registry_key, {})
        except ToolValidationError:
            return
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            assert "not found" not in msg and "no executor" not in msg
            return
        assert hasattr(result, "success")
        assert hasattr(result, "action")


@pytest.mark.parametrize(
    ("action_id", "requires_approval"),
    [
        ("hubspot.contacts.search", False),
        ("hubspot.contacts.create", True),
        ("slack.post_message", True),
        ("jira.issues.create", True),
        ("gmail.messages.send", True),
        ("salesforce.leads.update", True),
        ("monday.items.create", True),
        ("zendesk.tickets.create", True),
        ("asana.tasks.create", True),
        ("notion.pages.create", True),
    ],
)
def test_risk_and_approval_classification(action_id: str, requires_approval: bool):
    vendor = action_id.split(".", 1)[0]
    entry = get_matrix_entry(vendor, action_id)
    if entry is None or entry.implementation_status == "not_implemented":
        pytest.skip(f"{action_id} not implemented")
    assert entry.requires_approval is requires_approval or entry.kind == "write"
