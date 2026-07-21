"""Tests for connected vendor file read/search helpers."""
from __future__ import annotations

import json

import pytest

from app.services.connected_files_service import (
    build_file_citation_fields,
    chunk_connected_file_text,
    google_drive_search_hits,
    is_permission_sensitive_file_action,
    normalize_file_metadata,
)
from app.services.parameter_ledger import (
    bind_connected_file_args,
    get_ledger,
    ingest_connected_file_hits,
    ingest_message_slots,
    resolve_file_reference,
)
from app.services.read_action_result_cache import is_read_invoke_action


def test_permission_sensitive_actions_skip_read_cache():
    assert is_permission_sensitive_file_action("google_drive.search_files")
    assert is_permission_sensitive_file_action("microsoft365.get_file_content")
    assert not is_permission_sensitive_file_action("google_drive.files.list")
    assert not is_read_invoke_action("google_drive.search_files")
    assert is_read_invoke_action("google_drive.files.list")


def test_google_drive_search_normalization():
    hits = google_drive_search_hits(
        {
            "files": [
                {
                    "id": "abc123",
                    "name": "HubSpot Report Q3.pdf",
                    "mimeType": "application/pdf",
                    "modifiedTime": "2026-07-14T10:00:00Z",
                    "webViewLink": "https://drive.google.com/file/d/abc123/view",
                }
            ]
        }
    )
    assert len(hits) == 1
    assert hits[0]["file_id"] == "abc123"
    assert hits[0]["web_link"].startswith("https://drive.google.com")


def test_chunk_connected_file_text_reuses_rag_chunker():
    rows = chunk_connected_file_text("alpha beta gamma", metadata={"vendor": "google_drive"})
    assert rows
    assert rows[0]["content"]
    assert rows[0]["metadata"]["vendor"] == "google_drive"


def test_citation_fields_include_path_and_link():
    fields = build_file_citation_fields(
        {
            "vendor": "google_drive",
            "file_id": "abc",
            "path": "Reports/HubSpot Q3.pdf",
            "web_link": "https://drive.google.com/file/d/abc/view",
            "page": 2,
        }
    )
    assert fields["file_path"] == "Reports/HubSpot Q3.pdf"
    assert fields["web_link"].startswith("https://")
    assert fields["page"] == 2


def test_ledger_stores_search_hits_and_resolves_ordinals():
    hits = [
        normalize_file_metadata(vendor="google_drive", file_id="1", name="First"),
        normalize_file_metadata(vendor="google_drive", file_id="2", name="Second"),
    ]
    state = ingest_connected_file_hits({}, hits)
    ledger = get_ledger(state)
    assert ledger.get("file_id") == "1"
    refs = json.loads(ledger.get("file_refs_json") or "[]")
    assert len(refs) == 2
    assert resolve_file_reference("summarize the second one", ledger)["file_id"] == "2"


def test_bind_connected_file_args_from_ledger():
    state = ingest_connected_file_hits(
        {},
        [normalize_file_metadata(vendor="google_drive", file_id="xyz", name="Budget.xlsx")],
    )
    ledger = get_ledger(state)
    args = bind_connected_file_args("google_drive.get_file_content", {}, ledger)
    assert args["file_id"] == "xyz"


def test_ingest_message_slots_resolves_ordinal_follow_up():
    state = ingest_connected_file_hits(
        {},
        [
            normalize_file_metadata(vendor="google_drive", file_id="1", name="A"),
            normalize_file_metadata(vendor="google_drive", file_id="2", name="B"),
        ],
    )
    ledger = ingest_message_slots("what does the second one say about Q3?", ledger=get_ledger(state))
    assert ledger.get("file_id") == "2"
