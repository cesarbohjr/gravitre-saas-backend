from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.connectors.nango_registry import BUSINESS_CONNECTORS
from app.services.managed_business_tools import MANAGED_BUSINESS_TOOL_EXECUTORS
from app.services.tool_types import ToolValidationError, ToolAuthExpiredError


def context():
    return SimpleNamespace(client=MagicMock(),org_id="o1",environment_name="production",connector_id=None,settings=SimpleNamespace())


@pytest.fixture
def adapter(monkeypatch):
    import app.services.managed_service_desk_tools as shared
    import app.services.managed_business_tools as business
    fetch=MagicMock()
    monkeypatch.setattr(shared,"get_connector_by_type",fetch)
    monkeypatch.setattr(shared,"enforce_rate_limit",MagicMock())
    proxy=MagicMock(return_value=httpx.Response(200,json={"records":[]},request=httpx.Request("GET","https://nango/proxy")))
    monkeypatch.setattr(business,"proxy_request",proxy)
    return fetch,proxy


@pytest.mark.parametrize("spec",BUSINESS_CONNECTORS,ids=lambda s:s["vendor"])
def test_reads_preserve_vendor_and_scoped_custom_identity(adapter,spec):
    fetch,proxy=adapter
    fetch.return_value={"id":"c1","org_id":"o1","environment":"production","vendor":spec["vendor"],"type":"custom","status":"active",
                        "config":{"auth_provider":"managed","managed_connection_id":"n1","managed_integration_id":spec["integration_id"]}}
    params={}
    if spec["vendor"]=="harvest":params["harvest_account_id"]="123"
    if spec["vendor"]=="freshsales":params["contact_id"]="12"
    result=MANAGED_BUSINESS_TOOL_EXECUTORS[spec["vendor"]+"."+spec["read_action"]](context(),params)
    assert result.success and result.connector_id=="c1"
    assert proxy.call_args.kwargs["method"]=="GET"
    assert proxy.call_args.kwargs["integration_id"]==spec["integration_id"]
    assert proxy.call_args.kwargs["connection_id"]=="n1"
    assert "{" not in proxy.call_args.kwargs["endpoint"]
    assert fetch.call_args.kwargs["environment_name"]=="production"


def test_no_arbitrary_proxy_arguments(adapter):
    fetch,proxy=adapter
    with pytest.raises(ToolValidationError):
        MANAGED_BUSINESS_TOOL_EXECUTORS["discourse.categories.list"](context(),{"endpoint":"https://attacker","method":"POST"})
    proxy.assert_not_called();fetch.assert_not_called()


def test_foreign_tenant_is_rejected_before_proxy(adapter):
    fetch,proxy=adapter
    fetch.return_value={"id":"c1","org_id":"other","environment":"production","vendor":"discourse","type":"custom","status":"active"}
    with pytest.raises(ToolValidationError):MANAGED_BUSINESS_TOOL_EXECUTORS["discourse.categories.list"](context(),{})
    proxy.assert_not_called()


def test_custom_connector_lookup_scopes_vendor_and_environment():
    from app.connectors.repository import get_connector_by_type
    c=MagicMock();q=c.table.return_value
    for method in ("select","eq","in_","is_","order","limit"):getattr(q,method).return_value=q
    q.execute.return_value.data=[]
    assert get_connector_by_type(c,"o1","discourse","staging") is None
    values=[call.args for call in q.eq.call_args_list]
    assert ("vendor","discourse") in values and ("type","custom") in values
    assert ("environment","staging") in values and ("org_id","o1") in values


def test_business_actions_are_registered_reads_without_demo_writes():
    from app.connectors.action_catalog.registry import get_action_spec, get_vendor_spec
    from app.services.tool_service import list_registered_actions
    assert len(MANAGED_BUSINESS_TOOL_EXECUTORS)==30
    registered=set(list_registered_actions())
    for key in MANAGED_BUSINESS_TOOL_EXECUTORS:
        action=get_action_spec(key)
        assert action and action.kind=="read" and not action.destructive
        assert key in registered
        vendor=get_vendor_spec(key.split(".")[0])
        assert vendor and not vendor.v2 and not vendor.v3 and not vendor.demo_workflows


@pytest.fixture(autouse=True)
def managed_remote_ownership(monkeypatch):
    monkeypatch.setattr("app.services.managed_service_desk_tools.scoped_connection", lambda *a, **kw: {"errors": []})


def test_foreign_remote_ownership_blocks_business_proxy(adapter, monkeypatch):
    fetch, proxy = adapter
    fetch.return_value = {"id": "c1", "org_id": "o1", "environment": "production", "vendor": "discourse",
                          "type": "custom", "status": "active", "config": {
                              "auth_provider": "managed", "managed_connection_id": "foreign", "managed_integration_id": "discourse"}}
    def reject(*args, **kwargs):
        assert kwargs["org_id"] == "o1" and kwargs["connector_id"] == "c1"
        raise ValueError("ownership mismatch")
    monkeypatch.setattr("app.services.managed_service_desk_tools.scoped_connection", reject)
    with pytest.raises(ToolAuthExpiredError):
        MANAGED_BUSINESS_TOOL_EXECUTORS["discourse.categories.list"](context(), {})
    proxy.assert_not_called()
