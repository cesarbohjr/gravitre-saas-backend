"""Archived is not deleted: upstream archive/trash is a reversible retrieval exclusion.

Release decision for deletion propagation: content a provider can still restore
(Confluence archived or trashed page, HubSpot archived record, Zendesk soft-deleted
ticket, Notion archived / in-trash page) is excluded from active retrieval, kept, and
brought back when the record is live again. Only a confirmed deletion purges.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services import confluence_sync_service as conf
from app.services import hubspot_knowledge_sync_service as hs
from app.services import notion_sync_service as ns
from app.services import source_lifecycle as sl
from tests.services.test_incremental_deletion_propagation import (
    _CONF_CONFIG,
    CONN,
    DRY,
    OFF,
    ON,
    ORG,
    OTHER_ORG,
    SRC,
    _active_ids,
    _client,
    _doc,
    _doc_ids,
    _excluded_ids,
    _run_confluence,
    _run_hubspot,
)

MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"


@pytest.fixture(autouse=True)
def _no_live_provider_lookups(monkeypatch):
    monkeypatch.setattr(conf, "get_page_status", lambda *_a, **_k: "current")
    monkeypatch.setattr(hs, "crm_object_state", lambda *_a, **_k: "present")


@pytest.fixture(autouse=True)
def audits(monkeypatch):
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr("app.workflows.audit.write_audit_event", lambda client, **kw: rows.append(kw))
    return rows


def _actions(rows: list[dict[str, Any]]) -> list[str]:
    return [r["action"] for r in rows]


def _row(client, doc_id: str) -> dict[str, Any]:
    return next(r for r in client.tables["rag_documents"] if r["id"] == doc_id)


# ------------------------------------------------------------------ the primitive


def test_exclusion_deactivates_and_marks_only_the_named_records_in_that_org_and_source(audits):
    client = _client(
        {},
        [
            _doc("d1", "confluence:page:1"),
            _doc("d2", "confluence:page:2"),
            _doc("x1", "confluence:page:1", source="s2"),
            _doc("y1", "confluence:page:1", org=OTHER_ORG),
        ],
    )
    _row(client, "d1")["metadata"] = {"content_sha256": "abc"}
    n = sl.exclude_source_documents(
        client, ON, org_id=ORG, source_id=SRC, external_ids={"confluence:page:1"}, signal="t"
    )
    assert n == 1 and client.deletes == []
    assert _active_ids(client) == ["d2", "x1", "y1"] and _excluded_ids(client) == ["d1"]
    meta = _row(client, "d1")["metadata"]
    assert meta["content_sha256"] == "abc"  # existing metadata kept
    assert meta[sl.EXCLUSION_METADATA_KEY]["reason"] == "archived"
    assert meta[sl.EXCLUSION_METADATA_KEY]["signal"] == "t"
    for table, filters, _payload in client.updates:
        assert table == "rag_documents"
        assert ("eq", "org_id", ORG) in filters and ("eq", "source_id", SRC) in filters
    assert _actions(audits) == ["source.documents_excluded"]
    assert audits[0]["metadata"]["reversible"] is True and audits[0]["metadata"]["dry_run"] is False


def test_exclusion_is_idempotent():
    client = _client({}, [_doc("d1", "notion:page:p1")])
    kw: dict[str, Any] = {"org_id": ORG, "source_id": SRC, "external_ids": {"notion:page:p1"}, "signal": "t"}
    assert sl.exclude_source_documents(client, ON, **kw) == 1
    updates = len(client.updates)
    assert sl.exclude_source_documents(client, ON, **kw) == 0
    assert len(client.updates) == updates and _excluded_ids(client) == ["d1"]


@pytest.mark.parametrize("settings", [DRY, SimpleNamespace(source_deletion_propagation_enabled=True, source_purge_dry_run="false")])
def test_exclusion_dry_run_plans_and_changes_nothing(settings, audits):
    client = _client({}, [_doc("d1", "notion:page:p1")])
    client.tables["rag_ingest_jobs"] = [
        {"id": "j1", "org_id": ORG, "source_id": SRC, "external_id": "notion:page:p1", "status": "queued"}
    ]
    n = sl.exclude_source_documents(client, settings, org_id=ORG, source_id=SRC, external_ids={"notion:page:p1"}, signal="t")
    assert n == 0 and client.updates == [] and _active_ids(client) == ["d1"]
    assert client.tables["rag_ingest_jobs"][0]["status"] == "queued"
    assert _actions(audits) == ["source.documents_exclusion_planned"]
    assert audits[0]["metadata"]["documents"] == 1 and audits[0]["metadata"]["dry_run"] is True


@pytest.mark.parametrize("settings", [OFF, SimpleNamespace(source_deletion_propagation_enabled="true"), MagicMock()])
def test_exclusion_and_restore_require_the_flag_to_be_exactly_true(settings):
    client = _client({}, [_doc("d1", "notion:page:p1")])
    kw: dict[str, Any] = {"org_id": ORG, "source_id": SRC, "external_ids": {"notion:page:p1"}, "signal": "t"}
    assert sl.exclude_source_documents(client, settings, **kw) == 0
    assert sl.restore_source_documents(client, settings, **kw) == 0
    assert client.updates == [] and _active_ids(client) == ["d1"]


def test_exclusion_cancels_queued_jobs_so_the_worker_cannot_reactivate_the_record():
    client = _client({}, [_doc("d1", "hubspot:note:1")])
    client.tables["rag_ingest_jobs"] = [
        {"id": "j1", "org_id": ORG, "source_id": SRC, "external_id": "hubspot:note:1", "status": "queued",
         "request_payload": {"text": "body"}},
        {"id": "jx", "org_id": OTHER_ORG, "source_id": SRC, "external_id": "hubspot:note:1", "status": "queued",
         "request_payload": {"text": "other org"}},
    ]
    sl.exclude_source_documents(client, ON, org_id=ORG, source_id=SRC, external_ids={"hubspot:note:1"}, signal="t")
    jobs = {j["id"]: j for j in client.tables["rag_ingest_jobs"]}
    assert jobs["j1"]["status"] == "failed" and jobs["j1"]["error_code"] == sl.SOURCE_EXCLUDED_ERROR_CODE
    assert jobs["j1"]["request_payload"] is None
    assert jobs["jx"]["status"] == "queued"
    assert sl.ingest_job_cancelled(client, "j1") is True  # the worker discards its version


def test_restore_reactivates_the_excluded_version_and_clears_the_marker(audits):
    client = _client({}, [_doc("d1", "confluence:page:1"), _doc("y1", "confluence:page:1", org=OTHER_ORG)])
    kw: dict[str, Any] = {"org_id": ORG, "source_id": SRC, "external_ids": {"confluence:page:1"}, "signal": "t"}
    sl.exclude_source_documents(client, ON, **kw)
    assert sl.restore_source_documents(client, ON, **kw) == 1
    assert _active_ids(client) == ["d1", "y1"]
    assert sl.EXCLUSION_METADATA_KEY not in _row(client, "d1")["metadata"]
    assert _row(client, "d1")["archived_at"] is None
    assert _actions(audits) == ["source.documents_excluded", "source.documents_restored"]
    # Nothing left to restore: idempotent, no second receipt.
    assert sl.restore_source_documents(client, ON, **kw) == 0 and len(audits) == 2


def test_restore_never_reactivates_superseded_versions_or_a_record_with_a_live_version():
    old = {**_doc("v1", "confluence:page:1"), "is_active": False, "metadata": {}}  # superseded, no marker
    client = _client({}, [old, _doc("v2", "confluence:page:1")])
    kw: dict[str, Any] = {"org_id": ORG, "source_id": SRC, "external_ids": {"confluence:page:1"}, "signal": "t"}
    sl.exclude_source_documents(client, ON, **kw)
    assert _excluded_ids(client) == ["v2"] and _active_ids(client) == []
    # A re-ingest activated a newer version before the restore ran.
    client.tables["rag_documents"].append(_doc("v3", "confluence:page:1"))
    assert sl.restore_source_documents(client, ON, **kw) == 0
    assert _active_ids(client) == ["v3"]  # exactly one active version, never two
    assert sl.EXCLUSION_METADATA_KEY not in _row(client, "v2")["metadata"]  # stale marker dropped
    assert _row(client, "v1")["is_active"] is False


def test_restore_works_in_dry_run_because_it_only_reverses_an_exclusion():
    client = _client({}, [_doc("d1", "notion:page:p1")])
    kw: dict[str, Any] = {"org_id": ORG, "source_id": SRC, "external_ids": {"notion:page:p1"}, "signal": "t"}
    sl.exclude_source_documents(client, ON, **kw)
    assert sl.restore_source_documents(client, DRY, **kw) == 1 and _active_ids(client) == ["d1"]


def test_excluded_since_reads_the_marker():
    client = _client({}, [_doc("d1", "zendesk:ticket:1"), _doc("d2", "zendesk:ticket:2")])
    sl.exclude_source_documents(client, ON, org_id=ORG, source_id=SRC, external_ids={"zendesk:ticket:1"}, signal="t")
    assert sl.excluded_since(client, org_id=ORG, source_id=SRC, external_id="zendesk:ticket:1") is not None
    assert sl.excluded_since(client, org_id=ORG, source_id=SRC, external_id="zendesk:ticket:2") is None
    assert sl.excluded_since(client, org_id=OTHER_ORG, source_id=SRC, external_id="zendesk:ticket:1") is None


def test_exclusions_do_not_count_toward_the_deletion_safety_cap(audits):
    # Ten archived records in one pass: reversible, so not refused; nothing is deleted.
    client = _client({}, [_doc(f"n{i}", f"hubspot:note:{i}") for i in range(10)])
    errors: list[str] = []
    removed = sl.verify_source_documents(
        client, ON, org_id=ORG, source_id=SRC, external_id_prefix="hubspot:", is_gone=lambda ext: sl.EXCLUDE,
        position={}, batch_size=10, errors=errors,
    )
    assert removed == 0 and errors == [] and client.deletes == []
    assert len(_excluded_ids(client)) == 10
    assert _actions(audits) == ["source.documents_excluded"]


def test_verify_restores_an_excluded_record_found_live_again():
    client = _client({}, [_doc("n1", "hubspot:note:1")])
    sl.exclude_source_documents(client, ON, org_id=ORG, source_id=SRC, external_ids={"hubspot:note:1"}, signal="t")
    sl.verify_source_documents(
        client, ON, org_id=ORG, source_id=SRC, external_id_prefix="hubspot:", is_gone=lambda ext: False,
        position={}, batch_size=10, errors=[],
    )
    assert _active_ids(client) == ["n1"]


# ------------------------------------------------------------------ providers, round trip


def test_confluence_archive_then_unarchive_round_trip(audits):
    client = _client(dict(_CONF_CONFIG), [_doc("c1", "confluence:page:1"), _doc("c2", "confluence:page:2")])
    result, _, _ = _run_confluence(client, ON, [{"id": "1", "status": "current"}, {"id": "2", "status": "archived"}], [])
    assert result["documents_excluded"] == 1 and _active_ids(client) == ["c1"] and len(_doc_ids(client)) == 2
    # The page is unarchived: it is listed as current again and comes straight back.
    result, _, ingest = _run_confluence(
        client, ON, [{"id": "1", "status": "current"}, {"id": "2", "status": "current"}], []
    )
    assert result["documents_restored"] == 1 and _active_ids(client) == ["c1", "c2"]
    assert sorted(c.kwargs["page_id"] for c in ingest.call_args_list) == ["1", "2"]
    assert "source.documents_restored" in _actions(audits)


def test_confluence_trashed_then_purged_page_is_removed_only_on_confirmation():
    client = _client(dict(_CONF_CONFIG), [_doc("c1", "confluence:page:1"), _doc("c2", "confluence:page:2")])
    _run_confluence(client, ON, [{"id": "1", "status": "current"}], [{"id": "2", "status": "trashed"}])
    assert _excluded_ids(client) == ["c2"] and len(_doc_ids(client)) == 2
    # Emptied from the trash: in no listing, and the by-id read (all statuses) is 404.
    result, _, _ = _run_confluence(client, ON, [{"id": "1", "status": "current"}], [], statuses={"2": None})
    assert result["documents_removed"] == 1 and _doc_ids(client) == ["c1"]


def test_confluence_checker_purges_only_on_404_or_deleted():
    with patch.object(conf, "get_page_status", side_effect=[None, "deleted", "archived", "trashed", "current"]):
        check = conf._page_gone_checker("tok", "cloud")
        verdicts = [check(f"confluence:page:{i}") for i in range(5)]
    assert verdicts == [True, True, sl.EXCLUDE, sl.EXCLUDE, False]


def test_hubspot_checker_purges_only_on_confirmed_deletion():
    with patch.object(hs, "crm_object_state", side_effect=["deleted", "archived", "present"]):
        check = hs._record_gone_checker("tok")
        verdicts = [check("hubspot:note:1"), check("hubspot:note:2"), check("hubspot:email:3")]
    assert verdicts == [True, sl.EXCLUDE, False]


def test_hubspot_restored_record_comes_back_on_the_check_by_id_pass():
    client = _client({}, [_doc("n1", "hubspot:note:1")])
    _run_hubspot(client, ON, {"notes": [{"id": "1", "archived": True}]})
    assert _excluded_ids(client) == ["n1"]
    # Restored from the recycle bin: no longer listed as archived, present by id.
    _run_hubspot(client, ON, {})
    assert _active_ids(client) == ["n1"]


def test_hubspot_archived_by_id_is_excluded_and_deleted_by_id_is_removed():
    client = _client({}, [_doc("n1", "hubspot:note:1"), _doc("n2", "hubspot:note:2"), _doc("n3", "hubspot:note:3")])
    result, _ = _run_hubspot(client, ON, {}, gone={("notes", "2")}, archived_by_id={("notes", "1")})
    assert result["documents_removed"] == 1
    assert _doc_ids(client) == ["n1", "n3"] and _excluded_ids(client) == ["n1"]


def test_notion_checker_purges_only_on_404():
    from app.connectors.notion import NotionAPIError

    answers = [NotionAPIError("x", status_code=404), {"in_trash": True}, {"archived": True}, {"archived": False}]

    def get_page(_tok, _pid):
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a

    with patch.object(ns, "get_page", get_page):
        check = ns._page_gone_checker("tok")
        verdicts = [check(f"notion:page:p{i}") for i in range(4)]
    assert verdicts == [True, sl.EXCLUDE, sl.EXCLUDE, False]


def test_notion_page_restored_from_trash_round_trip():
    client = _client({"notion_sync_targets": [{"id": "p1", "type": "page"}]}, [_doc("d1", "notion:page:p1")])
    state = {"in_trash": True}

    def get_page(_tok, _pid):
        return dict(state)

    with patch.object(ns, "ensure_notion_session", return_value=("tok", None)), patch.object(
        ns, "ensure_notion_rag_source", return_value=SRC
    ), patch.object(ns, "get_page", get_page), patch.object(
        ns, "export_page_text", return_value=("t", "b", None)
    ), patch.object(ns, "_queue_page_ingest", MagicMock(return_value="job")):
        first = ns.run_notion_sync(client, ORG, CONN, ON, actor_id="u")
        assert first["documents_excluded"] == 1 and _excluded_ids(client) == ["d1"]
        state["in_trash"] = False
        second = ns.run_notion_sync(client, ORG, CONN, ON, actor_id="u")
    assert second["documents_restored"] == 1 and _active_ids(client) == ["d1"]


# ------------------------------------------------------------------ retrieval honours it


def _latest_rag_search_definition() -> str:
    defs: list[tuple[str, str]] = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = path.read_text()
        for m in re.finditer(r"CREATE OR REPLACE FUNCTION public\.rag_search\(.*?\$\$;", sql, flags=re.DOTALL):
            defs.append((path.name, m.group(0)))
    assert defs, "rag_search not found in migrations"
    return defs[-1][1]


def test_vector_search_rpc_only_returns_active_document_versions():
    # The exclusion works by deactivating the version; the vector arm must filter on it.
    assert "d.is_active IS TRUE" in _latest_rag_search_definition()


def test_keyword_arm_drops_chunks_of_an_excluded_document(monkeypatch):
    from app.rag import retrieval as rag_retrieval

    client = _client({}, [_doc("d1", "confluence:page:1"), _doc("d2", "confluence:page:2")])
    sl.exclude_source_documents(client, ON, org_id=ORG, source_id=SRC, external_ids={"confluence:page:2"}, signal="t")
    active = {r["id"]: r["is_active"] for r in client.tables["rag_documents"]}

    class _Chunks:
        def __init__(self):
            self.filters: list[tuple] = []

        def __getattr__(self, name):
            def call(*a, **_k):
                self.filters.append((name, a))
                return self

            return call

        def execute(self):
            rows = [
                {"id": f"c-{d}", "content": f"text {d}", "document_id": d, "rag_documents": {"is_active": active[d]}}
                for d in ("d1", "d2")
            ]
            if ("eq", ("rag_documents.is_active", True)) in self.filters:
                rows = [r for r in rows if r["rag_documents"]["is_active"] is True]
            return SimpleNamespace(data=rows)

    class _Db:
        def table(self, name):
            return _Chunks()

    monkeypatch.setattr(rag_retrieval, "create_client", lambda *a, **k: _Db())
    monkeypatch.setattr(rag_retrieval, "_resolve_source_ids_for_scope", lambda *a, **k: None)
    out, _ = rag_retrieval.fetch_bm25_corpus(
        SimpleNamespace(supabase_url="u", supabase_service_role_key="k"), ORG, query_text="text"
    )
    assert [r["id"] for r in out] == ["c-d1"]


# ------------------------------------------------------------------ automatic live deletion stays off


def test_defaults_keep_automatic_live_deletion_off():
    from app.config import Settings

    fields = Settings.model_fields
    assert fields["source_deletion_propagation_enabled"].default is False
    assert fields["source_purge_dry_run"].default is True
    assert sl.deletion_propagation_enabled(SimpleNamespace()) is False
    assert sl.deletion_dry_run(SimpleNamespace()) is True
