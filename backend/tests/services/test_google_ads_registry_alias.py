"""Google Ads catalog→registry alias must not be shadowed by catalog HTTP stubs."""
from __future__ import annotations

from app.connectors.action_catalog.tool_aliases import resolve_registry_action
from app.connectors.catalog_http.registry import build_catalog_http_executors
from app.services.tool_service import _TOOL_REGISTRY, _resolve_tool_executor


def test_resolve_registry_action_prefers_googleads_dedicated_executor():
    registered = {
        "google_ads.accounts.list",  # broken catalog HTTP stub key
        "googleads.accounts.list",  # real dedicated executor
    }
    assert (
        resolve_registry_action("google_ads.accounts.list", registered)
        == "googleads.accounts.list"
    )


def test_resolve_registry_action_keeps_google_drive_long_form():
    registered = {
        "google_drive.search_files",
        "drive.search_files",  # orphan stub must not win
    }
    assert (
        resolve_registry_action("google_drive.search_files", registered)
        == "google_drive.search_files"
    )


def test_catalog_http_skips_google_ads_when_googleads_implemented():
    skip = {k for k in _TOOL_REGISTRY if k.startswith("googleads.")}
    built = build_catalog_http_executors(skip=skip)
    assert "google_ads.accounts.list" not in built
    assert "google_ads.structure.create" not in built
    assert "googleads.accounts.list" not in built
    assert "drive.search_files" not in built


def test_resolve_tool_executor_uses_dedicated_googleads_accounts_list():
    executor = _resolve_tool_executor("google_ads.accounts.list")
    assert executor is not None
    assert executor is _TOOL_REGISTRY["googleads.accounts.list"]


def test_structure_create_registered():
    assert "googleads.structure.create" in _TOOL_REGISTRY
    assert _resolve_tool_executor("google_ads.structure.create") is _TOOL_REGISTRY[
        "googleads.structure.create"
    ]
