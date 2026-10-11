"""Phase 1: HubSpot knowledge sync advances its cursor only to the last processed record."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from app.connectors.hubspot import list_notes_since
from app.services import hubspot_knowledge_sync_service as svc


def _client(config: dict) -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "c-hs", "name": "HubSpot", "config": config, "environment": "production", "status": "active"}]
    )
    return client


def _saved_config(client: MagicMock) -> dict:
    payload = client.table.return_value.update.call_args_list[-1][0][0]
    return payload["config"]


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def _note(rid: str, modified: str) -> dict:
    return {"id": rid, "properties": {"hs_note_body": f"n{rid}", "hs_lastmodifieddate": modified}}


def _run(client, notes, emails, *, ingest_side_effect=None, full_sync=False):
    ingest = MagicMock(side_effect=ingest_side_effect or (lambda *a, **k: {"id": f"job-{k['external_id']}"}))
    with patch.object(svc, "ensure_hubspot_access_token", return_value=("tok", None)), patch.object(
        svc, "ensure_hubspot_rag_source", return_value="src-1"
    ), patch.object(svc, "list_notes_since", notes), patch.object(svc, "list_emails_since", emails), patch.object(
        svc, "create_ingest_job", ingest
    ):
        result = svc.run_hubspot_knowledge_sync(client, "org-1", "c-hs", MagicMock(), actor_id="u", full_sync=full_sync)
    return result, ingest


def test_search_sorts_ascending_and_follows_after_token():
    pages = [
        {"results": [{"id": "1"}, {"id": "2"}], "paging": {"next": {"after": "2"}}},
        {"results": [{"id": "3"}]},
    ]
    with patch("app.connectors.hubspot._request", side_effect=pages) as req:
        items = list_notes_since("tok", since_ms=1000, limit=500)
    assert [i["id"] for i in items] == ["1", "2", "3"]
    first, second = req.call_args_list
    assert first[1]["json_body"]["sorts"] == [{"propertyName": "hs_lastmodifieddate", "direction": "ASCENDING"}]
    assert "after" not in first[1]["json_body"]
    assert second[1]["json_body"]["after"] == "2"


def test_search_stops_at_cap():
    page = {"results": [{"id": str(i)} for i in range(100)], "paging": {"next": {"after": "x"}}}
    with patch("app.connectors.hubspot._request", return_value=page) as req:
        items = list_notes_since("tok", since_ms=None, limit=150)
    assert len(items) == 150
    assert req.call_count == 2


def test_cursor_advances_to_last_processed_record_not_wall_clock():
    client = _client({"hubspot_last_synced_at": "2026-10-01T00:00:00+00:00"})
    notes = MagicMock(return_value=[_note("1", "2026-10-01T01:00:00Z"), _note("2", "2026-10-01T02:00:00.500Z")])
    result, _ = _run(client, notes, MagicMock(return_value=[]))
    cursors = _saved_config(client)["hubspot_sync_cursors"]
    assert cursors["note"]["since_ms"] == _ms("2026-10-01T02:00:00.500+00:00")
    assert cursors["note"]["ids_at_since"] == ["2"]
    assert result["pages_synced"] == 2
    # First run fell back to the legacy run timestamp as the since window.
    assert notes.call_args[1]["since_ms"] == _ms("2026-10-01T00:00:00+00:00")


def test_ingest_failure_stops_cursor_before_failed_record():
    client = _client({"hubspot_sync_cursors": {"note": {"since_ms": 1000, "ids_at_since": []}}})
    notes = MagicMock(
        return_value=[_note("1", "2000"), _note("2", "3000"), _note("3", "4000")]
    )

    def ingest(*_a, **k):
        if k["external_id"].endswith(":2"):
            raise RuntimeError("db down")
        return {"id": "job"}

    result, ingest_mock = _run(client, notes, MagicMock(return_value=[]), ingest_side_effect=ingest)
    cursors = _saved_config(client)["hubspot_sync_cursors"]
    assert cursors["note"] == {"since_ms": 2000, "ids_at_since": ["1"]}
    assert ingest_mock.call_count == 2  # record 3 is not attempted past the failure
    assert result["has_more"] is True
    assert any("note 2" in e for e in result["errors"])


def test_fetch_error_keeps_existing_cursor():
    from app.connectors.hubspot import HubSpotAPIError

    existing = {"note": {"since_ms": 5000, "ids_at_since": ["9"]}, "email": {"since_ms": 7000, "ids_at_since": []}}
    client = _client({"hubspot_sync_cursors": existing})
    result, _ = _run(
        client,
        MagicMock(side_effect=HubSpotAPIError("boom")),
        MagicMock(return_value=[{"id": "e1", "properties": {"hs_email_subject": "s", "hs_lastmodifieddate": "8000"}}]),
    )
    cursors = _saved_config(client)["hubspot_sync_cursors"]
    assert cursors["note"] == {"since_ms": 5000, "ids_at_since": ["9"]}
    assert cursors["email"] == {"since_ms": 8000, "ids_at_since": ["e1"]}
    assert result["errors"]


def test_boundary_record_already_processed_is_not_requeued_and_cap_resumes():
    client = _client({"hubspot_sync_cursors": {"note": {"since_ms": 5000, "ids_at_since": ["9"]}}})
    notes = MagicMock(return_value=[_note("9", "5000"), _note("10", "5000"), _note("11", "6000")])
    with patch.object(svc, "MAX_OBJECTS_PER_SYNC", 3):
        result, ingest = _run(client, notes, MagicMock(return_value=[]))
    queued = [c[1]["external_id"] for c in ingest.call_args_list]
    assert queued == ["hubspot:note:10", "hubspot:note:11"]
    assert notes.call_args[1]["since_ms"] == 5000
    assert _saved_config(client)["hubspot_sync_cursors"]["note"] == {"since_ms": 6000, "ids_at_since": ["11"]}
    assert result["has_more"] is True


def test_full_page_at_one_timestamp_reports_stall_instead_of_silently_looping():
    client = _client({"hubspot_sync_cursors": {"note": {"since_ms": 5000, "ids_at_since": ["1", "2"]}}})
    notes = MagicMock(return_value=[_note("1", "5000"), _note("2", "5000")])
    with patch.object(svc, "MAX_OBJECTS_PER_SYNC", 2):
        result, ingest = _run(client, notes, MagicMock(return_value=[]))
    ingest.assert_not_called()
    assert any("cursor_stalled" in e for e in result["errors"])
    assert _saved_config(client)["hubspot_sync_cursors"]["note"]["since_ms"] == 5000
