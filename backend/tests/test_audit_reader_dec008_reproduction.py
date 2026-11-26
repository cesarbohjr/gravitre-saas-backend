"""DEC-008 regressions against the actual reader and Supabase SDK.

HTTP transport is isolated, with memory and disposable PostgreSQL backends.
Neither backend certifies a running PostgREST server, RLS, or deployed acceptance.
"""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from supabase import ClientOptions, create_client

from app.audit import query
from tests.db.pg_harness import PG_BIN


ORG_A = str(UUID(int=101))
ORG_B = str(UUID(int=102))
NEW = "2026-11-22T12:00:01+00:00"
TIE = "2026-11-22T12:00:00+00:00"
OLD = "2026-11-22T11:59:59+00:00"


def event(number, timestamp=TIE, org=ORG_A):
    return {
        "id": str(UUID(int=number)), "org_id": org,
        "created_at": timestamp, "action": "tool.invoke.completed",
        "actor_id": str(UUID(int=201)), "resource_type": "conversation",
        "resource_id": str(UUID(int=301)), "metadata": {},
    }


@pytest.fixture(params=["memory", "postgres"])
def isolated_transport(monkeypatch, request):
    if request.param == "postgres":
        if PG_BIN is None:
            pytest.skip("PostgreSQL server binaries not installed")
        from tests.audit_reader_pg_transport import postgres_transport, tcp_pg_cluster

        with tcp_pg_cluster() as pg:
            with postgres_transport(pg, monkeypatch) as state:
                yield state
        return
    state = SimpleNamespace(rows=[], requests=[])

    def matches(row, term):
        from tests.audit_reader_pg_transport import split_terms

        for boolean in ("and", "or"):
            if term.startswith(boolean + "(") and term.endswith(")"):
                results = [matches(row, part) for part in split_terms(term[len(boolean) + 1:-1])]
                return all(results) if boolean == "and" else any(results)
        field, operator, value = term.split(".", 2)
        if operator == "eq":
            return row[field] == value
        if operator == "lt":
            return row[field] < value
        if operator == "gte":
            return row[field] >= value
        if operator == "lte":
            return row[field] <= value
        if operator == "like":
            return row[field].startswith(value.rstrip("%"))
        raise AssertionError(f"unhandled transport predicate: {operator}")

    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/audit_events"
        state.requests.append(request)
        rows = list(state.rows)
        # A transport-side relational oracle, not a replacement audit reader:
        # apply only predicates actually sent by the real SDK and reader.
        for field, expression in request.url.params.multi_items():
            if field in {"select", "order", "limit"}:
                continue
            term = field + expression if field in {"and", "or"} else field + "." + expression
            rows = [r for r in rows if matches(r, term)]
        assert request.url.params["order"] == "created_at.desc,id.desc"
        rows.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
        rows = rows[:int(request.url.params["limit"])]
        columns = request.url.params["select"].split(",")
        return httpx.Response(200, json=[{k: r[k] for k in columns} for r in rows])

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = create_client("https://offline.invalid", "test-only-key", options=ClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
        monkeypatch.setattr(query, "shared_service_client", lambda *_: client)
        yield state


def traverse(settings, limit=2, **filters):
    pages = []
    cursor = None
    for _ in range(20):
        rows, cursor = query.query_audit_log(settings, ORG_A, limit, cursor=cursor, **filters)
        pages.append([r["id"] for r in rows])
        if cursor is None:
            return pages
    pytest.fail("reader never terminated")


def test_equal_timestamp_multi_page_is_complete(isolated_transport, mock_settings):
    isolated_transport.rows = [event(90, NEW), *[event(i) for i in range(11, 16)],
                               event(1, OLD), event(99, NEW, ORG_B), event(16, TIE, ORG_B)]
    pages = traverse(mock_settings)
    expected = [str(UUID(int=i)) for i in [90, 15, 14, 13, 12, 11, 1]]
    actual = [i for page in pages for i in page]
    assert actual == expected, {"pages": pages, "missing": sorted(set(expected) - set(actual))}


def test_tenant_boundary_and_stable_timestamp_pages(isolated_transport, mock_settings):
    isolated_transport.rows = [event(90, NEW), event(15), event(1, OLD),
                               event(99, NEW, ORG_B), event(50, TIE, ORG_B), event(2, OLD, ORG_B)]
    assert traverse(mock_settings, limit=1) == [[str(UUID(int=i))] for i in [90, 15, 1]]
    assert all(r.url.params["org_id"] == f"eq.{ORG_A}" for r in isolated_transport.requests)
    assert all(r.url.params["limit"] == "2" for r in isolated_transport.requests)


def test_other_tenant_cursor_cannot_remove_org_restriction(isolated_transport, mock_settings):
    isolated_transport.rows = [event(15), event(1, OLD), event(14, TIE, ORG_B)]
    cursor = query._encode_cursor(TIE, str(UUID(int=14)))
    rows, _ = query.query_audit_log(mock_settings, ORG_A, 10, cursor=cursor)
    assert [r["id"] for r in rows] == [str(UUID(int=1))]
    assert isolated_transport.requests[-1].url.params["org_id"] == f"eq.{ORG_A}"


def test_time_window_filters_remain_inclusive(isolated_transport, mock_settings):
    isolated_transport.rows = [event(90, NEW), event(15), event(1, OLD), event(99, TIE, ORG_B)]
    assert traverse(mock_settings, limit=1, start_at=TIE, end_at=NEW) == [
        [str(UUID(int=90))], [str(UUID(int=15))],
    ]


def test_cursor_round_trip_preserves_id():
    identifier = str(UUID(int=15))
    assert query._decode_cursor(query._encode_cursor(TIE, identifier)) == (TIE, identifier)


@pytest.mark.parametrize("cursor", ["not-base64", "e30", "eyJpZCI6MX0"])
def test_invalid_cursor_falls_back_to_tenant_scoped_first_page(cursor, isolated_transport, mock_settings):
    isolated_transport.rows = [event(15), event(99, TIE, ORG_B)]
    rows, next_cursor = query.query_audit_log(mock_settings, ORG_A, 2, cursor=cursor)
    assert [r["id"] for r in rows] == [str(UUID(int=15))]
    assert next_cursor is None
    assert isolated_transport.requests[-1].url.params["org_id"] == f"eq.{ORG_A}"


@pytest.mark.parametrize("payload", [[], None, 17, "text"])
def test_non_object_cursor_is_rejected_without_exception(payload):
    cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert query._decode_cursor(cursor) is None


@pytest.mark.parametrize("payload", [
    {"created_at": "", "id": str(UUID(int=15))},
    {"created_at": "not-a-date", "id": str(UUID(int=15))},
    {"created_at": "2026-11-22T12:00:00", "id": str(UUID(int=15))},
    {"created_at": TIE, "id": ""},
    {"created_at": TIE, "id": "not-a-uuid"},
    {"created_at": TIE, "id": "x),org_id.neq.null"},
    {"created_at": TIE + ",org_id.neq.null", "id": str(UUID(int=15))},
    {"created_at": None, "id": str(UUID(int=15))},
    {"created_at": TIE, "id": []},
])
def test_invalid_cursor_fields_cannot_enter_filter_grammar(payload, isolated_transport, mock_settings):
    cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert query._decode_cursor(cursor) is None
    isolated_transport.rows = [event(15), event(99, TIE, ORG_B)]
    rows, next_cursor = query.query_audit_log(mock_settings, ORG_A, 2, cursor=cursor)
    assert [r["id"] for r in rows] == [str(UUID(int=15))]
    assert next_cursor is None
    assert isolated_transport.requests[-1].url.params["org_id"] == f"eq.{ORG_A}"
    assert "or" not in isolated_transport.requests[-1].url.params


def test_cursor_canonicalizes_timestamp_and_uuid():
    identifier = str(UUID(int=250))
    cursor = query._encode_cursor("2026-11-22T12:00:00Z", identifier.upper())
    assert query._decode_cursor(cursor) == (TIE, identifier)


def test_seek_boundary_remains_inside_all_filters(isolated_transport, mock_settings):
    correct = [event(i) for i in range(11, 16)]
    excluded = [dict(event(18), action="other.action"), dict(event(17), actor_id=str(UUID(int=202))),
                dict(event(16), resource_type="workflow"), event(10, TIE, ORG_B)]
    isolated_transport.rows = correct + excluded
    pages = traverse(mock_settings, action="tool.invoke.completed", actor_id=str(UUID(int=201)),
                     resource_type="conversation", start_at=TIE, end_at=TIE)
    assert [i for page in pages for i in page] == [str(UUID(int=i)) for i in range(15, 10, -1)]
    assert len(pages) == 3


def test_rpc_reader_preserves_both_cursor_components(monkeypatch, mock_settings):
    captured = {}

    class RpcClient:
        def rpc(self, name, payload):
            captured.update(name=name, payload=payload)
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=[]))

    monkeypatch.setattr(query, "shared_service_client", lambda *_: RpcClient())
    identifier = str(UUID(int=15))
    assert query.query_audit_events(mock_settings, ORG_A, "conversation", str(UUID(int=301)),
                                    2, cursor=query._encode_cursor(TIE, identifier)) == ([], None)
    assert captured["name"] == "audit_query"
    assert captured["payload"]["p_cursor_created_at"] == TIE
    assert captured["payload"]["p_cursor_id"] == identifier
    assert captured["payload"]["p_org_id"] == ORG_A
