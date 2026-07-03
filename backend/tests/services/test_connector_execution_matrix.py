"""Tests for connector execution matrix."""
from __future__ import annotations

from app.services.connector_execution_matrix import (
    build_connector_execution_matrix,
    chat_executable_entries,
    get_matrix_entry,
    matrix_summary,
)


def test_matrix_covers_priority_vendors():
    summary = matrix_summary()
    by_vendor = summary["byVendor"]
    for vendor in ("monday", "google_drive", "gmail", "hubspot", "slack", "jira"):
        assert vendor in by_vendor
        assert by_vendor[vendor]["executable"] == by_vendor[vendor]["total"]


def test_monday_items_create_executable():
    entry = get_matrix_entry("monday", "monday.items.create")
    assert entry is not None
    assert entry.implementation_status != "not_implemented"
    assert entry.registry_key == "monday.items.create"
    assert entry.chat_executable is True
    assert entry.requires_approval is True


def test_google_drive_list_executable_with_alias():
    entry = get_matrix_entry("google_drive", "google_drive.files.list")
    assert entry is not None
    assert entry.registry_key in {"drive.files.list", "google_drive.files.list"}
    assert entry.kind == "read"


def test_chat_executable_filters_connected():
    all_entries = chat_executable_entries(connected_integrations=["hubspot", "slack"])
    vendors = {entry.connector_id for entry in all_entries}
    assert "hubspot" in vendors
    assert "slack" in vendors
    assert "zendesk" not in vendors


def test_matrix_entry_count_matches_catalog():
    entries = build_connector_execution_matrix()
    assert len(entries) >= 500
    assert all(entry.action_key for entry in entries)
