"""Incremental syncs remove documents of records the provider itself reports as removed.

Each provider's own signal (HubSpot archived listing, Zendesk deleted tickets, Confluence
page status, Notion archived/in_trash) removes exactly that record's document, only while
SOURCE_DELETION_PROPAGATION_ENABLED is on, only in the syncing org and source, and never
because a record is merely absent from an incremental page.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.hubspot import list_archived_objects
from app.services import confluence_sync_service as conf
from app.services import hubspot_knowledge_sync_service as hs
from app.services import notion_sync_service as ns
from app.services import source_lifecycle as sl
from app.services import zendesk_knowledge_sync_service as zd

ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "22222222-2222-4222-8222-222222222222"
CONN = "aaaaaaaa-0000-4000-8000-000000000001"
SRC = "s1"

ON = SimpleNamespace(source_deletion_propagation_enabled=True, source_purge_dry_run=False)
DRY = SimpleNamespace(source_deletion_propagation_enabled=True)  # dry-run unless explicitly False
OFF = SimpleNamespace()


@pytest.fixture(autouse=True)
def _no_live_provider_lookups(monkeypatch):
    # The check-by-id pass would otherwise call the real Confluence/HubSpot APIs
    # (a 404 from a fake cloud id reads as "deleted"). Tests that exercise it
    # patch these again with their own answers.
    monkeypatch.setattr(conf, "get_page_status", lambda *_a, **_k: "current")
    monkeypatch.setattr(hs, "crm_object_is_gone", lambda *_a, **_k: False)


@pytest.fixture(autouse=True)
def audits(monkeypatch):
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr("app.workflows.audit.write_audit_event", lambda client, **kw: rows.append(kw))
    return rows


class _Query:
    def __init__(self, client: _Client, table: str) -> None:
        self.client = client
        self.table = table
        self.filters: list[tuple[str, str, Any]] = []
        self.op = "select"
        self.payload: dict[str, Any] | None = None
        self.order_col: str | None = None
        self.window: tuple[int, int] | None = None

    def select(self, *_a, **_k):
        return self

    def delete(self):
        self.op = "delete"
        return self

    def update(self, payload):
        self.op = "update"
        self.payload = payload
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, list(vals)))
        return self

    def like(self, col, val):
        self.filters.append(("like", col, val))
        return self

    def is_(self, col, val):
        self.filters.append(("is", col, val))
        return self

    def gt(self, col, val):
        self.filters.append(("gt", col, val))
        return self

    def order(self, col):
        self.order_col = col
        return self

    def range(self, start, end):
        self.window = (start, end + 1)
        return self

    def limit(self, n):
        self.window = (0, n)
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        for kind, col, val in self.filters:
            v = row.get(col)
            if kind == "eq" and v != val:
                return False
            if kind == "in" and v not in val:
                return False
            if kind == "like" and not str(v or "").startswith(val.rstrip("%")):
                return False
            if kind == "is" and val == "null" and v is not None:
                return False
            if kind == "gt" and not str(v or "") > val:
                return False
        return True

    def execute(self):
        rows = self.client.tables.setdefault(self.table, [])
        hits = [r for r in rows if self._match(r)]
        if self.op == "select":
            if self.order_col:
                hits = sorted(hits, key=lambda r: str(r.get(self.order_col) or ""))
            if self.window:
                hits = hits[self.window[0] : self.window[1]]
        if self.op == "delete":
            self.client.tables[self.table] = [r for r in rows if r not in hits]
            self.client.deletes.append((self.table, list(self.filters)))
        elif self.op == "update":
            for r in hits:
                r.update(self.payload or {})
        return SimpleNamespace(data=hits)


class _Client:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.deletes: list[tuple[str, list]] = []

    def table(self, name):
        return _Query(self, name)


def _doc(doc_id: str, external_id: str, *, org: str = ORG, source: str = SRC) -> dict[str, Any]:
    return {"id": doc_id, "org_id": org, "source_id": source, "external_id": external_id}


def _client(connector_config: dict[str, Any], docs: list[dict[str, Any]]) -> _Client:
    connector = {
        "id": CONN,
        "org_id": ORG,
        "name": "Conn",
        "environment": "production",
        "status": "active",
        "config": connector_config,
    }
    return _Client({"connectors": [connector], "rag_documents": docs})


def _doc_ids(client: _Client) -> list[str]:
    return sorted(r["id"] for r in client.tables["rag_documents"])


def _saved_config(client: _Client) -> dict[str, Any]:
    return client.tables["connectors"][0]["config"]


# ------------------------------------------------------------------ shared helper


def test_remove_source_documents_removes_only_named_ids_in_that_org_and_source():
    client = _Client(
        {
            "rag_documents": [
                _doc("d1", "notion:page:p1"),
                _doc("d2", "notion:page:p2"),
                _doc("d3", "notion:page:p1", source="s2"),
                _doc("d4", "notion:page:p1", org=OTHER_ORG),
            ]
        }
    )
    removed = sl.remove_source_documents(
        client, ON, org_id=ORG, source_id=SRC, external_ids={"notion:page:p1", "notion:page:missing"}
    )
    assert removed == 1
    assert _doc_ids(client) == ["d2", "d3", "d4"]
    # Every document delete is scoped by org and source as well as by id; derived
    # observations (no source column) are scoped by org and the record's system/type/id.
    for table, filters in client.deletes:
        assert ("eq", "org_id", ORG) in filters
        if table == "rag_documents":
            assert ("eq", "source_id", SRC) in filters
        else:
            assert table == "entity_observations"
            assert ("eq", "source_system", "notion") in filters and ("eq", "source_record_type", "page") in filters


@pytest.mark.parametrize("settings", [OFF, SimpleNamespace(source_deletion_propagation_enabled="true"), MagicMock()])
def test_remove_source_documents_requires_the_flag_to_be_exactly_true(settings):
    client = _Client({"rag_documents": [_doc("d1", "notion:page:p1")]})
    assert sl.remove_source_documents(client, settings, org_id=ORG, source_id=SRC, external_ids={"notion:page:p1"}) == 0
    assert _doc_ids(client) == ["d1"] and client.deletes == []


def test_remove_source_documents_with_nothing_flagged_touches_nothing():
    client = _Client({"rag_documents": [_doc("d1", "notion:page:p1")]})
    assert sl.remove_source_documents(client, ON, org_id=ORG, source_id=SRC, external_ids=set()) == 0
    assert client.deletes == []


# ------------------------------------------------------------------ HubSpot


def _hubspot_docs() -> list[dict[str, Any]]:
    return [
        _doc("n1", "hubspot:note:1"),
        _doc("n2", "hubspot:note:2"),
        _doc("e1", "hubspot:email:1"),
        _doc("e9", "hubspot:email:9"),
        _doc("x1", "hubspot:note:1", source="s2"),
        _doc("y1", "hubspot:note:1", org=OTHER_ORG),
    ]


def _run_hubspot(
    client, settings, archived: dict[str, list[dict[str, Any]]], *, notes=None, next_after=None, gone=None, by_id=None
):
    calls: list[tuple[str, str | None]] = []
    by_id = by_id if by_id is not None else []

    def fake_is_gone(token, object_type, object_id):
        by_id.append((object_type, object_id))
        return (object_type, object_id) in (gone or set())

    def fake_archived(token, object_type, *, after=None, max_records=100):
        calls.append((object_type, after))
        return archived.get(object_type, []), next_after

    with patch.object(hs, "ensure_hubspot_access_token", return_value=("tok", None)), patch.object(
        hs, "ensure_hubspot_rag_source", return_value=SRC
    ), patch.object(hs, "list_notes_since", MagicMock(return_value=notes or [])), patch.object(
        hs, "list_emails_since", MagicMock(return_value=[])
    ), patch.object(hs, "create_ingest_job", MagicMock(return_value={"id": "job"})), patch.object(
        hs, "list_archived_objects", fake_archived
    ), patch.object(hs, "crm_object_is_gone", fake_is_gone):
        result = hs.run_hubspot_knowledge_sync(client, ORG, CONN, settings, actor_id="u")
    return result, calls


def test_hubspot_archived_record_removes_exactly_its_document():
    client = _client({}, _hubspot_docs())
    # Note 2 is modified in this incremental page but not archived; email 9 is simply absent.
    result, calls = _run_hubspot(
        client,
        ON,
        {"notes": [{"id": "1", "archived": True}], "emails": [{"id": "1", "archived": True}]},
        notes=[{"id": "2", "properties": {"hs_note_body": "b", "hs_lastmodifieddate": "1700000000000"}}],
    )
    assert result["documents_removed"] == 2
    assert _doc_ids(client) == ["e9", "n2", "x1", "y1"]
    assert sorted(c[0] for c in calls) == ["emails", "notes"]


def test_hubspot_record_without_archived_true_is_not_removed():
    client = _client({}, _hubspot_docs())
    result, _ = _run_hubspot(client, ON, {"notes": [{"id": "1"}, {"id": "2", "archived": False}]})
    assert result["documents_removed"] == 0
    assert len(client.tables["rag_documents"]) == 6


def test_hubspot_flag_off_reads_no_archive_and_removes_nothing():
    client = _client({}, _hubspot_docs())
    result, calls = _run_hubspot(client, OFF, {"notes": [{"id": "1", "archived": True}]})
    assert calls == [] and result["documents_removed"] == 0
    assert len(client.tables["rag_documents"]) == 6
    assert hs.ARCHIVED_CURSORS_CONFIG_KEY not in _saved_config(client)


def test_hubspot_archive_listing_position_continues_then_wraps():
    client = _client({hs.ARCHIVED_CURSORS_CONFIG_KEY: {"note": "500"}}, _hubspot_docs())
    _, calls = _run_hubspot(client, ON, {}, next_after="900")
    assert ("notes", "500") in calls and ("emails", None) in calls
    assert _saved_config(client)[hs.ARCHIVED_CURSORS_CONFIG_KEY] == {"note": "900", "email": "900"}

    _run_hubspot(client, ON, {}, next_after=None)
    assert _saved_config(client)[hs.ARCHIVED_CURSORS_CONFIG_KEY] == {}


def test_hubspot_archive_listing_error_removes_nothing_and_keeps_position():
    from app.connectors.hubspot import HubSpotAPIError

    client = _client({hs.ARCHIVED_CURSORS_CONFIG_KEY: {"note": "500"}}, _hubspot_docs())

    def boom(*_a, **_k):
        raise HubSpotAPIError("HubSpot API 503")

    with patch.object(hs, "ensure_hubspot_access_token", return_value=("tok", None)), patch.object(
        hs, "ensure_hubspot_rag_source", return_value=SRC
    ), patch.object(hs, "list_notes_since", MagicMock(return_value=[])), patch.object(
        hs, "list_emails_since", MagicMock(return_value=[])
    ), patch.object(hs, "list_archived_objects", boom):
        result = hs.run_hubspot_knowledge_sync(client, ORG, CONN, ON, actor_id="u")
    assert result["documents_removed"] == 0 and len(client.tables["rag_documents"]) == 6
    assert any("archived" in e for e in result["errors"])
    assert _saved_config(client)[hs.ARCHIVED_CURSORS_CONFIG_KEY] == {"note": "500"}


def test_hubspot_archived_listing_uses_documented_archived_flag_and_pages():
    pages = [
        {"results": [{"id": "1", "archived": True}], "paging": {"next": {"after": "2"}}},
        {"results": [{"id": "2", "archived": True}]},
    ]
    with patch("app.connectors.hubspot._request", side_effect=pages) as req:
        records, nxt = list_archived_objects("tok", "notes", max_records=500)
    assert [r["id"] for r in records] == ["1", "2"] and nxt is None
    first, second = req.call_args_list
    assert first[0][:2] == ("GET", "/crm/v3/objects/notes")
    assert first[1]["params"]["archived"] == "true" and "after" not in first[1]["params"]
    assert second[1]["params"]["after"] == "2"


# ------------------------------------------------------------------ Zendesk


def _zendesk_docs() -> list[dict[str, Any]]:
    return [
        _doc("t1", "zendesk:ticket:1"),
        _doc("t2", "zendesk:ticket:2"),
        _doc("t3", "zendesk:ticket:3"),
        _doc("x1", "zendesk:ticket:1", source="s2"),
        _doc("y1", "zendesk:ticket:1", org=OTHER_ORG),
    ]


def _run_zendesk(client, settings, *, solved=None, deleted_pages=None, gone_tickets=None):
    from app.connectors.zendesk import ZendeskAPIError

    requests: list[dict[str, Any]] = []

    def fake_request(_sub, _email, _tok, method, path, **kw):
        if path.startswith("/tickets/"):
            tid = path.removeprefix("/tickets/").removesuffix(".json")
            if tid in (gone_tickets or set()):
                raise ZendeskAPIError("Zendesk API 404", status_code=404)
            return {"ticket": {"id": int(tid)}}
        requests.append({"method": method, "path": path, **kw})
        pages = deleted_pages or [{"deleted_tickets": [], "next_page": None}]
        return pages[min(kw["params"]["page"] - 1, len(pages) - 1)]

    with patch.object(zd, "_zendesk_credentials", return_value=("acme", "a@b.com", "tok")), patch.object(
        zd, "ensure_zendesk_rag_source", return_value=SRC
    ), patch.object(zd, "fetch_solved_tickets_since", MagicMock(return_value=solved or [])), patch.object(
        zd, "create_ingest_job", MagicMock(return_value={"id": "job"})
    ), patch.object(zd, "zendesk_request", fake_request):
        result = zd.run_zendesk_knowledge_sync(client, ORG, CONN, settings, actor_id="u")
    return result, requests


def test_zendesk_deleted_ticket_removes_exactly_its_document():
    client = _client({"zendesk_sync_cursor": {"updated_at": "2026-10-01T00:00:00Z", "ids_at_since": []}}, _zendesk_docs())
    deleted = {
        "deleted_tickets": [
            # Deleted before the window: already handled by an earlier run, skipped.
            {"id": 3, "deleted_at": "2026-09-01T00:00:00Z"},
            {"id": 1, "deleted_at": "2026-10-02T00:00:00Z"},
        ],
        "next_page": None,
    }
    result, requests = _run_zendesk(
        client,
        ON,
        solved=[{"id": 2, "subject": "s", "status": "solved", "updated_at": "2026-10-01T05:00:00Z"}],
        deleted_pages=[deleted],
    )
    assert result["documents_removed"] == 1
    assert _doc_ids(client) == ["t2", "t3", "x1", "y1"]
    assert requests[0]["path"] == "/deleted_tickets.json"
    assert requests[0]["params"]["sort_by"] == "deleted_at" and requests[0]["params"]["sort_order"] == "asc"
    # Complete read: the window moves to the run start less the clock-skew overlap.
    assert _saved_config(client)[zd.DELETED_CURSOR_CONFIG_KEY] > "2026-10-02"


def test_zendesk_flag_off_reads_no_deletions_and_removes_nothing():
    client = _client({}, _zendesk_docs())
    result, requests = _run_zendesk(
        client, OFF, deleted_pages=[{"deleted_tickets": [{"id": 1, "deleted_at": "2099-01-01T00:00:00Z"}]}]
    )
    assert requests == [] and result["documents_removed"] == 0
    assert len(client.tables["rag_documents"]) == 5
    assert zd.DELETED_CURSOR_CONFIG_KEY not in _saved_config(client)


def test_zendesk_tickets_absent_from_the_solved_search_are_not_removed():
    client = _client({}, _zendesk_docs())
    result, _ = _run_zendesk(client, ON, solved=[])
    assert result["documents_removed"] == 0 and len(client.tables["rag_documents"]) == 5


def test_zendesk_deleted_listing_error_removes_nothing_and_keeps_window():
    from app.connectors.zendesk import ZendeskAPIError

    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, _zendesk_docs())

    def boom(*_a, **_k):
        raise ZendeskAPIError("Zendesk API 503")

    with patch.object(zd, "_zendesk_credentials", return_value=("acme", "a@b.com", "tok")), patch.object(
        zd, "ensure_zendesk_rag_source", return_value=SRC
    ), patch.object(zd, "fetch_solved_tickets_since", MagicMock(return_value=[])), patch.object(
        zd, "zendesk_request", boom
    ):
        result = zd.run_zendesk_knowledge_sync(client, ORG, CONN, ON, actor_id="u")
    assert result["documents_removed"] == 0 and len(client.tables["rag_documents"]) == 5
    assert any("deleted tickets" in e for e in result["errors"])
    assert _saved_config(client)[zd.DELETED_CURSOR_CONFIG_KEY] == "2026-10-01T00:00:00Z"


def test_zendesk_truncated_deleted_listing_removes_what_it_read_and_advances_to_it():
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, _zendesk_docs())
    page = {"deleted_tickets": [{"id": 1, "deleted_at": "2026-10-05T00:00:00Z"}], "next_page": "more"}
    with patch.object(zd, "MAX_DELETED_TICKETS_PER_SYNC", 1):
        result, _ = _run_zendesk(client, ON, deleted_pages=[page])
    assert result["documents_removed"] == 1
    # Read oldest first, so every deletion up to the last one read is done: the window
    # moves there (inclusive) instead of staying put and re-reading the same slice.
    assert _saved_config(client)[zd.DELETED_CURSOR_CONFIG_KEY] == "2026-10-05T00:00:00Z"
    assert any("read through" in e for e in result["errors"])


# ------------------------------------------------------------------ Confluence


def _confluence_docs() -> list[dict[str, Any]]:
    return [
        _doc("c1", "confluence:page:1"),
        _doc("c2", "confluence:page:2"),
        _doc("c3", "confluence:page:3"),
        _doc("c4", "confluence:page:4"),
        _doc("x1", "confluence:page:2", source="s2"),
        _doc("y1", "confluence:page:2", org=OTHER_ORG),
    ]


def _run_confluence(client, settings, default_pages, trashed_pages, statuses=None):
    statuses = statuses or {}
    listing_calls: list[str | None] = []

    def fake_list(token, cloud_id, space_id, *, status=None, limit=250):
        listing_calls.append(status)
        return trashed_pages if status == "trashed" else default_pages

    ingest = MagicMock(return_value="job")
    with patch.object(conf, "ensure_confluence_session", return_value=("tok", "cloud", None)), patch.object(
        conf, "ensure_confluence_rag_source", return_value=SRC
    ), patch.object(conf, "list_space_pages", fake_list), patch.object(
        conf, "get_page_view_text", return_value=("t", "body", None)
    ), patch.object(conf, "_queue_page_ingest", ingest), patch.object(
        conf, "get_page_status", lambda tok, cloud, pid: statuses.get(pid, "current")
    ):
        result = conf.run_confluence_sync(client, ORG, CONN, settings, actor_id="u")
    return result, listing_calls, ingest


_CONF_CONFIG = {"confluence_sync_targets": [{"id": "space-1", "type": "space"}]}


def test_confluence_archived_and_trashed_pages_remove_exactly_their_documents():
    client = _client(dict(_CONF_CONFIG), _confluence_docs())
    # Page 4 is absent from both listings: not a deletion signal.
    result, calls, ingest = _run_confluence(
        client,
        ON,
        [{"id": "1", "status": "current"}, {"id": "2", "status": "archived"}],
        [{"id": "3", "status": "trashed"}],
    )
    assert calls == [None, "trashed"]
    assert result["documents_removed"] == 2
    assert _doc_ids(client) == ["c1", "c4", "x1", "y1"]
    assert [c.kwargs["page_id"] for c in ingest.call_args_list] == ["1"]


def test_confluence_flag_off_keeps_todays_behaviour():
    client = _client(dict(_CONF_CONFIG), _confluence_docs())
    result, calls, ingest = _run_confluence(
        client, OFF, [{"id": "1", "status": "current"}, {"id": "2", "status": "archived"}], [{"id": "3"}]
    )
    assert calls == [None] and result["documents_removed"] == 0
    assert len(client.tables["rag_documents"]) == 6
    assert ingest.call_count == 2


def test_confluence_trashed_listing_error_still_honours_per_page_status():
    from app.connectors.confluence import ConfluenceAPIError

    client = _client(dict(_CONF_CONFIG), _confluence_docs())

    def fake_list(token, cloud_id, space_id, *, status=None, limit=250):
        if status == "trashed":
            raise ConfluenceAPIError("Confluence API 400")
        return [{"id": "2", "status": "archived"}]

    with patch.object(conf, "ensure_confluence_session", return_value=("tok", "cloud", None)), patch.object(
        conf, "ensure_confluence_rag_source", return_value=SRC
    ), patch.object(conf, "list_space_pages", fake_list), patch.object(conf, "_queue_page_ingest", MagicMock()):
        result = conf.run_confluence_sync(client, ORG, CONN, ON, actor_id="u")
    assert result["documents_removed"] == 1 and _doc_ids(client) == ["c1", "c3", "c4", "x1", "y1"]
    assert any("trashed" in e for e in result["errors"])


def test_confluence_trashed_listing_passes_the_status_filter():
    from app.connectors import confluence as cc

    with patch.object(cc, "_paginate", return_value=[{"id": "9", "status": "trashed"}]) as pag:
        pages = cc.list_space_pages("tok", "cloud", "space-1", status="trashed")
    assert pag.call_args[1]["params"]["status"] == "trashed"
    assert pages[0]["status"] == "trashed"
    with patch.object(cc, "_paginate", return_value=[]) as pag:
        cc.list_space_pages("tok", "cloud", "space-1")
    assert "status" not in pag.call_args[1]["params"]


# ------------------------------------------------------------------ Notion


def _notion_docs() -> list[dict[str, Any]]:
    return [
        _doc("p1", "notion:page:p1"),
        _doc("p2", "notion:page:p2"),
        _doc("p3", "notion:page:p3"),
        _doc("x1", "notion:page:p2", source="s2"),
        _doc("y1", "notion:page:p2", org=OTHER_ORG),
    ]


def _run_notion(client, settings, pages: dict[str, dict[str, Any]], *, fail: set[str] | None = None):
    from app.connectors.notion import NotionAPIError

    exports: list[str] = []

    def fake_get_page(token, page_id):
        if page_id in (fail or set()):
            raise NotionAPIError("rate limited", status_code=429)
        if page_id not in pages:
            raise NotionAPIError("Notion API 404", status_code=404)  # deleted upstream
        return pages[page_id]

    def fake_export(token, page_id, *, page=None):
        exports.append(page_id)
        return ("t", "body", None)

    with patch.object(ns, "ensure_notion_session", return_value=("tok", None)), patch.object(
        ns, "ensure_notion_rag_source", return_value=SRC
    ), patch.object(ns, "get_page", fake_get_page), patch.object(ns, "export_page_text", fake_export), patch.object(
        ns, "_queue_page_ingest", MagicMock(return_value="job")
    ):
        result = ns.run_notion_sync(client, ORG, CONN, settings, actor_id="u")
    return result, exports


def _notion_config(*ids: str) -> dict[str, Any]:
    return {"notion_sync_targets": [{"id": i, "type": "page"} for i in ids]}


def test_notion_archived_or_trashed_page_removes_exactly_its_document_even_after_a_partial_sweep():
    client = _client(_notion_config("p1", "p2", "p3"), _notion_docs())
    # p3 fails to read: the sweep is partial, so reconcile must not run, but p2's own
    # in_trash flag is still a safe per-page signal.
    result, exports = _run_notion(
        client,
        ON,
        {"p1": {"archived": False, "in_trash": False}, "p2": {"in_trash": True}},
        fail={"p3"},
    )
    assert exports == ["p1"]
    assert result["documents_removed"] == 1
    assert _doc_ids(client) == ["p1", "p3", "x1", "y1"]


def test_notion_archived_flag_alone_is_a_removal_signal():
    client = _client(_notion_config("p1", "p2"), _notion_docs())
    result, _ = _run_notion(client, ON, {"p1": {}, "p2": {"archived": True}})
    # A clean sweep: p2 by its own flag, p3 by the existing full-sweep reconcile.
    assert _doc_ids(client) == ["p1", "x1", "y1"]
    assert result["documents_removed"] == 2


def test_notion_flag_off_reads_page_once_and_removes_nothing():
    client = _client(_notion_config("p1", "p2"), _notion_docs())
    gets: list[str] = []

    def fake_export(token, page_id):
        return ("t", "body", None)

    def fake_get_page(token, page_id):
        gets.append(page_id)
        return {"archived": True}

    with patch.object(ns, "ensure_notion_session", return_value=("tok", None)), patch.object(
        ns, "ensure_notion_rag_source", return_value=SRC
    ), patch.object(ns, "get_page", fake_get_page), patch.object(ns, "export_page_text", fake_export), patch.object(
        ns, "_queue_page_ingest", MagicMock(return_value="job")
    ):
        result = ns.run_notion_sync(client, ORG, CONN, OFF, actor_id="u")
    assert gets == [] and result["documents_removed"] == 0
    assert len(client.tables["rag_documents"]) == 5


def test_notion_export_reuses_a_fetched_page_object():
    from app.connectors import notion as nc

    with patch.object(nc, "get_page") as get, patch.object(nc, "fetch_block_tree_text", return_value="body"):
        _title, body, edited = nc.export_page_text("tok", "p1", page={"last_edited_time": "2026-10-01T00:00:00Z"})
    get.assert_not_called()
    assert body == "body" and edited == "2026-10-01T00:00:00Z"
    assert nc.page_is_removed({"in_trash": True}) and nc.page_is_removed({"archived": True})
    assert not nc.page_is_removed({"archived": False, "in_trash": False}) and not nc.page_is_removed({})
