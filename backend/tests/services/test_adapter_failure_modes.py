"""Phase A verification — adapter/resolver typed failure states."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.connectors.google_analytics import GoogleAnalyticsAPIError
from app.connectors.google_search_console import GoogleSearchConsoleAPIError
from app.services.connector_resource_resolver import resolve_ga4_property, resolve_resource


def test_ga4_not_configured() -> None:
    with patch("app.services.connector_resource_resolver._connector_row", return_value=None):
        res = resolve_ga4_property(client=object(), org_id="o", settings=SimpleNamespace())
    assert res.status == "not_found"
    assert res.resolution_reason == "connector_not_configured"


def test_ga4_auth_failed() -> None:
    conn = {"id": "c1", "config": {}}
    with patch("app.services.connector_resource_resolver._connector_row", return_value=conn), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=(None, "auth_failed"),
    ):
        res = resolve_ga4_property(client=object(), org_id="o", settings=SimpleNamespace())
    assert res.status == "not_authorized"


def test_ga4_api_unavailable() -> None:
    conn = {"id": "c1", "config": {}}
    with patch("app.services.connector_resource_resolver._connector_row", return_value=conn), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=("token", None),
    ), patch(
        "app.connectors.google_analytics.list_ga4_properties",
        side_effect=GoogleAnalyticsAPIError("timeout"),
    ):
        res = resolve_ga4_property(client=object(), org_id="o", settings=SimpleNamespace())
    assert res.status == "unavailable"


def test_gsc_auth_failed() -> None:
    conn = {"id": "c1", "config": {}}
    with patch("app.services.connector_resource_resolver._connector_row", return_value=conn), patch(
        "app.connectors.google_vendor_oauth.ensure_google_vendor_session",
        return_value=(None, "expired"),
    ):
        res = resolve_resource(
            connector_id="google_search_console",
            client=object(),
            org_id="o",
            settings=SimpleNamespace(),
        )
    assert res.status == "not_authorized"


def test_unimplemented_vendor_typed_unavailable() -> None:
    conn = {"id": "c1", "config": {}}
    with patch("app.services.connector_resource_resolver._connector_row", return_value=conn):
        res = resolve_resource(
            connector_id="zendesk",
            client=object(),
            org_id="o",
            settings=SimpleNamespace(),
        )
    assert res.status == "unavailable"
    assert res.resolution_reason == "resolver_not_implemented"
