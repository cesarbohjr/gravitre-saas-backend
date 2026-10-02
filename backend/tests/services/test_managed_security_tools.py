from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.managed_security_tools import (
    _okta_apps_list,
    _okta_groups_list,
    _okta_system_logs_list,
    _okta_user_factors_list,
    _okta_users_get,
)
from app.services.tool_types import ToolAuthExpiredError


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        client=MagicMock(),
        org_id="org-1",
        environment_name="production",
        connector_id=None,
        settings=SimpleNamespace(
            nango_secret_key="secret",
            nango_api_base_url="https://api.nango.dev",
        ),
    )


def _connector() -> dict:
    return {
        "id": "connector-1",
        "org_id": "org-1",
        "type": "okta",
        "status": "active",
        "config": {
            "auth_provider": "managed",
            "managed_connection_id": "okta-connection-1",
            "managed_integration_id": "okta",
        },
    }


def _response(data) -> httpx.Response:
    request = httpx.Request("GET", "https://api.nango.dev/proxy")
    return httpx.Response(200, json=data, request=request)


@patch("app.services.managed_security_tools.enforce_rate_limit")
@patch("app.services.managed_security_tools.proxy_request")
@patch("app.services.managed_security_tools.get_connector_by_type")
def test_okta_system_log_uses_managed_connection(get_by_type, proxy, _rate) -> None:
    get_by_type.return_value = _connector()
    proxy.return_value = _response([
        {"uuid": "event-1", "eventType": "user.session.start"},
        {"uuid": "event-2", "eventType": "user.risk.detect"},
    ])
    ctx = _ctx()

    result = _okta_system_logs_list(ctx, {"limit": 50})

    assert result.success is True
    assert result.data["count"] == 2
    kwargs = proxy.call_args.kwargs
    assert kwargs["method"] == "GET"
    assert kwargs["endpoint"] == "/api/v1/logs"
    assert kwargs["connection_id"] == "okta-connection-1"


@patch("app.services.managed_security_tools.enforce_rate_limit")
@patch("app.services.managed_security_tools.proxy_request")
@patch("app.services.managed_security_tools.get_connector_by_type")
def test_okta_user_get_uses_documented_user_route(get_by_type, proxy, _rate) -> None:
    get_by_type.return_value = _connector()
    proxy.return_value = _response({"id": "00u123", "status": "ACTIVE"})
    result = _okta_users_get(_ctx(), {"user_id": "00u123"})

    assert result.success is True
    assert result.data["id"] == "00u123"
    assert proxy.call_args.kwargs["endpoint"] == "/api/v1/users/00u123"


@patch("app.services.managed_security_tools.get_connector_by_type")
def test_okta_managed_connection_requires_connection_identity(get_by_type) -> None:
    connector = _connector()
    connector["config"] = {
        "auth_provider": "managed",
        "managed_integration_id": "okta",
    }
    get_by_type.return_value = connector

    with pytest.raises(ToolAuthExpiredError):
        _okta_users_get(_ctx(), {"user_id": "00u123"})


@pytest.mark.parametrize(
    ("executor", "params", "payload", "endpoint", "collection"),
    [
        (_okta_groups_list, {"limit": 25}, [{"id": "grp-1"}], "/api/v1/groups", "groups"),
        (_okta_apps_list, {"limit": 25}, [{"id": "app-1"}], "/api/v1/apps", "apps"),
        (
            _okta_user_factors_list,
            {"user_id": "00u123"},
            [{"id": "factor-1", "factorType": "push"}],
            "/api/v1/users/00u123/factors",
            "factors",
        ),
    ],
)
@patch("app.services.managed_security_tools.enforce_rate_limit")
@patch("app.services.managed_security_tools.proxy_request")
@patch("app.services.managed_security_tools.get_connector_by_type")
def test_okta_extended_security_reads_use_managed_proxy(
    get_by_type, proxy, _rate, executor, params, payload, endpoint, collection
) -> None:
    get_by_type.return_value = _connector()
    proxy.return_value = _response(payload)

    result = executor(_ctx(), params)

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data[collection][0]["id"] == payload[0]["id"]
    assert proxy.call_args.kwargs["method"] == "GET"
    assert proxy.call_args.kwargs["endpoint"] == endpoint
