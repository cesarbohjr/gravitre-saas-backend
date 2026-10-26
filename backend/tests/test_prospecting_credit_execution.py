from unittest.mock import MagicMock, patch
from app.connectors.partners.prospecting_providers import execute_prospecting_action

def context():
    x=MagicMock()
    x.org_id="org-a"
    x.environment_name="production"
    x.connector_id="connector-a"
    return x

def enabled():
    return {"type":"hunter","status":"active","config":{
        "prospecting_enabled":True,"credits_confirmed":True,
        "credit_budget_approved":True,"remaining_free_credits":4,
        "credit_period":"2026-10-01"}}

def test_credit_reservation_decline_blocks_http():
    ctx=context()
    ctx.client.rpc.return_value.execute.return_value.data=False
    with patch("app.connectors.partners.prospecting_providers.get_connector",return_value=enabled()),patch(
        "app.connectors.partners.prospecting_providers.get_decrypted_secret",return_value="test-key"
    ),patch("httpx.Client") as network:
        answer=execute_prospecting_action(ctx,"hunter.email.verify",{"email":"person@example.ca","request_id":"id-1"})
    assert not answer.success
    assert answer.error_code=="permission_denied"
    network.assert_not_called()

def test_success_settles_charge_with_same_request_id():
    ctx=context()
    ctx.client.rpc.return_value.execute.return_value.data=True
    network=MagicMock()
    response=MagicMock(status_code=200)
    response.json.return_value={"data":{"status":"valid"}}
    network.return_value.__enter__.return_value.request.return_value=response
    with patch("app.connectors.partners.prospecting_providers.get_connector",return_value=enabled()),patch(
        "app.connectors.partners.prospecting_providers.get_decrypted_secret",return_value="test-key"
    ),patch("httpx.Client",network):
        answer=execute_prospecting_action(ctx,"hunter.email.verify",{"email":"person@example.ca","request_id":"id-2"})
    assert answer.success
    calls=ctx.client.rpc.call_args_list
    assert calls[0].args[0]=="prospect_reserve_credits"
    assert calls[1].args[0]=="prospect_settle_credits"
    assert calls[1].args[1]["p_request"]=="id-2"
    assert calls[1].args[1]["p_consumed"]==1
