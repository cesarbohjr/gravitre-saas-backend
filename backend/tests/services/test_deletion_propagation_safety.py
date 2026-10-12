"""Deletion propagation never mass-deletes, honours dry-run, and cannot be undone by a queued job.

Each test here started as a reviewer probe that reproduced an unsafe behaviour (empty or
truncated Notion listings read as "everything deleted", hard deletes under
SOURCE_PURGE_DRY_RUN, deleted tickets resurrected by queued ingest jobs, the Zendesk
deleted-tickets window stuck above 1000 deletions, ...). They now assert the safe one.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.connectors import confluence as cc
from app.connectors import notion as nc
from app.services import confluence_sync_service as conf
from app.services import hubspot_knowledge_sync_service as hs
from app.services import notion_sync_service as ns
from app.services import source_lifecycle as sl
from app.services import zendesk_knowledge_sync_service as zd
from tests.services.test_incremental_deletion_propagation import (
    CONN,
    DRY,
    ON,
    ORG,
    OTHER_ORG,
    SRC,
    _client,
    _doc,
    _doc_ids,
    _run_confluence,
    _run_hubspot,
    _run_zendesk,
    _saved_config,
)


@pytest.fixture(autouse=True)
def audits(monkeypatch):
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr("app.workflows.audit.write_audit_event", lambda client, **kw: rows.append(kw))
    return rows


def _actions(rows: list[dict[str, Any]]) -> list[str]:
    return [r["action"] for r in rows]


def _notion(client, settings, *, api_body=None, query=None, get_page=None):
    """Run a Notion sync with the HTTP layer faked at the narrowest useful point."""
    patches = [
        patch.object(ns, "ensure_notion_session", return_value=("tok", None)),
        patch.object(ns, "ensure_notion_rag_source", return_value=SRC),
        patch.object(ns, "export_page_text", return_value=("t", "b", None)),
        patch.object(ns, "_queue_page_ingest", MagicMock(return_value="job")),
    ]
    if api_body is not None:
        patches.append(patch.object(nc, "api_request", return_value=api_body))
    if query is not None:
        patches.append(patch.object(nc, "query_database", side_effect=query))
    if get_page is not None:
        patches.append(patch.object(ns, "get_page", side_effect=get_page))
    for p in patches:
        p.start()
    try:
        return ns.run_notion_sync(client, ORG, CONN, settings, actor_id="u")
    finally:
        for p in reversed(patches):
            p.stop()


def _live_page(_tok, _pid):
    return {"object": "page", "archived": False, "in_trash": False}


def _deleted_page(_tok, pid):
    raise nc.NotionAPIError("Notion API 404", status_code=404)


_DB = {"notion_sync_targets": [{"id": "db1", "type": "database"}]}


# ------------------------------------------------------------------ Notion full sweep (F1)


@pytest.mark.parametrize(
    "body",
    [{}, {"results": [], "has_more": False}, {"object": "error"}, {"object": "list", "results": None, "has_more": False}],
)
def test_notion_malformed_database_listing_deletes_nothing_and_reports_it(body, audits):
    client = _client(dict(_DB), [_doc(f"d{i}", f"notion:page:p{i}") for i in range(5)])
    result = _notion(client, ON, api_body=body, get_page=_deleted_page)
    assert any("malformed listing" in e for e in result["errors"])
    assert len(_doc_ids(client)) == 5 and result["documents_removed"] == 0
    assert audits == []


def test_notion_has_more_without_cursor_is_incomplete_and_deletes_nothing():
    client = _client(dict(_DB), [_doc(f"d{i}", f"notion:page:p{i}") for i in range(4)])
    first = {"object": "list", "results": [{"object": "page", "id": "p0"}], "has_more": True, "next_cursor": None}
    result = _notion(client, ON, query=[first], get_page=_deleted_page)
    assert any("next_cursor" in e for e in result["errors"])
    assert len(_doc_ids(client)) == 4 and result["documents_removed"] == 0


def test_notion_repeated_cursor_is_incomplete():
    page = {"object": "list", "results": [], "has_more": True, "next_cursor": "c1"}
    with patch.object(nc, "query_database", return_value=page), pytest.raises(nc.NotionListingIncomplete):
        nc.collect_database_page_ids("tok", "db1")


def test_notion_complete_multi_page_listing_is_read_in_full():
    pages = [
        {"object": "list", "results": [{"object": "page", "id": "a"}], "has_more": True, "next_cursor": "c1"},
        {"object": "list", "results": [{"object": "page", "id": "b"}], "has_more": False, "next_cursor": None},
    ]
    with patch.object(nc, "query_database", side_effect=pages) as q:
        assert nc.collect_database_page_ids("tok", "db1") == ["a", "b"]
    assert q.call_args_list[1].kwargs["start_cursor"] == "c1"


def test_notion_complete_empty_listing_removes_only_pages_notion_confirms_gone():
    docs = [_doc(f"d{i}", f"notion:page:p{i}") for i in range(5)]
    client = _client(dict(_DB), docs)
    empty = {"object": "list", "results": [], "has_more": False, "next_cursor": None}

    def get_page(_tok, pid):
        if pid == "p3":
            raise nc.NotionAPIError("Notion API 404", status_code=404)
        return {"object": "page", "in_trash": pid == "p4"}

    result = _notion(client, ON, query=[empty], get_page=get_page)
    # Absence alone removed nothing: p0-p2 still exist in Notion and are kept.
    assert _doc_ids(client) == ["d0", "d1", "d2"]
    assert result["documents_removed"] == 2 and result["errors"] == []


def test_notion_target_removed_from_config_is_out_of_scope_not_deleted():
    client = _client({"notion_sync_targets": [{"id": "p1", "type": "page"}]}, [
        _doc("d1", "notion:page:p1"),
        _doc("d2", "notion:page:p2"),
    ])
    result = _notion(client, ON, get_page=_live_page)
    assert _doc_ids(client) == ["d1", "d2"] and result["documents_removed"] == 0


def test_notion_safety_cap_refuses_a_mass_removal(audits):
    client = _client(dict(_DB), [_doc(f"d{i}", f"notion:page:p{i}") for i in range(10)])
    empty = {"object": "list", "results": [], "has_more": False, "next_cursor": None}
    # e.g. a reconnect to a different workspace: every page 404s.
    result = _notion(client, ON, query=[empty], get_page=_deleted_page)
    assert len(_doc_ids(client)) == 10 and result["documents_removed"] == 0
    assert any("refused to remove 10 of 10" in e for e in result["errors"])
    assert _actions(audits) == ["source.documents_removal_refused"]


def test_notion_safety_cap_allows_a_normal_deletion_rate():
    docs = [_doc(f"d{i:02d}", f"notion:page:p{i:02d}") for i in range(40)]
    client = _client(dict(_DB), docs)
    listing = {
        "object": "list",
        "results": [{"object": "page", "id": f"p{i:02d}"} for i in range(30)],
        "has_more": False,
        "next_cursor": None,
    }

    def get_page(_tok, pid):
        if int(pid[1:]) >= 30:
            raise nc.NotionAPIError("Notion API 404", status_code=404)
        return {"object": "page"}

    result = _notion(client, ON, query=[listing], get_page=get_page)
    assert result["documents_removed"] == 10 and len(_doc_ids(client)) == 30  # 10 of 40 = 25%


def test_notion_page_target_404_is_not_an_error_and_is_removed_under_the_cap():
    client = _client({"notion_sync_targets": [{"id": "p1", "type": "page"}, {"id": "p2", "type": "page"}]}, [
        _doc("d1", "notion:page:p1"),
        _doc("d2", "notion:page:p2"),
    ])

    def get_page(_tok, pid):
        if pid == "p2":
            raise nc.NotionAPIError("Notion API 404", status_code=404)
        return {"object": "page"}

    result = _notion(client, ON, get_page=get_page)
    assert result["errors"] == [] and _doc_ids(client) == ["d1"]


def test_notion_transport_error_aborts_without_deleting():
    client = _client(dict(_DB), [_doc(f"d{i}", f"notion:page:p{i}") for i in range(3)])
    with pytest.raises(httpx.ConnectError):
        _notion(client, ON, query=httpx.ConnectError("down"))
    assert len(_doc_ids(client)) == 3


def test_notion_429_records_error_and_keeps_docs():
    client = _client(dict(_DB), [_doc(f"d{i}", f"notion:page:p{i}") for i in range(3)])
    result = _notion(client, ON, query=nc.NotionAPIError("429", status_code=429), get_page=_deleted_page)
    assert result["errors"] and len(_doc_ids(client)) == 3


def test_notion_removal_failure_is_reported_not_raised():
    client = _client({"notion_sync_targets": [{"id": "p1", "type": "page"}]}, [_doc("d1", "notion:page:p1")])
    with patch.object(ns, "get_page", return_value={"in_trash": True}), patch(
        "app.services.source_lifecycle.remove_source_documents", side_effect=RuntimeError("db down")
    ), patch.object(ns, "ensure_notion_session", return_value=("tok", None)), patch.object(
        ns, "ensure_notion_rag_source", return_value=SRC
    ):
        result = ns.run_notion_sync(client, ORG, CONN, ON, actor_id="u")
    assert any("removed pages" in e for e in result["errors"])
    assert "notion_last_synced_at" in _saved_config(client)


def test_reconcile_requires_a_proven_complete_sweep():
    client = _client({}, [_doc("d1", "notion:page:p1")])
    removed = sl.reconcile_source_documents(
        client,
        ON,
        org_id=ORG,
        source_id=SRC,
        external_id_prefix="notion:page:",
        seen_external_ids=set(),
        is_gone=lambda ext: True,
        sweep_complete=False,
    )
    assert removed == 0 and _doc_ids(client) == ["d1"]


def test_reconcile_rotates_its_bounded_verification():
    client = _client({}, [_doc(f"d{i}", f"notion:page:p{i}") for i in range(5)])
    position: dict[str, Any] = {}
    checked: list[str] = []
    kw: dict[str, Any] = {
        "org_id": ORG,
        "source_id": SRC,
        "external_id_prefix": "notion:page:",
        "seen_external_ids": set(),
        "is_gone": lambda ext: checked.append(ext) or False,
        "sweep_complete": True,
        "max_verifications": 2,
        "position": position,
    }
    for _ in range(3):
        sl.reconcile_source_documents(client, ON, **kw)
    assert checked == [f"notion:page:p{i}" for i in range(5)] + ["notion:page:p0"]


def test_list_source_documents_pages_past_one_read(monkeypatch):
    monkeypatch.setattr(sl, "DOCUMENT_PAGE_SIZE", 2)
    client = _client({}, [_doc(f"d{i}", f"notion:page:p{i}") for i in range(5)])
    rows = sl.list_source_documents(client, org_id=ORG, source_id=SRC, external_id_prefix="notion:page:")
    assert sorted(r["id"] for r in rows) == [f"d{i}" for i in range(5)]


# ------------------------------------------------------------------ dry-run and receipts (F2)


@pytest.mark.parametrize("dry", [DRY, SimpleNamespace(source_deletion_propagation_enabled=True, source_purge_dry_run="false")])
def test_dry_run_plans_records_and_deletes_nothing(dry, audits):
    client = _client({}, [_doc("d1", "zendesk:ticket:1")])
    client.tables["rag_ingest_jobs"] = [
        {"id": "j1", "org_id": ORG, "source_id": SRC, "external_id": "zendesk:ticket:1", "status": "queued"}
    ]
    assert sl.remove_source_documents(client, dry, org_id=ORG, source_id=SRC, external_ids={"zendesk:ticket:1"}) == 0
    assert _doc_ids(client) == ["d1"] and client.tables["rag_ingest_jobs"][0]["status"] == "queued"
    assert _actions(audits) == ["source.documents_removal_planned"]
    meta = audits[0]["metadata"]
    assert meta["documents"] == 1 and meta["ingest_jobs"] == 1 and meta["dry_run"] is True
    assert audits[0]["resource_id"] == SRC and audits[0]["resource_type"] == "rag_source"


def test_live_removal_writes_a_receipt(audits):
    client = _client({}, [_doc("d1", "zendesk:ticket:1")])
    assert sl.remove_source_documents(client, ON, org_id=ORG, source_id=SRC, external_ids={"zendesk:ticket:1"}) == 1
    assert _actions(audits) == ["source.documents_removed"]
    assert audits[0]["metadata"]["external_ids"] == ["zendesk:ticket:1"] and audits[0]["metadata"]["dry_run"] is False


def test_zendesk_dry_run_does_not_advance_the_deleted_window():
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, [_doc("t1", "zendesk:ticket:1")])
    page = {"deleted_tickets": [{"id": 1, "deleted_at": "2026-10-05T00:00:00Z"}], "next_page": None}
    result, _ = _run_zendesk(client, DRY, deleted_pages=[page])
    assert result["documents_removed"] == 0 and _doc_ids(client) == ["t1"]
    # Nothing planned is skipped once dry-run is switched off.
    assert _saved_config(client)[zd.DELETED_CURSOR_CONFIG_KEY] == "2026-10-01T00:00:00Z"
    result, _ = _run_zendesk(client, ON, deleted_pages=[page])
    assert result["documents_removed"] == 1 and _doc_ids(client) == []


# ------------------------------------------------------------------ queued jobs cannot resurrect (F3, F11)


def test_deleted_ticket_cancels_its_queued_ingest_job():
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, [])
    client.tables["rag_ingest_jobs"] = [
        {"id": "j7", "org_id": ORG, "source_id": SRC, "external_id": "zendesk:ticket:7", "status": "queued",
         "request_payload": {"text": "raw ticket body"}},
        {"id": "j8", "org_id": ORG, "source_id": SRC, "external_id": "zendesk:ticket:8", "status": "queued",
         "request_payload": {"text": "other"}},
        {"id": "jx", "org_id": OTHER_ORG, "source_id": SRC, "external_id": "zendesk:ticket:7", "status": "queued",
         "request_payload": {"text": "other org"}},
        {"id": "jd", "org_id": ORG, "source_id": SRC, "external_id": "zendesk:ticket:7", "status": "completed"},
    ]
    page = {"deleted_tickets": [{"id": 7, "deleted_at": "2026-10-05T00:00:00Z"}], "next_page": None}
    _run_zendesk(client, ON, deleted_pages=[page])
    jobs = {j["id"]: j for j in client.tables["rag_ingest_jobs"]}
    assert jobs["j7"]["status"] == "failed" and jobs["j7"]["error_code"] == sl.SOURCE_DELETED_ERROR_CODE
    assert jobs["j7"]["request_payload"] is None  # raw text of the deleted ticket dropped
    assert jobs["j8"]["status"] == "queued" and jobs["jx"]["status"] == "queued"
    assert jobs["jd"]["status"] == "completed"


def test_a_document_that_appears_after_its_deletion_window_is_still_found_by_id():
    # Backstop for any path that indexes a ticket after its deletion was read (for
    # example a job created outside the sync): the check-by-id pass removes it.
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, [])
    page = {"deleted_tickets": [{"id": 7, "deleted_at": "2026-10-05T00:00:00Z"}], "next_page": None}
    _run_zendesk(client, ON, deleted_pages=[page], gone_tickets={"7"})
    client.tables["rag_documents"].append(_doc("t7", "zendesk:ticket:7"))
    _run_zendesk(client, ON, deleted_pages=[page], gone_tickets={"7"})
    assert _doc_ids(client) == []


def _process(cancelled_answers: list[bool]):
    from app.rag import worker

    job = {"id": "j7", "org_id": ORG, "source_id": SRC, "external_id": "zendesk:ticket:7",
           "request_payload": {"title": "t", "chunks": ["a"]}}
    settings = SimpleNamespace(embedding_model="m", openai_embedding_dimension=3)
    client = MagicMock()
    with patch.object(worker, "validate_chunks"), patch.object(worker, "write_audit_event"), patch.object(
        worker, "upsert_document", return_value={"id": "newdoc"}
    ), patch.object(worker, "replace_chunks_and_embeddings", return_value=1), patch.object(
        worker, "finalize_ingest_job"
    ) as finalize, patch.object(worker, "cleanup_document_version") as cleanup, patch(
        "app.services.source_lifecycle.ingest_job_cancelled", side_effect=cancelled_answers
    ):
        worker.process_job(settings, client, job)
    return client, finalize, cleanup


def test_worker_discards_a_job_cancelled_before_activation():
    client, finalize, cleanup = _process([True])
    cleanup.assert_called_once_with(client, ORG, "newdoc")
    finalize.assert_not_called()
    client.rpc.assert_not_called()  # never activated


def test_worker_discards_a_job_cancelled_between_check_and_activation():
    client, finalize, cleanup = _process([False, True])
    assert client.rpc.call_args[0][0] == "activate_rag_document_version"
    cleanup.assert_called_once_with(client, ORG, "newdoc")
    finalize.assert_not_called()


def test_worker_keeps_a_job_that_was_not_cancelled():
    _client_mock, finalize, cleanup = _process([False, False])
    cleanup.assert_not_called()
    assert finalize.call_args.kwargs["status"] == "completed"


def test_ingest_job_cancelled_reads_the_marker():
    client = _client({}, [])
    client.tables["rag_ingest_jobs"] = [
        {"id": "a", "status": "failed", "error_code": "source_deleted"},
        {"id": "b", "status": "running", "error_code": None},
    ]
    assert sl.ingest_job_cancelled(client, "a") is True
    assert sl.ingest_job_cancelled(client, "b") is False
    assert sl.ingest_job_cancelled(MagicMock(), "a") is False  # unreadable: never blocks ingest


def test_removal_deletes_observations_derived_from_the_record():
    client = _client({}, [_doc("e1", "hubspot:email:1")])
    client.tables["entity_observations"] = [
        {"org_id": ORG, "source_system": "hubspot", "source_record_type": "email", "source_record_id": "1"},
        {"org_id": ORG, "source_system": "hubspot", "source_record_type": "email", "source_record_id": "2"},
        {"org_id": OTHER_ORG, "source_system": "hubspot", "source_record_type": "email", "source_record_id": "1"},
    ]
    sl.remove_source_documents(client, ON, org_id=ORG, source_id=SRC, external_ids={"hubspot:email:1"})
    left = [(o["org_id"], o["source_record_id"]) for o in client.tables["entity_observations"]]
    assert left == [(ORG, "2"), (OTHER_ORG, "1")]


# ------------------------------------------------------------------ Zendesk window (F4, F6)


def test_zendesk_over_cap_window_advances_until_older_deletions_are_reached():
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, [_doc("old", "zendesk:ticket:5000")])
    pages = [
        {"deleted_tickets": [{"id": i, "deleted_at": "2026-10-02T00:00:00Z"} for i in range(100)], "next_page": "2"},
        {"deleted_tickets": [{"id": 100 + i, "deleted_at": "2026-10-03T00:00:00Z"} for i in range(100)],
         "next_page": "3"},
        {"deleted_tickets": [{"id": 5000, "deleted_at": "2026-10-04T00:00:00Z"}], "next_page": None},
    ]
    windows: list[str] = []
    page_reads: list[list[int]] = []
    with patch.object(zd, "MAX_DELETED_TICKETS_PER_SYNC", 100):
        for _ in range(3):
            _, reqs = _run_zendesk(client, ON, deleted_pages=pages)
            page_reads.append([r["params"]["page"] for r in reqs])
            windows.append(_saved_config(client)[zd.DELETED_CURSOR_CONFIG_KEY])
    assert page_reads == [[1], [1, 2], [1, 2, 3]]
    assert windows[0] == "2026-10-02T00:00:00Z" and windows[1] == "2026-10-03T00:00:00Z"
    assert windows[2] > "2026-10-04"
    assert _doc_ids(client) == []  # the oldest-listed deletion was reached and applied


def test_zendesk_empty_page_with_next_page_does_not_advance_the_window():
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, [])
    result, _ = _run_zendesk(client, ON, deleted_pages=[{"deleted_tickets": [], "next_page": "n"}])
    assert _saved_config(client)[zd.DELETED_CURSOR_CONFIG_KEY] == "2026-10-01T00:00:00Z"
    assert any("incomplete" in e for e in result["errors"])


@pytest.mark.parametrize(
    "page",
    [
        {"deleted_tickets": [{"id": 1, "deleted_at": "2026-10-05T00:00:00Z"},
                             {"id": 2, "deleted_at": "2026-10-03T00:00:00Z"}], "next_page": None},
        {"deleted_tickets": None, "next_page": None},
    ],
)
def test_zendesk_out_of_order_or_malformed_listing_keeps_the_window(page):
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, [_doc("t1", "zendesk:ticket:1")])
    result, _ = _run_zendesk(client, ON, deleted_pages=[page])
    assert _saved_config(client)[zd.DELETED_CURSOR_CONFIG_KEY] == "2026-10-01T00:00:00Z"
    assert _doc_ids(client) == ["t1"] and any("deleted tickets" in e for e in result["errors"])


# ------------------------------------------------------------------ permanent deletes: check by id (F5)


def test_zendesk_permanently_deleted_ticket_is_found_by_id():
    client = _client({}, [_doc("t1", "zendesk:ticket:1"), _doc("t2", "zendesk:ticket:2")])
    result, _ = _run_zendesk(client, ON, gone_tickets={"2"})
    assert _doc_ids(client) == ["t1"] and result["documents_removed"] == 1


def test_hubspot_gdpr_deleted_record_is_found_by_id_and_position_rotates(monkeypatch):
    monkeypatch.setattr(hs, "VERIFY_BATCH_PER_SYNC", 2)
    docs = [_doc("n1", "hubspot:note:1"), _doc("n2", "hubspot:note:2"), _doc("e1", "hubspot:email:1")]
    client = _client({}, docs)
    by_id: list[tuple[str, str]] = []
    _run_hubspot(client, ON, {}, gone={("notes", "2")}, by_id=by_id)
    assert by_id == [("emails", "1"), ("notes", "1")]
    assert _saved_config(client)[hs.VERIFY_POSITION_CONFIG_KEY] == {"after": "hubspot:note:1"}
    _run_hubspot(client, ON, {}, gone={("notes", "2")}, by_id=by_id)
    assert by_id[2:] == [("notes", "2")]
    assert _doc_ids(client) == ["e1", "n1"]
    assert _saved_config(client)[hs.VERIFY_POSITION_CONFIG_KEY] == {}  # wrapped


def test_hubspot_verify_error_stops_the_pass_and_keeps_position():
    from app.connectors.hubspot import HubSpotAPIError

    client = _client({hs.VERIFY_POSITION_CONFIG_KEY: {"after": "hubspot:email:0"}}, [_doc("n1", "hubspot:note:1")])

    def boom(*_a):
        raise HubSpotAPIError("HubSpot API 401", status_code=401)

    with patch.object(hs, "ensure_hubspot_access_token", return_value=("tok", None)), patch.object(
        hs, "ensure_hubspot_rag_source", return_value=SRC
    ), patch.object(hs, "list_notes_since", MagicMock(return_value=[])), patch.object(
        hs, "list_emails_since", MagicMock(return_value=[])
    ), patch.object(hs, "list_archived_objects", return_value=([], None)), patch.object(
        hs, "crm_object_is_gone", boom
    ):
        result = hs.run_hubspot_knowledge_sync(client, ORG, CONN, ON, actor_id="u")
    assert _doc_ids(client) == ["n1"] and any("401" in e for e in result["errors"])
    assert _saved_config(client)[hs.VERIFY_POSITION_CONFIG_KEY] == {"after": "hubspot:email:0"}


def test_verify_safety_cap_refuses_a_batch_that_is_mostly_gone(audits):
    client = _client({}, [_doc(f"n{i}", f"hubspot:note:{i}") for i in range(10)])
    position: dict[str, Any] = {}
    errors: list[str] = []
    removed = sl.verify_source_documents(
        client, ON, org_id=ORG, source_id=SRC, external_id_prefix="hubspot:", is_gone=lambda ext: True,
        position=position, batch_size=10, errors=errors,
    )
    assert removed == 0 and len(_doc_ids(client)) == 10 and position == {}
    assert _actions(audits) == ["source.documents_removal_refused"] and errors


def test_hubspot_crm_object_is_gone_only_on_404():
    from app.connectors import hubspot as hc

    with patch.object(hc, "_request", side_effect=hc.HubSpotAPIError("x", status_code=404)):
        assert hc.crm_object_is_gone("tok", "notes", "1") is True
    with patch.object(hc, "_request", return_value={"id": "1", "archived": False}) as req:
        assert hc.crm_object_is_gone("tok", "notes", "1") is False
    assert req.call_args[0][1] == "/crm/v3/objects/notes/1"
    for err in (hc.HubSpotAPIError("x", status_code=401), hc.HubSpotAPIError("x", status_code=429)):
        with patch.object(hc, "_request", side_effect=err), pytest.raises(hc.HubSpotAPIError):
            hc.crm_object_is_gone("tok", "notes", "1")
    with patch.object(hc, "_request", return_value={}), pytest.raises(hc.HubSpotAPIError):
        hc.crm_object_is_gone("tok", "notes", "1")


def test_confluence_purged_page_is_found_by_id():
    client = _client(
        {"confluence_sync_targets": [{"id": "space-1", "type": "space"}]},
        [_doc("c1", "confluence:page:1"), _doc("c2", "confluence:page:2")],
    )
    result, _, _ = _run_confluence(client, ON, [{"id": "1", "status": "current"}], [], statuses={"2": None})
    assert _doc_ids(client) == ["c1"] and result["documents_removed"] == 1


def test_confluence_get_page_status_is_none_only_on_404():
    with patch.object(cc, "_request", side_effect=cc.ConfluenceAPIError("x", status_code=404)):
        assert cc.get_page_status("tok", "cloud", "1") is None
    with patch.object(cc, "_request", return_value={"id": "1", "status": "trashed"}):
        assert cc.get_page_status("tok", "cloud", "1") == "trashed"
    with patch.object(cc, "_request", side_effect=cc.ConfluenceAPIError("x", status_code=403)), pytest.raises(
        cc.ConfluenceAPIError
    ):
        cc.get_page_status("tok", "cloud", "1")


# ------------------------------------------------------------------ minors (F7, F10)


def test_confluence_trashed_listing_without_status_stays_trashed():
    with patch.object(cc, "_paginate", return_value=[{"id": "9", "title": "x"}]):
        pages = cc.list_space_pages("tok", "cloud", "space", status="trashed")
    assert pages[0]["status"] == "trashed"
    with patch.object(cc, "_paginate", return_value=[{"id": "9", "title": "x"}]):
        assert cc.list_space_pages("tok", "cloud", "space")[0]["status"] == "current"


def test_confluence_trashed_page_without_status_is_removed_not_reingested():
    client = _client({"confluence_sync_targets": [{"id": "space-1", "type": "space"}]}, [_doc("c9", "confluence:page:9")])

    def fake_paginate(cloud_id, token, path, *, params):
        return [{"id": "9", "title": "x"}] if params.get("status") == "trashed" else []

    ingest = MagicMock(return_value="job")
    with patch.object(conf, "ensure_confluence_session", return_value=("tok", "cloud", None)), patch.object(
        conf, "ensure_confluence_rag_source", return_value=SRC
    ), patch.object(cc, "_paginate", fake_paginate), patch.object(conf, "_queue_page_ingest", ingest), patch.object(
        conf, "get_page_status", return_value="trashed"
    ):
        result = conf.run_confluence_sync(client, ORG, CONN, ON, actor_id="u")
    assert ingest.call_count == 0 and _doc_ids(client) == [] and result["documents_removed"] == 1


def test_hubspot_archived_listing_valueerror_is_recorded_and_cursors_saved():
    client = _client({}, [])
    notes = [{"id": "1", "properties": {"hs_lastmodifieddate": "1700000000000"}}]
    with patch.object(hs, "ensure_hubspot_access_token", return_value=("tok", None)), patch.object(
        hs, "ensure_hubspot_rag_source", return_value=SRC
    ), patch.object(hs, "list_notes_since", MagicMock(return_value=notes)), patch.object(
        hs, "list_emails_since", MagicMock(return_value=[])
    ), patch.object(hs, "create_ingest_job", MagicMock(return_value={"id": "job"})) as ingest, patch.object(
        hs, "list_archived_objects", side_effect=ValueError("Expecting value")
    ):
        result = hs.run_hubspot_knowledge_sync(client, ORG, CONN, ON, actor_id="u")
    assert ingest.call_count == 1
    assert any("archived" in e and "ValueError" in e for e in result["errors"])
    # The run completed: the incremental cursor was saved, so the next run does not
    # re-queue the same records.
    assert "note" in _saved_config(client)[hs.CURSORS_CONFIG_KEY]
