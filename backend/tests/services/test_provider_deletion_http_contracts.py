"""Provider deletion semantics, replayed through the real HTTP client layer.

These are contract tests, not service mocks: each sync runs end to end through the
connector modules' own ``_request`` / ``api_request`` code (URL building, query
parameters, headers, retry on 429, error envelopes, JSON decoding). Only the network is
replaced, at the transport (``httpx.MockTransport``), by responses whose shapes follow
each provider's published API reference (``tests/services/fixtures/provider_deletion``).
Database writes go to the in-memory fake used by the other deletion tests.

What they pin, per provider: which upstream answer excludes a document from retrieval
(archived / trashed / soft-deleted: reversible), which one purges it (confirmed deletion
only), and that auth or rate-limit failures never read as a deletion.

They are the strongest evidence available offline. They do not prove the providers
still answer this way today; ``test_provider_deletion_sandbox.py`` does that against
owner-provided sandbox accounts.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.connectors import confluence as cc
from app.connectors import hubspot as hc
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
    _active_ids,
    _client,
    _doc,
    _doc_ids,
    _excluded_ids,
)

FIXTURES = Path(__file__).parent / "fixtures" / "provider_deletion"
_REAL_CLIENT = httpx.Client


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _reply(spec: dict[str, Any]) -> httpx.Response:
    return httpx.Response(spec["status"], json=spec["body"])


class _Provider:
    """A fake provider at the transport layer: routes requests, records every one."""

    def __init__(self) -> None:
        self.routes: list[tuple[str, Callable[[httpx.Request], bool], Callable[[httpx.Request], httpx.Response]]] = []
        self.requests: list[httpx.Request] = []
        self.unmatched: list[str] = []

    def on(self, method: str, match: Callable[[httpx.Request], bool], respond) -> None:
        self.routes.append((method, match, respond))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for method, match, respond in self.routes:
            if request.method == method and match(request):
                return respond(request)
        self.unmatched.append(f"{request.method} {request.url}")
        raise AssertionError(f"unexpected provider request: {request.method} {request.url}")

    def paths(self, method: str | None = None) -> list[str]:
        return [r.url.path for r in self.requests if method is None or r.method == method]


@pytest.fixture
def provider(monkeypatch) -> _Provider:
    fake = _Provider()

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake.handle)
        return _REAL_CLIENT(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)
    monkeypatch.setattr(cc, "RETRY_BACKOFF_SEC", 0)
    monkeypatch.setattr(hc, "RETRY_BACKOFF_SEC", 0)
    yield fake
    assert fake.unmatched == []
    # Deletion propagation only ever reads from the provider.
    assert {r.method for r in fake.requests} <= {"GET", "POST"}
    assert all(r.method == "GET" or r.url.path.endswith(("/search", "/query")) for r in fake.requests)


@pytest.fixture(autouse=True)
def audits(monkeypatch):
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr("app.workflows.audit.write_audit_event", lambda client, **kw: rows.append(kw))
    return rows


def _actions(rows: list[dict[str, Any]]) -> list[str]:
    return [r["action"] for r in rows]


# ------------------------------------------------------------------ Confluence (REST v2)

CONF_BASE = "/ex/confluence/cloud-1/wiki/api/v2"


def _confluence_provider(provider: _Provider, *, page_105_rate_limited_once: bool = False) -> None:
    data = _load("confluence")
    calls_105 = {"n": 0}

    def listing(req: httpx.Request) -> httpx.Response:
        return _reply(data["space_pages_trashed" if req.url.params.get("status") == "trashed" else "space_pages_default"])

    def page(req: httpx.Request) -> httpx.Response:
        pid = req.url.path.rsplit("/", 1)[-1]
        if req.url.params.get("body-format") == "view":
            return _reply(data[f"page_{pid}_view"])
        if pid == "105" and page_105_rate_limited_once and calls_105["n"] == 0:
            calls_105["n"] += 1
            return _reply(data["rate_limited"])
        return _reply(data["page_by_id"][pid])

    provider.on("GET", lambda r: r.url.path == f"{CONF_BASE}/spaces/S1/pages", listing)
    provider.on("GET", lambda r: r.url.path.startswith(f"{CONF_BASE}/pages/"), page)


def _run_confluence_sync(client, settings):
    ingest = MagicMock(return_value="job")
    with patch.object(conf, "ensure_confluence_session", return_value=("tok", "cloud-1", None)), patch.object(
        conf, "ensure_confluence_rag_source", return_value=SRC
    ), patch.object(conf, "_queue_page_ingest", ingest):
        result = conf.run_confluence_sync(client, ORG, CONN, settings, actor_id="u")
    return result, ingest


def _confluence_docs():
    return [_doc(f"c{i}", f"confluence:page:{i}") for i in range(101, 107)] + [
        _doc("other-org-102", "confluence:page:102", org=OTHER_ORG)
    ]


def test_confluence_contract_archived_and_trashed_excluded_only_404_purges(provider, audits):
    _confluence_provider(provider, page_105_rate_limited_once=True)
    client = _client({"confluence_sync_targets": [{"id": "S1", "type": "space"}]}, _confluence_docs())
    result, ingest = _run_confluence_sync(client, ON)

    # 102 archived, 103 trashed: excluded from retrieval, kept, restorable.
    assert _excluded_ids(client) == ["c102", "c103"]
    # 104 answered 404 to a by-id read that asked for every status: purged.
    assert "c104" not in _doc_ids(client) and result["documents_removed"] == 1
    # 101 and 105 are current (105 after one 429 + retry); 106 answered 403, which
    # stopped the pass and was never read as a deletion. The other org is untouched.
    assert _active_ids(client) == ["c101", "c105", "c106", "other-org-102"]
    assert any("403" in e for e in result["errors"])
    assert [c.kwargs["page_id"] for c in ingest.call_args_list] == ["101"]
    assert ingest.call_args.kwargs["text"] == "Step 1: request laptop"

    by_id = [r for r in provider.requests if r.url.path.startswith(f"{CONF_BASE}/pages/") and "body-format" not in r.url.params]
    assert by_id, "check-by-id pass did not run"
    for r in by_id:
        assert sorted(r.url.params.get_list("status")) == ["archived", "current", "deleted", "trashed"]
        assert r.headers["authorization"] == "Bearer tok"
    assert provider.paths().count(f"{CONF_BASE}/pages/105") == 2  # retried once after 429
    trashed = [r for r in provider.requests if r.url.params.get("status") == "trashed"]
    assert len(trashed) == 1 and trashed[0].url.path == f"{CONF_BASE}/spaces/S1/pages"
    assert "source.documents_excluded" in _actions(audits) and "source.documents_removed" in _actions(audits)


def test_confluence_contract_dry_run_reads_everything_and_changes_nothing(provider, audits):
    _confluence_provider(provider)
    client = _client({"confluence_sync_targets": [{"id": "S1", "type": "space"}]}, _confluence_docs())
    result, _ = _run_confluence_sync(client, DRY)
    assert result["documents_removed"] == 0 and result["documents_excluded"] == 0
    assert client.deletes == [] and len(_active_ids(client)) == 7
    assert set(_actions(audits)) == {"source.documents_exclusion_planned", "source.documents_removal_planned"}


# ------------------------------------------------------------------ HubSpot (CRM v3)


def _hubspot_provider(provider: _Provider) -> None:
    data = _load("hubspot")
    calls_203 = {"n": 0}

    def by_id(req: httpx.Request) -> httpx.Response:
        rid = req.url.path.rsplit("/", 1)[-1]
        archived = req.url.params.get("archived") == "true"
        if rid == "201":
            return _reply(data["note_201_archived"] if archived else data["object_not_found"])
        if rid == "202":
            return _reply(data["object_not_found"])
        if rid == "203":
            calls_203["n"] += 1
            return _reply(data["rate_limited"] if calls_203["n"] == 1 else data["note_203_live"])
        if rid == "204":
            return _reply(data["unauthorized"])
        raise AssertionError(f"unexpected record {rid}")

    provider.on("POST", lambda r: r.url.path.endswith("/search"), lambda r: _reply(data["search_empty"]))
    provider.on(
        "GET",
        lambda r: r.url.path == "/crm/v3/objects/notes" and r.url.params.get("archived") == "true",
        lambda r: _reply(data["notes_archived_listing"]),
    )
    provider.on(
        "GET",
        lambda r: r.url.path == "/crm/v3/objects/emails" and r.url.params.get("archived") == "true",
        lambda r: _reply(data["emails_archived_listing"]),
    )
    provider.on("GET", lambda r: r.url.path.startswith("/crm/v3/objects/notes/"), by_id)


def test_hubspot_contract_archived_excluded_only_double_404_purges(provider, audits):
    _hubspot_provider(provider)
    docs = [_doc(f"n{i}", f"hubspot:note:{i}") for i in range(201, 205)] + [
        _doc("other-org-202", "hubspot:note:202", org=OTHER_ORG)
    ]
    client = _client({}, docs)
    with patch.object(hs, "ensure_hubspot_access_token", return_value=("tok", None)), patch.object(
        hs, "ensure_hubspot_rag_source", return_value=SRC
    ):
        result = hs.run_hubspot_knowledge_sync(client, ORG, CONN, ON, actor_id="u")

    # 201: archived listing + found with archived=true: recycle bin, excluded only.
    assert _excluded_ids(client) == ["n201"] and result["documents_excluded"] == 1
    # 202: 404 on the plain read AND on the archived=true read: permanently deleted.
    assert "n202" not in _doc_ids(client) and result["documents_removed"] == 1
    # 203 live after one 429 + retry; 204 answered 401: stops the pass, never a deletion.
    assert _active_ids(client) == ["n203", "n204", "other-org-202"]
    assert any("401" in e for e in result["errors"])

    reads = [(r.url.path, r.url.params.get("archived")) for r in provider.requests if r.method == "GET"]
    assert ("/crm/v3/objects/notes/202", None) in reads and ("/crm/v3/objects/notes/202", "true") in reads
    assert reads.count(("/crm/v3/objects/notes/203", None)) == 2  # retried after 429
    assert ("/crm/v3/objects/notes/203", "true") not in reads  # live: no second read
    assert all(r.headers["authorization"] == "Bearer tok" for r in provider.requests)


# ------------------------------------------------------------------ Zendesk (Support API v2)

ZD_HOST = "acme-sandbox.zendesk.com"


def _zendesk_provider(provider: _Provider) -> None:
    data = _load("zendesk")

    def ticket(req: httpx.Request) -> httpx.Response:
        tid = req.url.path.rsplit("/", 1)[-1].removesuffix(".json")
        return _reply(data["ticket_303"] if tid == "303" else data["record_not_found"])

    provider.on("GET", lambda r: r.url.path == "/api/v2/search.json", lambda r: _reply(data["search_empty"]))
    provider.on("GET", lambda r: r.url.path == "/api/v2/deleted_tickets.json", lambda r: _reply(data["deleted_tickets"]))
    provider.on("GET", lambda r: r.url.path.startswith("/api/v2/tickets/"), ticket)


def _run_zendesk_sync(client, settings):
    with patch.object(zd, "_zendesk_credentials", return_value=("acme-sandbox", "agent@example.com", "tok")), patch.object(
        zd, "ensure_zendesk_rag_source", return_value=SRC
    ):
        return zd.run_zendesk_knowledge_sync(client, ORG, CONN, settings, actor_id="u")


def test_zendesk_contract_soft_deleted_excluded_purged_only_after_restore_window(provider, audits):
    _zendesk_provider(provider)
    docs = [_doc(f"t{i}", f"zendesk:ticket:{i}") for i in (301, 302, 303)] + [
        _doc("other-org-302", "zendesk:ticket:302", org=OTHER_ORG)
    ]
    client = _client({zd.DELETED_CURSOR_CONFIG_KEY: "2026-10-01T00:00:00Z"}, docs)
    result = _run_zendesk_sync(client, ON)

    # 301 is in "Deleted tickets" (restorable for 30 days); 302 answers 404 by id, which
    # Zendesk also returns for soft-deleted tickets: both excluded, nothing purged.
    assert _excluded_ids(client) == ["t301", "t302"] and result["documents_removed"] == 0
    assert _active_ids(client) == ["other-org-302", "t303"]
    assert all(r.url.host == ZD_HOST for r in provider.requests)
    assert all(r.headers["authorization"].startswith("Basic ") for r in provider.requests)
    listing = next(r for r in provider.requests if r.url.path == "/api/v2/deleted_tickets.json")
    assert listing.url.params["sort_by"] == "deleted_at" and listing.url.params["sort_order"] == "asc"

    # 31 days later 302 still answers 404: Zendesk has scrubbed it, it can no longer be
    # restored. Only now is it purged. 301 was excluded recently and stays excluded.
    for row in client.tables["rag_documents"]:
        if row["id"] == "t302":
            row["metadata"][sl.EXCLUSION_METADATA_KEY]["excluded_at"] = "2026-09-01T00:00:00+00:00"
    result = _run_zendesk_sync(client, ON)
    assert "t302" not in _doc_ids(client) and result["documents_removed"] == 1
    assert _excluded_ids(client) == ["t301"] and "other-org-302" in _active_ids(client)


# ------------------------------------------------------------------ Notion (2022-06-28)


def _notion_provider(provider: _Provider, *, page_403: str = "object_not_found") -> None:
    data = _load("notion")
    pages = {"401": "page_401", "402": "page_402_in_trash", "403": page_403}
    provider.on("POST", lambda r: r.url.path == "/v1/databases/db1/query", lambda r: _reply(data["database_query"]))
    provider.on(
        "GET", lambda r: r.url.path.startswith("/v1/pages/"), lambda r: _reply(data[pages[r.url.path.rsplit("/", 1)[-1]]])
    )
    provider.on("GET", lambda r: r.url.path == "/v1/blocks/401/children", lambda r: _reply(data["blocks_401"]))


def _run_notion_sync(client, settings):
    ingest = MagicMock(return_value="job")
    with patch.object(ns, "ensure_notion_session", return_value=("tok", None)), patch.object(
        ns, "ensure_notion_rag_source", return_value=SRC
    ), patch.object(ns, "_queue_page_ingest", ingest):
        result = ns.run_notion_sync(client, ORG, CONN, settings, actor_id="u")
    return result, ingest


def _notion_docs():
    return [_doc(f"p{i}", f"notion:page:{i}") for i in (401, 402, 403)] + [
        _doc("other-org-403", "notion:page:403", org=OTHER_ORG)
    ]


def test_notion_contract_in_trash_excluded_only_404_purges(provider, audits):
    _notion_provider(provider)
    client = _client({"notion_sync_targets": [{"id": "db1", "type": "database"}]}, _notion_docs())
    result, ingest = _run_notion_sync(client, ON)

    assert _excluded_ids(client) == ["p402"]  # in_trash: restorable, excluded only
    assert "p403" not in _doc_ids(client) and result["documents_removed"] == 1  # object_not_found
    assert _active_ids(client) == ["other-org-403", "p401"]
    assert ingest.call_args.kwargs["text"] == "Annual plans are billed upfront."
    assert all(r.headers["notion-version"] == "2022-06-28" for r in provider.requests)


def test_notion_contract_rate_limit_is_never_a_deletion(provider):
    _notion_provider(provider, page_403="rate_limited")
    client = _client({"notion_sync_targets": [{"id": "db1", "type": "database"}]}, _notion_docs())
    result, _ = _run_notion_sync(client, ON)
    assert "p403" in _active_ids(client) and result["documents_removed"] == 0
    assert any("429" in e for e in result["errors"])


def test_notion_version_header_matches_the_contract_fixtures():
    from app.connectors import notion as nc

    assert nc.NOTION_VERSION == "2022-06-28"


# ------------------------------------------------------------------ the opt-in sandbox module refuses non-sandboxes


def _sandbox_module():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "integration" / "test_provider_deletion_sandbox.py"
    spec = importlib.util.spec_from_file_location("_provider_deletion_sandbox_guards", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("account_type", "refused"), [("STANDARD", True), ("", True), ("SANDBOX", False), ("DEVELOPER_TEST", False)]
)
def test_sandbox_guard_refuses_a_non_sandbox_hubspot_account(provider, account_type, refused):
    mod = _sandbox_module()
    provider.on(
        "GET",
        lambda r: r.url.path == "/account-info/v3/details",
        lambda r: httpx.Response(200, json={"portalId": 1, "accountType": account_type}),
    )
    if refused:
        with pytest.raises(pytest.fail.Exception):
            mod._hubspot_guard("tok")
    else:
        mod._hubspot_guard("tok")


@pytest.mark.parametrize(
    ("url", "refused"),
    [
        ("https://acme.atlassian.net", True),
        ("https://acme-sandbox-123.atlassian.net", False),
        ("https://sandbox.evil.example", True),
    ],
)
def test_sandbox_guard_refuses_a_non_sandbox_confluence_site(provider, url, refused):
    mod = _sandbox_module()
    provider.on(
        "GET",
        lambda r: r.url.path == "/oauth/token/accessible-resources",
        lambda r: httpx.Response(200, json=[{"id": "cloud-1", "url": url, "name": "acme", "scopes": []}]),
    )
    if refused:
        with pytest.raises(pytest.fail.Exception):
            mod._confluence_guard("tok", "cloud-1")
    else:
        mod._confluence_guard("tok", "cloud-1")


def test_sandbox_guard_refuses_non_sandbox_zendesk_and_notion(provider):
    mod = _sandbox_module()
    with pytest.raises(pytest.fail.Exception):
        mod._zendesk_guard("acme")
    mod._zendesk_guard("acme-sandbox")
    provider.on(
        "GET",
        lambda r: r.url.path == "/v1/users/me",
        lambda r: httpx.Response(
            200, json={"object": "user", "id": "u", "type": "bot", "bot": {"workspace_name": "Acme Inc"}}
        ),
    )
    with pytest.raises(pytest.fail.Exception):
        mod._notion_guard("tok")
