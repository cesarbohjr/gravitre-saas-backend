from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.connectors.catalog_dependencies import declared_dependencies
from app.connectors.managed_oauth import ManagedOAuthAccessToken
from app.connectors.nango_registry import get_nango_connector_spec, LEGACY_NANGO_CONNECTOR_SPECS


@pytest.mark.parametrize("vendor,provider", [
    ("freshservice", "freshservice-oauth"), ("gong", "gong-oauth"), ("hibob", "hibob-oauth"),
    ("cal_com", "cal-com-oauth"), ("bamboohr", "bamboohr"),
    ("greenhouse", "greenhouse-harvest-partner"), ("ahrefs", "ahrefs"),
    ("linear", "linear"), ("gitlab", "gitlab"), ("shopify", "shopify"),
    ("paypal", "paypal"), ("meta_marketing", "facebook"),
])
def test_new_authorization_paths_use_reviewed_interactive_oauth(vendor, provider):
    spec = get_nango_connector_spec(vendor)
    assert spec.provider == provider and spec.auth_mode == "OAUTH2"
    assert get_nango_connector_spec(vendor, integration_id="unrelated") is None


@pytest.mark.parametrize("vendor", ["freshservice", "gong", "hibob", "cal_com"])
def test_legacy_identity_is_allowlisted_only_for_its_original_vendor(vendor):
    old = LEGACY_NANGO_CONNECTOR_SPECS[vendor]
    assert get_nango_connector_spec(vendor, integration_id=old.integration_id) == old
    assert get_nango_connector_spec("front", integration_id=old.integration_id) is None


def test_dependency_extractor_reads_nested_packages_workflows_and_serialized_config():
    payload = {"systems": ["Microsoft 365", "platform"], "required_connector_groups": [["hubspot", "salesforce"]],
               "steps": [{"config": '{"tool_action":"gitlab.issues.list"}'},
                         {"requires_connector": "bamboohr"}],
               "children": [{"requiredConnectors": [{"connectorType": "greenhouse", "label": "not-a-vendor"}]}],
               "actions": ["slack.post_message", "unknown.untrusted"],
               "description": "Use a made-up provider", "api_key": "do-not-include"}
    refs = declared_dependencies(payload, action_vendors={"gitlab", "slack"})
    assert set(refs) == {"microsoft365", "platform", "hubspot", "salesforce", "gitlab", "bamboohr", "greenhouse", "slack"}


@pytest.mark.parametrize("vendor,module_name,resolver,error", [
    ("bamboohr", "bamboohr", "resolve_bamboohr_credentials", "BambooHRAPIError"),
    ("greenhouse", "greenhouse", "resolve_greenhouse_api_key", "GreenhouseAPIError"),
    ("ahrefs", "ahrefs_api", "resolve_ahrefs_connector", "AhrefsAPIError"),
])
def test_managed_failure_never_reads_old_native_credentials(monkeypatch, vendor, module_name, resolver, error):
    import importlib
    module = importlib.import_module(f"app.connectors.{module_name}")
    from app.connectors import managed_oauth
    row = {"id": "c1", "config": {"auth_provider": "managed", "subdomain": "acme"}}
    monkeypatch.setattr(module, "get_connector", lambda *a, **kw: row)
    token = MagicMock(side_effect=ValueError("unavailable"))
    monkeypatch.setattr(managed_oauth, "managed_oauth_tokens", token)
    if hasattr(module, "managed_oauth_tokens"):
        monkeypatch.setattr(module, "managed_oauth_tokens", token)
    legacy = MagicMock(return_value="old-native-secret")
    monkeypatch.setattr(module, "get_decrypted_secret", legacy)
    with pytest.raises(getattr(module, error)):
        getattr(module, resolver)(MagicMock(), "o1", "c1", SimpleNamespace(), environment_name="production")
    legacy.assert_not_called()


@pytest.mark.parametrize("managed", [False, True])
def test_bamboohr_selects_bearer_only_after_managed_authorization(monkeypatch, managed):
    from app.connectors import bamboohr
    request = MagicMock(return_value=httpx.Response(200, json={"employees": []}))
    monkeypatch.setattr(httpx.Client, "request", request)
    credential = ManagedOAuthAccessToken("current") if managed else "native-key"
    bamboohr.list_employees("https://api.bamboohr.com/api/gateway.php/acme/v1", credential)
    assert request.call_args.args[:2] == ("GET", "https://api.bamboohr.com/api/gateway.php/acme/v1/employees/directory")
    if managed:
        assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer current"
        assert "auth" not in request.call_args.kwargs
    else:
        assert request.call_args.kwargs["auth"] == ("native-key", "x")


