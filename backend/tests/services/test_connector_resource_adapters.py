"""Provider resource adapter smoke tests."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.connector_resource_adapters import (
    resolve_connection_only,
    resolve_github,
    resolve_hubspot,
    resolve_quickbooks,
    resolve_slack,
)


def test_hubspot_linked_portal() -> None:
    conn = {"id": "c1", "config": {"portal_id": "12345"}}
    res = resolve_hubspot(
        client=object(),
        org_id="org",
        settings=SimpleNamespace(),
        conn=conn,
        environment_name="default",
    )
    assert res.status == "resolved"
    assert res.resource_id == "12345"


def test_slack_single_connection() -> None:
    conn = {"id": "c1", "config": {}}
    res = resolve_slack(conn=conn)
    assert res.status == "resolved"
    assert res.resource_type == "workspace"


def test_github_org_from_config() -> None:
    conn = {"id": "c1", "config": {"org": "gravitre-ai"}}
    res = resolve_github(conn=conn)
    assert res.status == "resolved"
    assert res.resource_id == "gravitre-ai"


def test_quickbooks_realm() -> None:
    conn = {"id": "c1", "config": {"realm_id": "999"}}
    res = resolve_quickbooks(
        client=object(),
        org_id="org",
        settings=SimpleNamespace(),
        conn=conn,
        environment_name="default",
    )
    assert res.status == "resolved"
    assert res.resource_id == "999"


def test_connection_only_fallback() -> None:
    conn = {"id": "conn-x", "name": "Primary HubSpot"}
    res = resolve_connection_only(connector_id="hubspot", conn=conn)
    assert res.status == "resolved"
    assert res.resource_id == "conn-x"
