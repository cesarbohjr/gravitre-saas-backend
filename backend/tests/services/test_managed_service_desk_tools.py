from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.managed_service_desk_tools import (
    _freshservice_ticket_activities,
    _freshservice_ticket_update_status,
    _freshservice_tickets_get,
    _freshservice_tickets_list,
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
        "type": "freshservice",
        "status": "active",
        "config": {
            "auth_provider": "managed",
            "managed_connection_id": "nango-connection-1",
            "managed_integration_id": "freshservice",
        },
    }


def _response(data: dict) -> httpx.Response:
    request = httpx.Request("GET", "https://api.nango.dev/proxy")
    return httpx.Response(200, json=data, request=request)


@patch("app.services.managed_service_desk_tools.enforce_rate_limit")
@patch("app.services.managed_service_desk_tools.proxy_request")
@patch("app.services.managed_service_desk_tools.get_connector_by_type")
def test_freshservice_list_uses_org_scoped_managed_connection(
    get_by_type, proxy, _rate
) -> None:
    get_by_type.return_value = _connector()
    proxy.return_value = _response({"tickets": [{"id": 12}, {"id": 13}]})

    ctx = _ctx()
    result = _freshservice_tickets_list(ctx, {"status": 2, "per_page": 25})

    assert result.success is True
    assert result.data["count"] == 2
    get_by_type.assert_called_once_with(
        ctx.client, "org-1", "freshservice", environment_name="production"
    )
    kwargs = proxy.call_args.kwargs
    assert kwargs["connection_id"] == "nango-connection-1"
    assert kwargs["integration_id"] == "freshservice"
    assert kwargs["endpoint"] == "/api/v2/tickets"
    assert kwargs["method"] == "GET"


@patch("app.services.managed_service_desk_tools.enforce_rate_limit")
@patch("app.services.managed_service_desk_tools.proxy_request")
@patch("app.services.managed_service_desk_tools.get_connector_by_type")
def test_freshservice_get_and_activities_use_documented_ticket_routes(
    get_by_type, proxy, _rate
) -> None:
    get_by_type.return_value = _connector()
    proxy.side_effect = [
        _response({"ticket": {"id": 42, "status": 2}}),
        _response({"activities": [{"id": 1}]}),
    ]
    ctx = _ctx()

    ticket = _freshservice_tickets_get(ctx, {"ticket_id": 42, "include": "stats"})
    activity = _freshservice_ticket_activities(ctx, {"ticket_id": 42})

    assert ticket.data["id"] == "42"
    assert activity.data["ticket_id"] == "42"
    assert proxy.call_args_list[0].kwargs["endpoint"] == "/api/v2/tickets/42"
    assert proxy.call_args_list[1].kwargs["endpoint"] == "/api/v2/tickets/42/activities"


@patch("app.services.managed_service_desk_tools.enforce_rate_limit")
@patch("app.services.managed_service_desk_tools.proxy_request")
@patch("app.services.managed_service_desk_tools.get_connector_by_type")
def test_freshservice_status_write_returns_verifiable_entity(
    get_by_type, proxy, _rate
) -> None:
    get_by_type.return_value = _connector()
    proxy.return_value = _response({"ticket": {"id": 42, "status": 3}})
    ctx = _ctx()

    result = _freshservice_ticket_update_status(ctx, {"ticket_id": 42, "status": 3})

    assert result.success is True
    assert result.data["id"] == "42"
    assert result.data["ticket"]["status"] == 3
    assert result.data["outcome_effect"] == "updated"
    kwargs = proxy.call_args.kwargs
    assert kwargs["method"] == "PUT"
    assert kwargs["endpoint"] == "/api/v2/tickets/42"
    assert kwargs["json_body"] == {"status": 3}


@patch("app.services.managed_service_desk_tools.get_connector_by_type")
def test_managed_service_desk_action_fails_when_connection_identity_missing(
    get_by_type,
) -> None:
    connector = _connector()
    connector["config"] = {
        "auth_provider": "managed",
        "managed_integration_id": "freshservice",
    }
    get_by_type.return_value = connector

    with pytest.raises(ToolAuthExpiredError):
        _freshservice_tickets_get(_ctx(), {"ticket_id": 42})


@pytest.mark.parametrize('field,value', [('org_id','other-org'),('environment','staging'),('status','pending_auth')])
@patch("app.services.managed_service_desk_tools.proxy_request")
@patch("app.services.managed_service_desk_tools.get_connector_by_type")
def test_managed_executor_rejects_wrong_scope_or_inactive(get_by_type,proxy,field,value):
    from app.services.tool_types import ToolValidationError
    row = _connector(); row[field] = value
    get_by_type.return_value = row
    with pytest.raises((ToolValidationError,ToolAuthExpiredError)):
        _freshservice_tickets_list(_ctx(),{})
    proxy.assert_not_called()


@pytest.mark.parametrize('ticket_id',['../users','42/activities','0','https://example.com',True])
def test_managed_ticket_path_cannot_be_injected(ticket_id):
    from app.services.tool_types import ToolValidationError
    with pytest.raises(ToolValidationError):
        _freshservice_tickets_get(_ctx(),{'ticket_id':ticket_id})
