"""Focused fail-closed integration contracts (no live sends)."""
from unittest.mock import MagicMock,patch
import pytest
from app.plays.prospecting_approval import payload_hash
from app.plays.prospecting_authorized_writes import approved_hubspot_create
from app.services.tool_types import ToolContext

def test_approval_hash_is_order_independent_and_exact():
    assert payload_hash({"properties":{"email":"a@example.test"},"connector_id":"c"})==payload_hash({"connector_id":"c","properties":{"email":"a@example.test"}})
    assert payload_hash({"properties":{"email":"b@example.test"}})!=payload_hash({"properties":{"email":"a@example.test"}})

def test_unapproved_hubspot_never_calls_provider():
    ctx=MagicMock()
    ctx.org_id="org-a";ctx.actor_id="actor-a"
    with patch("app.plays.prospecting_authorized_writes.resolve_prospecting_approval",return_value=None),patch("app.plays.prospecting_authorized_writes.invoke_tool") as invoke:
        with pytest.raises(PermissionError):
            approved_hubspot_create(ctx,run_id="run-a",connector_id="c-a",payload={"properties":{"email":"recipient@example.test"}})
        invoke.assert_not_called()
