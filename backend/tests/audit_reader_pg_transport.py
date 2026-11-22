"""SDK HTTP transport to a disposable PostgreSQL cluster for audit reader tests.

Translates the small PostgREST predicate subset emitted by the real SDK into
parameterized SQL. This tests real persisted ordering/filter semantics, not a
running PostgREST server, production auth, or RLS.
"""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
from types import SimpleNamespace
from uuid import UUID

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from supabase import ClientOptions, create_client
from tests.db.pg_harness import PG_BIN, Pg


FIELDS = {"id", "org_id", "created_at", "action", "actor_id", "resource_type", "resource_id", "metadata"}


@contextmanager
def tcp_pg_cluster():
    """Loopback-only disposable cluster; this sandbox disallows Unix sockets."""
    root = Path(tempfile.mkdtemp(prefix="dec008-pg-"))
    pg = Pg(root, [])
    pg.sock = "127.0.0.1"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        pg.port = str(reservation.getsockname()[1])
    try:
        subprocess.run([str(PG_BIN / "initdb"), "-D", str(pg.data), "-A", "trust",
                        "-U", "postgres", "--no-sync"], check=True, capture_output=True)
        opts = (f"-p {pg.port} -c listen_addresses=127.0.0.1 "
                "-c unix_socket_directories='' -c fsync=off")
        subprocess.run([str(PG_BIN / "pg_ctl"), "-D", str(pg.data), "-o", opts,
                        "-w", "-l", str(root / "log"), "start"], check=True, capture_output=True)
        yield pg
    finally:
        pg.stop()
        shutil.rmtree(root)


def split_terms(value):
    terms, depth, start = [], 0, 0
    for i, char in enumerate(value):
        depth += (char == "(") - (char == ")")
        if char == "," and depth == 0:
            terms.append(value[start:i])
            start = i + 1
    assert depth == 0
    return [*terms, value[start:]]


def predicate(term, values):
    for operator in ("and", "or"):
        if term.startswith(operator + "(") and term.endswith(")"):
            parts = [predicate(t, values) for t in split_terms(term[len(operator) + 1:-1])]
            return "(" + f" {operator.upper()} ".join(parts) + ")"
    field, operator, value = term.split(".", 2)
    assert field in FIELDS
    operators = {"eq": "=", "lt": "<", "gte": ">=", "lte": "<=", "like": "LIKE"}
    assert operator in operators
    values.append(value)
    return f'"{field}" {operators[operator]} %s'


@contextmanager
def postgres_transport(pg, monkeypatch):
    from app.audit import query

    state = SimpleNamespace(rows=[], requests=[], persisted_counts=[])
    with psycopg.connect(host=str(pg.sock), port=pg.port, dbname="postgres", user="postgres",
                         autocommit=True, row_factory=dict_row) as conn:
        conn.execute("""CREATE TABLE audit_events (
            id uuid PRIMARY KEY, org_id uuid NOT NULL, created_at timestamptz NOT NULL,
            action text NOT NULL, actor_id uuid, resource_type text, resource_id uuid, metadata jsonb
        )""")

        def respond(request):
            assert request.method == "GET"
            assert request.url.path == "/rest/v1/audit_events"
            state.requests.append(request)
            # Persist fixture rows once before the first real reader request.
            if len(state.requests) == 1:
                for row in state.rows:
                    conn.execute("""INSERT INTO audit_events
                        (id,org_id,created_at,action,actor_id,resource_type,resource_id,metadata)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (row["id"], row["org_id"], row["created_at"], row["action"], row["actor_id"],
                         row["resource_type"], row["resource_id"], Jsonb(row["metadata"])))
                state.persisted_counts = conn.execute(
                    "SELECT org_id::text, count(*) AS count FROM audit_events GROUP BY org_id ORDER BY org_id"
                ).fetchall()
                assert sum(r["count"] for r in state.persisted_counts) == len(state.rows)
            values, clauses = [], []
            for field, expression in request.url.params.multi_items():
                if field in {"select", "order", "limit"}:
                    continue
                term = field + expression if field in {"and", "or"} else field + "." + expression
                clauses.append(predicate(term, values))
            assert request.url.params["order"] == "created_at.desc,id.desc"
            columns = request.url.params["select"].split(",")
            assert set(columns) <= FIELDS
            values.append(int(request.url.params["limit"]))
            sql = ('SELECT ' + ",".join(f'"{c}"' for c in columns) + ' FROM audit_events WHERE '
                   + " AND ".join(clauses) + ' ORDER BY created_at DESC,id DESC LIMIT %s')
            rows = conn.execute(sql, values).fetchall()
            result = [{k: v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, UUID) else v
                       for k, v in row.items()} for row in rows]
            return httpx.Response(200, json=result)

        with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
            client = create_client("https://offline.invalid", "test-only-key", options=ClientOptions(
                httpx_client=transport, auto_refresh_token=False, persist_session=False,
            ))
            monkeypatch.setattr(query, "shared_service_client", lambda *_: client)
            yield state
