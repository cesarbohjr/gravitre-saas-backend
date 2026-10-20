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
    response = {**response, "tags": {"organization_id": "o1", "connector_id": "c1"}}
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


@pytest.mark.parametrize("tags", [None, {}, {"organization_id": "foreign", "connector_id": "c1"},
                                 {"organization_id": "o1", "connector_id": "foreign"}])
def test_remote_account_cannot_be_used_by_another_tenant_or_connector(monkeypatch, tags):
    config = {"auth_provider": "managed", "managed_connection_id": "n1", "managed_integration_id": "gravitre-slack"}
    body = {"connection_id": "n1", "provider_config_key": "gravitre-slack", "tags": tags,
            "credentials": {"access_token": "foreign-token"}}
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **kw: httpx.Response(
        200, json=body, request=httpx.Request("GET", "https://nango/connections/n1")))
    with pytest.raises(ValueError, match="Managed authorization unavailable"):
        managed_oauth_tokens(scoped_client(config), "o1", "c1",
                             SimpleNamespace(nango_secret_key="key", nango_api_base_url="https://api.nango.dev"))


@pytest.mark.asyncio
@pytest.mark.parametrize("serialized", [False, True])
async def test_config_patch_preserves_server_managed_identity(monkeypatch, serialized):
    from uuid import UUID
    from unittest.mock import AsyncMock
    from app.routers import connectors as routes
    from tests.routers.test_managed_connector_flow import Query, row
    cid = UUID("11111111-1111-1111-1111-111111111111")
    store = [row(id=str(cid))]
    if serialized:
        import json
        store[0]["config"] = json.dumps(store[0]["config"])
    db = SimpleNamespace(table=lambda name: Query(store))
    monkeypatch.setattr(routes, "shared_service_client", lambda *a: db)
    monkeypatch.setattr(routes, "write_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "get_connector_route_alias", AsyncMock(return_value={}))
    await routes.update_connector_route(cid, routes.ConnectorUpdateRequest(config={
        "managed_connection_id": "foreign", "managed_auth_attempt_id": "forged",
        "auth_provider": "native", "instance_url": "https://new.example"}),
        ({"user_id": "u1"}, "o1"), "production", SimpleNamespace())
    assert store[0]["config"]["managed_connection_id"] == "n1"
    assert store[0]["config"]["auth_provider"] == "managed"
    assert "managed_auth_attempt_id" not in store[0]["config"]
    assert store[0]["config"]["instance_url"] == "https://new.example"


def test_new_customer_config_cannot_select_managed_identity():
    from app.connectors.nango_client import customer_connector_config
    assert customer_connector_config({"auth_provider": "managed", "managed_connection_id": "foreign",
                                      "managed_future_routing_field": "forged", "region": "us"}) == {"region": "us"}


@pytest.mark.parametrize("vendor,managed", [("hubspot", False), ("slack", True), ("cal_com", True)])
def test_connection_test_endpoint_loads_config_and_selects_correct_auth_path(monkeypatch, vendor, managed):
    from uuid import UUID
    from app.routers import connectors as routes
    from app.connectors import managed_health
    cid = UUID("11111111-1111-1111-1111-111111111111")
    db = MagicMock()
    query = db.table.return_value
    for method in ("select", "eq", "is_", "limit"):
        getattr(query, method).return_value = query
    query.execute.return_value.data = [{"id": str(cid), "vendor": vendor, "environment": "production",
                                       "config": {"auth_provider": "managed"} if managed else {}}]
    monkeypatch.setattr(routes, "shared_service_client", lambda *args: db)
    remote = MagicMock(return_value="connected")
    native = MagicMock(return_value=("native-token", None))
    monkeypatch.setattr(managed_health, "managed_auth_status", remote)
    monkeypatch.setattr(routes, "ensure_hubspot_access_token", native)
    result = routes.test_connector_route(cid, {"user_id": "u1"}, "o1", "production", SimpleNamespace())
    assert result["success"]
    assert "config" in query.select.call_args.args[0].split(", ")
    if managed:
        assert remote.call_args.kwargs == {"environment_name": "production", "validate_remote": True}
        native.assert_not_called()
    else:
        native.assert_called_once()
        remote.assert_not_called()
