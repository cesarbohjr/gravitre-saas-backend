"""Resource auto-resolution — GA4 property selection."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.connector_resource_resolver import resolve_ga4_property


def test_resolve_ga4_property_from_linked_config() -> None:
    conn = {
        "id": "conn-1",
        "config": {"property_id": "123456", "property_name": "Gravitre Website"},
    }
    with patch(
        "app.services.connector_resource_resolver._connector_row",
        return_value=conn,
    ):
        resolution = resolve_ga4_property(
            client=object(),
            org_id="org-1",
            settings=SimpleNamespace(),
        )
    assert resolution.status == "resolved"
    assert resolution.resource_id == "123456"
    assert resolution.display_name == "Gravitre Website"
    assert resolution.candidate_count == 1


def test_resolve_ga4_property_single_discovered() -> None:
    conn = {"id": "conn-1", "config": {}}
    with patch(
        "app.services.connector_resource_resolver._connector_row",
        return_value=conn,
    ), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=("token", None),
    ), patch(
        "app.connectors.google_analytics.list_ga4_properties",
        return_value=[{"property_id": "999", "display_name": "Only Site"}],
    ):
        resolution = resolve_ga4_property(
            client=object(),
            org_id="org-1",
            settings=SimpleNamespace(),
        )
    assert resolution.status == "resolved"
    assert resolution.resource_id == "999"


def test_resolve_ga4_property_ambiguous() -> None:
    conn = {"id": "conn-1", "config": {}}
    with patch(
        "app.services.connector_resource_resolver._connector_row",
        return_value=conn,
    ), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=("token", None),
    ), patch(
        "app.connectors.google_analytics.list_ga4_properties",
        return_value=[
            {"property_id": "1", "display_name": "Gravitre"},
            {"property_id": "2", "display_name": "Docs"},
            {"property_id": "3", "display_name": "Portal"},
        ],
    ):
        resolution = resolve_ga4_property(
            client=object(),
            org_id="org-1",
            settings=SimpleNamespace(),
        )
    assert resolution.status == "ambiguous"
    assert resolution.candidate_count == 3
