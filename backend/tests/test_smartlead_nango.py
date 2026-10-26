from unittest.mock import MagicMock,patch
from app.connectors.partners.smartlead_outreach import execute_smartlead

def ctx():
    x=MagicMock()
    x.org_id="tenant-a";x.connector_id="conn-a";x.environment_name="production"
    return x

def row():
    return {"type":"smartlead","status":"active","config":{
        "outreach_enabled":True,"auth_provider":"managed",
        "managed_connection_id":"tenant-a-smartlead",
        "managed_integration_id":"smartlead-ai"}}

def test_nango_connection_checks_org_and_connector_before_proxy():
    response=MagicMock(status_code=200)
    response.json.return_value=[]
    with patch("app.connectors.partners.smartlead_outreach.get_connector",return_value=row()),patch(
        "app.connectors.partners.smartlead_outreach.scoped_connection",return_value={}
    ) as ownership,patch("app.connectors.partners.smartlead_outreach.proxy_request",return_value=response) as proxy:
        result=execute_smartlead(ctx(),"campaigns.list",{})
    assert result.success
    assert ownership.call_args.kwargs["org_id"]=="tenant-a"
    assert ownership.call_args.kwargs["connector_id"]=="conn-a"
    assert proxy.call_args.kwargs["integration_id"]=="smartlead-ai"
    assert proxy.call_args.kwargs["endpoint"]=="/campaigns/"

def test_missing_nango_connection_never_proxies():
    with patch("app.connectors.partners.smartlead_outreach.get_connector",return_value={
        "type":"smartlead","status":"active","config":{"outreach_enabled":True}
    }),patch("app.connectors.partners.smartlead_outreach.proxy_request") as proxy:
        result=execute_smartlead(ctx(),"campaigns.list",{})
    assert not result.success
    proxy.assert_not_called()

def test_enrollment_stays_blocked_with_valid_nango():
    with patch("app.connectors.partners.smartlead_outreach.get_connector",return_value=row()),patch(
        "app.connectors.partners.smartlead_outreach.proxy_request"
    ) as proxy:
        result=execute_smartlead(ctx(),"leads.enroll",{"approved":True})
    assert not result.success
    proxy.assert_not_called()
