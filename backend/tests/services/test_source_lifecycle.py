"""Phase 2B source lifecycle: purge handler, provider revoke, deletion propagation.

The purge SQL itself runs against real PostgreSQL in tests/db/test_source_purge_pg.py.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.connectors import provider_revoke as pr
from app.services import domain_events as de
from app.services import source_lifecycle as sl

ORG = "11111111-1111-4111-8111-111111111111"
CONN = "aaaaaaaa-0000-4000-8000-000000000001"


class _Query:
    def __init__(self, client: _Client, table: str) -> None:
        self.client = client
        self.table = table
        self.filters: list[tuple[str, str, Any]] = []
        self.op = "select"

    def select(self, *_a, **_k):
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def is_(self, col, val):
        self.filters.append(("is", col, val))
        return self

    def like(self, col, val):
        self.filters.append(("like", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, list(vals)))
        return self

    def limit(self, _n):
        return self

    def order(self, _col):
        return self

    def range(self, start, end):
        self.window = (start, end + 1)
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        for kind, col, val in self.filters:
            v = row.get(col)
            if kind == "eq" and v != val:
                return False
            if kind == "is" and val == "null" and v is not None:
                return False
            if kind == "like" and not str(v or "").startswith(val.rstrip("%")):
                return False
            if kind == "in" and v not in val:
                return False
        return True

    def execute(self):
        rows = self.client.tables.setdefault(self.table, [])
        hits = [r for r in rows if self._match(r)]
        if self.op == "select" and getattr(self, "window", None):
            hits = hits[self.window[0] : self.window[1]]
        if self.op == "delete":
            self.client.tables[self.table] = [r for r in rows if r not in hits]
            self.client.deletes.append((self.table, list(self.filters)))
        return SimpleNamespace(data=hits)


class _Client:
    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None, *, rpc_error: bool = False) -> None:
        self.tables = tables or {}
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []
        self.deletes: list[tuple[str, list]] = []
        self.rpc_error = rpc_error
        self.events: list[dict[str, Any]] = []

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params):
        client = self

        def execute():
            client.rpc_calls.append((name, params))
            if name == "purge_connector_derived_data":
                if client.rpc_error:
                    raise RuntimeError("db down")
                return SimpleNamespace(data={"rag_sources": 2, "dry_run_seen": params["p_dry_run"]})
            if name == "claim_domain_events":
                out, client.events = client.events, []
                return SimpleNamespace(data=out)
            if name == "complete_domain_event":
                return SimpleNamespace(data=True)
            if name == "fail_domain_event":
                return SimpleNamespace(data="pending")
            raise AssertionError(name)

        return SimpleNamespace(execute=execute)


def _event(**payload) -> dict[str, Any]:
    p = {"connector_id": CONN, "connector_type": "hubspot", "deleted_at": "2026-10-12T10:00:00+00:00"}
    p.update(payload)
    return {
        "id": 1,
        "event_id": "e-1",
        "org_id": ORG,
        "event_type": de.EVENT_SOURCE_DISCONNECTED,
        "aggregate_id": CONN,
        "attempts": 1,
        "delivered_handlers": [],
        "payload": p,
    }


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    de.reset_domain_event_handlers_for_tests()
    audits: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.workflows.audit.write_audit_event",
        lambda client, **kw: audits.append(kw),
    )
    yield audits
    de.reset_domain_event_handlers_for_tests()


# ------------------------------------------------------------------ purge handler


def test_handler_plans_by_default(_reset):
    client = _Client({"connectors": [{"id": CONN, "org_id": ORG, "vendor": "HubSpot", "type": "hubspot"}]})
    counts = sl.handle_source_disconnected(client, _event(), SimpleNamespace())
    name, params = client.rpc_calls[0]
    assert name == "purge_connector_derived_data"
    assert params == {
        "p_org_id": ORG,
        "p_connector_id": CONN,
        "p_vendor": "hubspot",
        "p_disconnected_at": "2026-10-12T10:00:00+00:00",
        "p_dry_run": True,
        "p_event_id": "e-1",
    }
    assert counts["dry_run_seen"] is True
    assert _reset[0]["action"] == "connector.data_purge_planned"
    assert _reset[0]["metadata"]["counts"]["rag_sources"] == 2


@pytest.mark.parametrize("value", [None, "false", 0, True])
def test_only_explicit_false_turns_dry_run_off(value):
    client = _Client()
    sl.handle_source_disconnected(client, _event(), SimpleNamespace(source_purge_dry_run=value))
    assert client.rpc_calls[0][1]["p_dry_run"] is True


def test_handler_purges_when_dry_run_off(_reset):
    client = _Client()
    sl.handle_source_disconnected(client, _event(), SimpleNamespace(source_purge_dry_run=False))
    assert client.rpc_calls[0][1]["p_dry_run"] is False
    assert _reset[0]["action"] == "connector.data_purged"


def test_hard_deleted_connector_uses_payload_vendor():
    client = _Client()  # row is gone
    sl.handle_source_disconnected(client, _event(connector_type="gmail", hard_deleted=True), SimpleNamespace())
    assert client.rpc_calls[0][1]["p_vendor"] == "gmail"


def test_malformed_event_completes_without_purging():
    client = _Client()
    assert sl.handle_source_disconnected(client, _event(connector_id="nope"), SimpleNamespace()) == {
        "skipped": "malformed"
    }
    assert sl.handle_source_disconnected(client, _event(deleted_at=None), SimpleNamespace()) == {
        "skipped": "malformed"
    }
    assert client.rpc_calls == []


def test_rpc_failure_raises_so_relay_retries():
    with pytest.raises(sl.SourcePurgeError):
        sl.handle_source_disconnected(_Client(rpc_error=True), _event(), SimpleNamespace())


def test_registration_is_idempotent():
    sl.register_source_lifecycle_handlers()
    sl.register_source_lifecycle_handlers()
    assert [r.name for r in de.handlers_for(de.EVENT_SOURCE_DISCONNECTED)] == [sl.PURGE_HANDLER_NAME]


def test_relay_retries_failed_purge_then_skips_it_once_delivered(monkeypatch):
    sl.register_source_lifecycle_handlers()
    client = _Client(rpc_error=True)
    client.events = [_event()]
    relay = de.DomainEventRelay(client, worker_id="w1")
    first = relay.run_once()
    assert first.retried == 1
    fail = next(p for n, p in client.rpc_calls if n == "fail_domain_event")
    assert fail["p_delivered_handlers"] == []

    # Redelivered after success elsewhere: the delivered handler is not run again.
    client.rpc_error = False
    client.events = [dict(_event(), delivered_handlers=[sl.PURGE_HANDLER_NAME], attempts=2)]
    client.rpc_calls.clear()
    relay.run_once()
    assert [n for n, _ in client.rpc_calls] == ["claim_domain_events", "complete_domain_event"]


def test_relay_start_registers_handlers(monkeypatch):
    from app.schedulers import domain_event_relay_scheduler as sched

    monkeypatch.setattr(
        sched,
        "get_settings",
        lambda: SimpleNamespace(domain_event_relay_enabled=True, domain_event_relay_interval_seconds=15),
    )
    created: list[Any] = []

    def fake_task(coro):
        created.append(coro)
        coro.close()
        return "task"

    monkeypatch.setattr(sched.asyncio, "create_task", fake_task)
    assert sched.start_domain_event_relay_scheduler() == "task"
    assert [r.name for r in de.handlers_for(de.EVENT_SOURCE_DISCONNECTED)] == [sl.PURGE_HANDLER_NAME]


# ------------------------------------------------------------------ provider revoke


def _http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_revoke_disabled_by_default():
    out = sl.revoke_on_disconnect(_Client(), SimpleNamespace(), org_id=ORG, connector_id=CONN, vendor="hubspot")
    assert out.status == "disabled"


def test_google_revoke_skipped_when_another_google_connector_is_live(monkeypatch):
    client = _Client(
        {
            "connectors": [
                {"id": CONN, "org_id": ORG, "vendor": "google_drive", "deleted_at": "x"},
                {"id": "other", "org_id": ORG, "vendor": "gmail", "deleted_at": None},
            ]
        }
    )
    monkeypatch.setattr(
        "app.connectors.hubspot_oauth.load_oauth_tokens", lambda *a: {"refresh_token": "r", "access_token": "a"}
    )
    sent: list[Any] = []
    monkeypatch.setattr(pr, "_post", lambda *a, **k: sent.append(a))
    out = sl.revoke_on_disconnect(
        client,
        SimpleNamespace(connector_provider_revoke_on_disconnect=True),
        org_id=ORG,
        connector_id=CONN,
        vendor="google_drive",
    )
    assert out.status == "skipped_shared_grant" and sent == []


def test_revoke_never_raises(monkeypatch):
    def boom(*_a):
        raise RuntimeError("secrets table down")

    monkeypatch.setattr("app.connectors.hubspot_oauth.load_oauth_tokens", boom)
    out = sl.revoke_on_disconnect(
        _Client(),
        SimpleNamespace(connector_provider_revoke_on_disconnect=True),
        org_id=ORG,
        connector_id=CONN,
        vendor="hubspot",
    )
    assert out.status == "failed"


def test_google_revoke_posts_refresh_token():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200)

    out = pr.revoke_provider_tokens("gmail", {"refresh_token": "r1", "access_token": "a1"}, http=_http(handler))
    assert out.status == "revoked"
    assert str(seen[0].url) == pr.GOOGLE_REVOKE_URL and seen[0].content == b"token=r1"


def test_google_already_revoked_counts_as_revoked():
    out = pr.revoke_provider_tokens(
        "google_analytics",
        {"access_token": "a"},
        http=_http(lambda r: httpx.Response(400, json={"error": "invalid_token"})),
    )
    assert out.status == "revoked"


def test_hubspot_deletes_refresh_token():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return httpx.Response(204)

    out = pr.revoke_provider_tokens("hubspot", {"refresh_token": "rt", "access_token": "a"}, http=_http(handler))
    assert out.status == "revoked"
    assert seen[0].method == "DELETE" and seen[0].url.path == "/oauth/v1/refresh-tokens/rt"


def test_slack_auth_revoke():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json={"ok": True, "revoked": True})

    out = pr.revoke_provider_tokens("slack", {"access_token": "xoxb"}, http=_http(handler))
    assert out.status == "revoked" and seen[0].headers["authorization"] == "Bearer xoxb"


def test_salesforce_uses_instance_url():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200)

    out = pr.revoke_provider_tokens(
        "salesforce",
        {"refresh_token": "r"},
        config={"instance_url": "https://acme.my.salesforce.com/"},
        http=_http(handler),
    )
    assert out.status == "revoked"
    assert str(seen[0].url) == "https://acme.my.salesforce.com/services/oauth2/revoke"


@pytest.mark.parametrize(
    ("vendor", "tokens", "status"),
    [
        ("notion", {"access_token": "a"}, "not_supported"),
        ("microsoft365", {"access_token": "a"}, "not_supported"),
        ("hubspot", {}, "no_token"),
        ("hubspot", None, "no_token"),
    ],
)
def test_unsupported_or_missing(vendor, tokens, status):
    assert pr.revoke_provider_tokens(vendor, tokens).status == status


def test_provider_error_and_outage_are_failed_not_raised():
    out = pr.revoke_provider_tokens("hubspot", {"refresh_token": "r"}, http=_http(lambda r: httpx.Response(500)))
    assert out.status == "failed"

    def offline(_req):
        raise httpx.ConnectError("offline")

    out = pr.revoke_provider_tokens("slack", {"access_token": "a"}, http=_http(offline))
    assert out.status == "failed" and "ConnectError" in out.detail


# ------------------------------------------------------------------ deletion propagation


def _docs_client() -> _Client:
    return _Client(
        {
            "rag_documents": [
                {"id": "d1", "org_id": ORG, "source_id": "s1", "external_id": "notion:page:p1"},
                {"id": "d2", "org_id": ORG, "source_id": "s1", "external_id": "notion:page:p2"},
                {"id": "d3", "org_id": ORG, "source_id": "s1", "external_id": "manual:upload"},
                {"id": "d4", "org_id": ORG, "source_id": "s2", "external_id": "notion:page:p9"},
            ]
        }
    )


_LIVE = SimpleNamespace(source_deletion_propagation_enabled=True, source_purge_dry_run=False)


def test_reconcile_removes_only_unseen_documents_in_that_source(_reset):
    client = _docs_client()
    checked: list[str] = []
    removed = sl.reconcile_source_documents(
        client,
        _LIVE,
        org_id=ORG,
        source_id="s1",
        external_id_prefix="notion:page:",
        seen_external_ids={"notion:page:p1"},
        is_gone=lambda ext: checked.append(ext) or True,
        sweep_complete=True,
    )
    assert removed == 1 and checked == ["notion:page:p2"]
    assert sorted(r["id"] for r in client.tables["rag_documents"]) == ["d1", "d3", "d4"]
    assert [a["action"] for a in _reset] == ["source.documents_removed"]


def test_reconcile_keeps_unseen_documents_the_provider_says_still_exist():
    client = _docs_client()
    removed = sl.reconcile_source_documents(
        client,
        _LIVE,
        org_id=ORG,
        source_id="s1",
        external_id_prefix="notion:page:",
        seen_external_ids=set(),
        is_gone=lambda ext: False,
        sweep_complete=True,
    )
    assert removed == 0 and len(client.tables["rag_documents"]) == 4


def test_reconcile_off_by_default():
    client = _docs_client()
    removed = sl.reconcile_source_documents(
        client,
        SimpleNamespace(),
        org_id=ORG,
        source_id="s1",
        external_id_prefix="notion:page:",
        seen_external_ids=set(),
        is_gone=lambda ext: True,
        sweep_complete=True,
    )
    assert removed == 0 and len(client.tables["rag_documents"]) == 4


def test_notion_sync_reconciles_only_after_a_clean_sweep(monkeypatch):
    from app.connectors.notion import NotionAPIError
    from app.services import notion_sync_service as ns

    connector = {
        "id": CONN,
        "name": "Notion",
        "environment": "production",
        "config": {"notion_sync_targets": [{"id": "p1", "type": "page"}, {"id": "p2", "type": "page"}]},
    }
    calls: list[set[str]] = []
    monkeypatch.setattr(ns, "ensure_notion_session", lambda *a: ("tok", None))
    monkeypatch.setattr(ns, "ensure_notion_rag_source", lambda *a, **k: "s1")
    monkeypatch.setattr(ns, "_queue_page_ingest", lambda *a, **k: "job")
    monkeypatch.setattr(
        sl, "reconcile_source_documents", lambda *a, **k: calls.append(set(k["seen_external_ids"])) or 1
    )

    class _C(_Client):
        def table(self, name):
            q = super().table(name)
            q.update = lambda *_a, **_k: q
            return q

    client = _C({"connectors": [dict(connector, org_id=ORG)]})
    monkeypatch.setattr(ns, "export_page_text", lambda tok, pid: ("t", "body", None))
    out = ns.run_notion_sync(client, ORG, CONN, SimpleNamespace(), actor_id="u")
    assert calls == [{"notion:page:p1", "notion:page:p2"}] and out["documents_removed"] == 1

    def flaky(tok, pid):
        if pid == "p2":
            raise NotionAPIError("rate limited", status_code=429)
        return ("t", "body", None)

    monkeypatch.setattr(ns, "export_page_text", flaky)
    calls.clear()
    out = ns.run_notion_sync(client, ORG, CONN, SimpleNamespace(), actor_id="u")
    assert calls == [] and out["documents_removed"] == 0


# ------------------------------------------------------------------ disconnect route


@pytest.mark.asyncio
async def test_disconnect_revokes_before_tokens_are_dropped(monkeypatch):
    from uuid import UUID

    from app.routers import connectors as routes
    from app.routers.connectors import ConnectorDeleteRequest, _delete_connector_impl
    from tests.routers.test_managed_connector_flow import Query, row

    cid = UUID(CONN)
    store = [row(id=str(cid), org_id=ORG, config={}, vendor="hubspot", type="hubspot")]
    client = SimpleNamespace(table=lambda name: Query(store if name == "connectors" else []))
    order: list[str] = []
    audits: list[dict[str, Any]] = []
    monkeypatch.setattr(routes, "create_client", lambda *a: client)
    monkeypatch.setattr(routes, "write_audit_event", lambda *a, **kw: audits.append(kw))
    monkeypatch.setattr(
        sl,
        "revoke_on_disconnect",
        lambda *a, **k: order.append("revoke") or pr.RevokeOutcome("revoked", "hubspot"),
    )
    monkeypatch.setattr(
        "app.connectors.platform.clear_connector_oauth_tokens", lambda *a: order.append("clear")
    )
    settings = SimpleNamespace(supabase_url="https://example.supabase.co", supabase_service_role_key="service")
    out = await _delete_connector_impl(cid, ConnectorDeleteRequest(confirmName="desk"), ({"user_id": "u1"}, ORG), settings)
    assert out == {"success": True}
    assert order == ["revoke", "clear"]
    assert audits[-1]["metadata"]["provider_revoke"] == {"status": "revoked", "detail": "hubspot"}
    assert json.dumps(audits[-1]["metadata"])  # serialisable for the audit row
