"""Phase 1: Zendesk knowledge sync paginates oldest-first and advances only to the last processed ticket."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import zendesk_knowledge_sync_service as svc


def _client(config: dict) -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "c-zd", "name": "Zendesk", "config": config, "environment": "production", "status": "active"}]
    )
    return client


def _saved_config(client: MagicMock) -> dict:
    return client.table.return_value.update.call_args_list[-1][0][0]["config"]


def _ticket(tid: int, updated: str) -> dict:
    return {"id": tid, "subject": f"T{tid}", "status": "solved", "updated_at": updated}


def _run(client, tickets, *, ingest_side_effect=None):
    ingest = MagicMock(side_effect=ingest_side_effect or (lambda *a, **k: {"id": "job"}))
    fetch = MagicMock(return_value=tickets)
    with patch.object(svc, "_zendesk_credentials", return_value=("acme", "a@b.com", "tok")), patch.object(
        svc, "ensure_zendesk_rag_source", return_value="src-1"
    ), patch.object(svc, "fetch_solved_tickets_since", fetch), patch.object(svc, "create_ingest_job", ingest):
        result = svc.run_zendesk_knowledge_sync(client, "org-1", "c-zd", MagicMock(), actor_id="u")
    return result, fetch, ingest


def test_fetch_sorts_ascending_and_paginates_to_cap():
    pages = [
        {"results": [{"id": i, "result_type": "ticket"} for i in range(100)], "next_page": "p2"},
        {"results": [{"id": i, "result_type": "ticket"} for i in range(100, 200)], "next_page": "p3"},
    ]
    with patch.object(svc, "zendesk_request", side_effect=pages) as req:
        tickets = svc.fetch_solved_tickets_since("acme", "a", "t", since_iso="2026-10-01T00:00:00Z", max_records=150)
    assert len(tickets) == 150
    assert req.call_count == 2
    params = req.call_args_list[0][1]["params"]
    assert params["sort_by"] == "updated_at" and params["sort_order"] == "asc"
    assert params["query"] == "type:ticket status:solved updated>=2026-10-01T00:00:00Z"
    assert req.call_args_list[1][1]["params"]["page"] == 2


def test_cursor_advances_to_last_processed_ticket():
    client = _client({"zendesk_sync_cursor": {"updated_at": "2026-10-01T00:00:00Z", "ids_at_since": []}})
    result, fetch, _ = _run(client, [_ticket(1, "2026-10-01T01:00:00Z"), _ticket(2, "2026-10-01T02:00:00Z")])
    assert fetch.call_args[1]["since_iso"] == "2026-10-01T00:00:00Z"
    assert _saved_config(client)["zendesk_sync_cursor"] == {"updated_at": "2026-10-01T02:00:00Z", "ids_at_since": ["2"]}
    assert result["pages_synced"] == 2


def test_ingest_failure_keeps_cursor_at_last_success():
    client = _client({"zendesk_sync_cursor": {"updated_at": "2026-10-01T00:00:00Z", "ids_at_since": []}})

    def ingest(*_a, **k):
        if k["external_id"] == "zendesk:ticket:2":
            raise RuntimeError("db down")
        return {"id": "job"}

    result, _, ingest_mock = _run(
        client,
        [_ticket(1, "2026-10-01T01:00:00Z"), _ticket(2, "2026-10-01T02:00:00Z"), _ticket(3, "2026-10-01T03:00:00Z")],
        ingest_side_effect=ingest,
    )
    assert _saved_config(client)["zendesk_sync_cursor"] == {"updated_at": "2026-10-01T01:00:00Z", "ids_at_since": ["1"]}
    assert ingest_mock.call_count == 2
    assert result["has_more"] is True and result["errors"]


def test_boundary_ticket_not_requeued():
    client = _client({"zendesk_sync_cursor": {"updated_at": "2026-10-01T05:00:00Z", "ids_at_since": ["7"]}})
    _, _, ingest = _run(client, [_ticket(7, "2026-10-01T05:00:00Z"), _ticket(8, "2026-10-01T05:00:00Z")])
    assert [c[1]["external_id"] for c in ingest.call_args_list] == ["zendesk:ticket:8"]
    assert _saved_config(client)["zendesk_sync_cursor"] == {"updated_at": "2026-10-01T05:00:00Z", "ids_at_since": ["7", "8"]}


def test_legacy_run_timestamp_used_when_no_cursor():
    client = _client({"zendesk_last_synced_at": "2026-10-01T10:30:00+00:00"})
    _, fetch, _ = _run(client, [])
    assert fetch.call_args[1]["since_iso"] == "2026-10-01T10:30:00Z"
    assert _saved_config(client)["zendesk_sync_cursor"]["updated_at"] == "2026-10-01T10:30:00Z"


def test_full_page_at_one_instant_reports_stall_instead_of_silently_looping():
    client = _client({"zendesk_sync_cursor": {"updated_at": "2026-10-01T05:00:00Z", "ids_at_since": ["1", "2"]}})
    with patch.object(svc, "MAX_TICKETS_PER_SYNC", 2):
        result, _, ingest = _run(client, [_ticket(1, "2026-10-01T05:00:00Z"), _ticket(2, "2026-10-01T05:00:00Z")])
    ingest.assert_not_called()
    assert any("cursor_stalled" in e for e in result["errors"])