@pytest.mark.parametrize("managed", [False, True])
def test_greenhouse_oauth_uses_v3_and_native_api_key_stays_on_v1(monkeypatch, managed):
    from app.connectors import greenhouse
    request = MagicMock(return_value=httpx.Response(200, json=[]))
    monkeypatch.setattr(httpx.Client, "request", request)
    key = ManagedOAuthAccessToken("current") if managed else "native-key"
    greenhouse.list_applications(key, job_id="123")
    assert request.call_args.args[1] == f"https://harvest.greenhouse.io/{'v3' if managed else 'v1'}/applications"
    assert request.call_args.kwargs["params"] == {"job_ids" if managed else "job_id": "123"}
    if managed:
        assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer current"
        assert request.call_args.kwargs["auth"] is None
    else:
        assert request.call_args.kwargs["auth"] == ("native-key", "")


def test_greenhouse_v3_candidate_uses_documented_ids_filter(monkeypatch):
    from app.connectors import greenhouse
    request = MagicMock(return_value=[{"id": 123, "first_name": "Example"}])
    monkeypatch.setattr(greenhouse, "_request", request)
    assert greenhouse.get_candidate(ManagedOAuthAccessToken("token"), "123")["id"] == 123
    assert request.call_args.args[2] == "candidates"
    assert request.call_args.kwargs["params"] == {"ids": "123", "per_page": 1}
    with pytest.raises(greenhouse.GreenhouseAPIError):
        greenhouse.get_candidate(ManagedOAuthAccessToken("token"), "../applications")
    assert request.call_count == 1


def test_managed_linear_failure_cannot_use_a_legacy_api_key(monkeypatch):
    from app.connectors import phase2_connector_tools as tools, managed_oauth
    from app.services.tool_types import ToolAuthExpiredError
    monkeypatch.setattr(tools, "_oauth_token", MagicMock(side_effect=ToolAuthExpiredError("expired")))
    monkeypatch.setattr(managed_oauth, "managed_oauth_row", lambda *a, **kw: {"id": "c1"})
    legacy = MagicMock(return_value="old-key")
    monkeypatch.setattr(tools, "get_decrypted_secret", legacy)
    with pytest.raises(ToolAuthExpiredError):
        tools._linear_token(SimpleNamespace(client=MagicMock(), org_id="o1", environment_name="production"), "c1")
    legacy.assert_not_called()


def test_managed_linear_graphql_uses_bearer(monkeypatch):
    from app.connectors import phase2_connector_tools as tools
    request = MagicMock(return_value=httpx.Response(200, json={"data": {"viewer": {"id": "1"}}}))
    monkeypatch.setattr(httpx.Client, "post", request)
    tools._linear_graphql(ManagedOAuthAccessToken("current"), "query { viewer { id } }")
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer current"


def test_wrong_provider_is_rejected_before_fetching_any_credential(monkeypatch):
    from app.connectors import managed_oauth
    monkeypatch.setattr(managed_oauth, "managed_oauth_row", lambda *a, **kw: {
        "vendor": "slack", "status": "healthy", "config": {"auth_provider": "managed",
        "managed_integration_id": "gravitre-slack", "managed_connection_id": "c1"}})
    remote = MagicMock()
    monkeypatch.setattr(managed_oauth, "scoped_connection", remote)
    with pytest.raises(ValueError, match="vendor mismatch"):
        managed_oauth.managed_oauth_tokens(MagicMock(), "o1", "c1", SimpleNamespace(), expected_vendor="linear")
    remote.assert_not_called()


def test_generic_managed_failure_never_loads_native_tokens(monkeypatch):
    from app.connectors import generic_oauth, managed_oauth
    monkeypatch.setattr(managed_oauth, "managed_oauth_tokens", MagicMock(side_effect=ValueError("expired")))
    native = MagicMock()
    monkeypatch.setattr(generic_oauth, "load_oauth_tokens", native)
    token, error = generic_oauth.ensure_generic_session(MagicMock(), "o1", "c1", SimpleNamespace(), vendor="gitlab", environment_name="production")
    assert token is None and "reconnect" in error
    native.assert_not_called()


@pytest.mark.parametrize("vendor,config,expected", [
    ("gitlab", {"instance_url": "https://untrusted.example"}, "https://gitlab.com/api/v4/projects"),
    ("shopify", {"shop": "untrusted.example/", "subdomain": "authorized-store"},
     "https://authorized-store.myshopify.com/admin/api/2024-01/products.json"),
])
def test_managed_template_uses_its_approved_vendor_host(monkeypatch, vendor, config, expected):
    from app.connectors import phase2_connector_tools as tools
    monkeypatch.setattr(tools, "_resolve_connector", lambda *a: {"id": "c1", "config": config})
    monkeypatch.setattr(tools, "enforce_rate_limit", lambda *a: None)
    monkeypatch.setattr(tools, "_oauth_token", lambda *a: ManagedOAuthAccessToken("current"))
    request = MagicMock(return_value={"result": []})
    monkeypatch.setattr(tools, "_rest_request", request)
    ctx = SimpleNamespace(client=MagicMock(), org_id="o1")
    getattr(tools, f"_exec_{vendor}")(ctx, {}, f"{vendor}.{'projects' if vendor == 'gitlab' else 'products'}.list")
    assert request.call_args.kwargs["url"] == expected
