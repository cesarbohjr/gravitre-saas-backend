from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.connectors.managed_oauth import managed_oauth_tokens


def scoped_client(config, status="healthy"):
    c=MagicMock();q=c.table.return_value
    for method in ("select","eq","is_","limit"):getattr(q,method).return_value=q
    q.execute.return_value.data=[{"id":"c1","org_id":"o1","vendor":"slack","environment":"production","status":status,"config":config}]
    return c


def test_native_account_never_calls_nango(monkeypatch):
    http=MagicMock();monkeypatch.setattr(httpx.Client,"get",http)
    c=scoped_client({"auth_type":"oauth"})
    assert managed_oauth_tokens(c,"o1","c1",SimpleNamespace(),environment_name="production") is None
    http.assert_not_called()


@pytest.mark.parametrize("response",[
    {"connection_id":"n1","provider_config_key":"gravitre-slack","credentials":{"access_token":"current","refresh_token":"do-not-export"}},
    {"connection_id":"wrong","provider_config_key":"gravitre-slack","credentials":{"access_token":"current"}},
    {"connection_id":"n1","provider_config_key":"wrong","credentials":{"access_token":"current"}},
    {"connection_id":"n1","provider_config_key":"gravitre-slack","errors":[{"type":"auth"}]},
])
def test_bridge_is_scoped_checks_identity_and_never_exposes_refresh_token(monkeypatch,response):
    c=scoped_client({"auth_provider":"managed","managed_connection_id":"n1","managed_integration_id":"gravitre-slack"})
    monkeypatch.setattr(httpx.Client,"get",lambda *a,**kw:httpx.Response(200,json=response,request=httpx.Request("GET","https://nango/connections/n1")))
    settings=SimpleNamespace(nango_secret_key="key",nango_api_base_url="https://api.nango.dev")
    if response.get("connection_id")=="n1" and response.get("provider_config_key")=="gravitre-slack" and not response.get("errors"):
        assert managed_oauth_tokens(c,"o1","c1",settings,environment_name="production")=={"access_token":"current"}
    else:
        with pytest.raises(ValueError,match="Managed authorization unavailable"):
            managed_oauth_tokens(c,"o1","c1",settings,environment_name="production")
    args=[call.args for call in c.table.return_value.eq.call_args_list]
    assert ("org_id","o1") in args and ("environment","production") in args
    c.table.return_value.update.assert_not_called()


def test_slack_managed_failure_cannot_fall_back_to_old_native_secret(monkeypatch):
    import app.connectors.connector_tool_auth as auth
    import app.connectors.managed_oauth as managed
    monkeypatch.setattr(managed,"managed_oauth_tokens",MagicMock(side_effect=ValueError("Managed authorization unavailable")))
    legacy=MagicMock(return_value="old-revoked-token");monkeypatch.setattr(auth,"get_decrypted_secret",legacy)
    with pytest.raises(ValueError):auth.resolve_slack_bot_token(MagicMock(),"o1","c1",SimpleNamespace())
    legacy.assert_not_called()
