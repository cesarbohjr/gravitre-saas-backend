"""Domain → GA4/GSC property binding from tenant org profile."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.connector_resource_resolver import resolve_ga4_property
from app.services.domain_property_binding import match_resource_to_domain
from app.services.org_business_identity import (
    extract_domain_hint_from_message,
    load_org_business_identity,
    merge_business_identity,
)


class _OrgClient:
    def __init__(self, org_id: str, settings: dict) -> None:
        self.org_id = org_id
        self.settings = settings
        self.eq_ids: list[tuple[str, str]] = []
        self._table = ""

    def table(self, name: str) -> "_OrgClient":
        self._table = name
        return self

    def select(self, *_a, **_k) -> "_OrgClient":
        return self

    def eq(self, key: str, value: str) -> "_OrgClient":
        self.eq_ids.append((self._table, key, str(value)))
        return self

    def limit(self, _n: int) -> "_OrgClient":
        return self

    def execute(self) -> SimpleNamespace:
        if self._table == "organizations":
            wanted = next((v for t, k, v in reversed(self.eq_ids) if t == "organizations" and k == "id"), "")
            if wanted != self.org_id:
                return SimpleNamespace(data=[])
            return SimpleNamespace(data=[{"id": self.org_id, "settings": self.settings}])
        return SimpleNamespace(data=[])


def test_org_settings_load_is_tenant_scoped() -> None:
    client = _OrgClient("org-1", {"website": "https://acme.example", "timezone": "America/Los_Angeles"})
    identity = load_org_business_identity(client, "org-1")
    assert identity["host"] == "acme.example"
    assert identity["source"] == "org_settings"
    assert ("organizations", "id", "org-1") in client.eq_ids

    other = load_org_business_identity(client, "org-2")
    assert other["host"] == ""
    assert ("organizations", "id", "org-2") in client.eq_ids


def test_foreign_org_row_is_rejected() -> None:
    class _Mismatch:
        def table(self, _name: str) -> "_Mismatch":
            return self

        def select(self, *_a, **_k) -> "_Mismatch":
            return self

        def eq(self, *_a, **_k) -> "_Mismatch":
            return self

        def limit(self, _n: int) -> "_Mismatch":
            return self

        def execute(self) -> SimpleNamespace:
            return SimpleNamespace(data=[{"id": "org-evil", "settings": {"website": "https://evil.example"}}])

    identity = load_org_business_identity(_Mismatch(), "org-1")
    assert identity["host"] == ""


def test_message_hint_wins_over_org_profile() -> None:
    identity = merge_business_identity(
        org_id="org-1",
        context={"business_identity": {"website": "https://acme.example"}},
        user_message="Use gravitre.app for the traffic report.",
        client=None,
    )
    assert identity["host"] == "gravitre.app"
    assert identity["source"] == "user_message"


def test_extract_ignores_filenames() -> None:
    assert extract_domain_hint_from_message("see report.pdf please") == ""
    assert extract_domain_hint_from_message("https://gravitre.app/traffic") == "gravitre.app"


def test_unique_stream_uri_binds() -> None:
    matched = match_resource_to_domain(
        (
            {"property_id": "1", "display_name": "Alpha", "default_uri": "https://acme.example", "org_id": "org-1"},
            {"property_id": "2", "display_name": "Beta", "default_uri": "https://other.example", "org_id": "org-1"},
        ),
        host="acme.example",
        org_id="org-1",
    )
    assert matched is not None
    assert matched["property_id"] == "1"


def test_unique_display_label_binds() -> None:
    matched = match_resource_to_domain(
        (
            {"property_id": "1", "display_name": "Gravitre Website", "org_id": "org-1"},
            {"property_id": "2", "display_name": "Docs", "org_id": "org-1"},
            {"property_id": "3", "display_name": "Portal", "org_id": "org-1"},
        ),
        host="gravitre.app",
        org_id="org-1",
    )
    assert matched is not None
    assert matched["property_id"] == "1"


def test_non_unique_label_stays_unbound() -> None:
    matched = match_resource_to_domain(
        (
            {"property_id": "1", "display_name": "Gravitre", "org_id": "org-1"},
            {"property_id": "2", "display_name": "Gravitre Docs", "org_id": "org-1"},
        ),
        host="gravitre.app",
        org_id="org-1",
    )
    assert matched is None


def test_resolver_binds_from_org_profile_without_linked_config() -> None:
    conn = {"id": "conn-1", "config": {}, "environment": "production"}
    client = _OrgClient("org-1", {"website": "https://acme.example"})
    with patch(
        "app.services.connector_resource_resolver._connector_row",
        return_value=conn,
    ), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=("token", None),
    ), patch(
        "app.connectors.google_analytics.list_ga4_properties",
        return_value=[
            {"property_id": "111", "display_name": "Acme"},
            {"property_id": "222", "display_name": "Other brand"},
        ],
    ), patch(
        "app.connectors.google_analytics.list_ga4_web_stream_uris",
        side_effect=lambda _token, pid: ["https://acme.example"] if pid == "111" else ["https://other.example"],
    ):
        resolution = resolve_ga4_property(
            client=client,
            org_id="org-1",
            settings=SimpleNamespace(),
        )
    assert resolution.status == "resolved"
    assert resolution.resource_id == "111"
    assert resolution.resolution_reason == "tenant_domain_binding"


def test_resolver_does_not_bind_without_unique_match() -> None:
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
            {"property_id": "1", "display_name": "Site A"},
            {"property_id": "2", "display_name": "Site B"},
        ],
    ), patch(
        "app.connectors.google_analytics.list_ga4_web_stream_uris",
        return_value=[],
    ):
        resolution = resolve_ga4_property(
            client=object(),
            org_id="org-1",
            settings=SimpleNamespace(),
        )
    assert resolution.status == "ambiguous"
    assert resolution.candidate_count == 2
