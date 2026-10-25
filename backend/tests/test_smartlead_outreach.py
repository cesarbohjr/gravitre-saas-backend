from unittest.mock import MagicMock,patch
from app.connectors.partners.smartlead_outreach import execute_smartlead

def ctx():
    x=MagicMock()
    x.org_id="tenant-a";x.connector_id="conn-a";x.environment_name="production"
    return x

def test_enrollment_never_calls_network_without_canonical_approval():
    c=ctx()
    row={"type":"smartlead","status":"active","config":{"outreach_enabled":True}}
    with patch("app.connectors.partners.smartlead_outreach.get_connector",return_value=row),patch("httpx.Client") as network:
        result=execute_smartlead(c,"leads.enroll",{"approved":True,"connector_id":"conn-a"})
    assert not result.success and result.error_code=="permission_denied"
    network.assert_not_called()

def test_read_requires_connected_tenant_connector():
    with patch("app.connectors.partners.smartlead_outreach.get_connector",return_value=None),patch("httpx.Client") as network:
        result=execute_smartlead(ctx(),"campaigns.list",{})
    assert result.error_code=="connector_not_connected"
    network.assert_not_called()
