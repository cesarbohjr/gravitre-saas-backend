from unittest.mock import MagicMock, patch
from app.connectors.partners.prospecting_providers import execute_prospecting_action
from app.marketplace.workflows.qualified_prospecting_workflow import build_prospecting_read_workflow_steps, workflow_config

def ctx():
    obj=MagicMock()
    obj.org_id="org-a"
    obj.environment_name="production"
    obj.connector_id="connector-a"
    return obj

def test_provider_rejects_cross_tenant_or_missing_connection():
    with patch("app.connectors.partners.prospecting_providers.get_connector",return_value=None):
        result=execute_prospecting_action(ctx(),"hunter.email.verify",{"email":"person@example.ca"})
    assert not result.success and result.error_code=="connector_not_connected"

def test_provider_never_calls_api_without_confirmed_free_budget():
    connector={"type":"hunter","status":"active","config":{"prospecting_enabled":True,"credits_confirmed":True,"credit_budget_approved":True,"remaining_free_credits":0}}
    with patch("app.connectors.partners.prospecting_providers.get_connector",return_value=connector),patch("httpx.Client") as network:
        result=execute_prospecting_action(ctx(),"hunter.email.verify",{"email":"person@example.ca"})
    assert result.error_code=="permission_denied"
    network.assert_not_called()

def test_workflow_is_canonical_and_has_no_writes():
    steps=build_prospecting_read_workflow_steps()
    assert len(steps)==1
    assert "hubspot.contacts.create" not in str(steps)
    assert workflow_config()["crm_writes_enabled"] is False
    assert workflow_config()["play"]["key"]=="qualified-prospecting"
