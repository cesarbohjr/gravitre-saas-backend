"""DEC-008: actual Supabase SDK -> real PostgREST -> disposable PostgreSQL/RLS.

No HTTP transport doubles, external project credentials, deployed claims or store
retirement. Set GRAVITRE_POSTGREST_BIN and GRAVITRE_PG_BIN to run locally.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
from types import SimpleNamespace
from uuid import UUID

import httpx
import jwt
import psycopg
from psycopg.types.json import Jsonb
import pytest
from supabase import ClientOptions, create_client

from app.audit import query
from tests.audit_reader_pg_transport import tcp_pg_cluster
from tests.db.pg_harness import PG_BIN, REPO_ROOT
from tests.test_audit_reader_dec008_reproduction import ORG_A, ORG_B, NEW, TIE, OLD, event


POSTGREST = os.environ.get("GRAVITRE_POSTGREST_BIN")
pytestmark = pytest.mark.skipif(not POSTGREST or PG_BIN is None,
                                reason="Real PostgREST and PostgreSQL binaries required")
ACTOR_A = str(UUID(int=201))
ACTOR_B = str(UUID(int=202))
RESOURCE = str(UUID(int=301))
EXPECTED = [str(UUID(int=i)) for i in [90, 15, 14, 13, 12, 11, 1]]


@pytest.fixture
def real_audit_api(monkeypatch, request):
    with tcp_pg_cluster() as pg:
        with psycopg.connect(host=pg.sock, port=pg.port, user="postgres", dbname="postgres",
                             autocommit=True) as conn:
            conn.execute("""
                CREATE ROLE audit_member NOLOGIN;
                CREATE ROLE audit_authenticator LOGIN NOINHERIT;
                GRANT audit_member TO audit_authenticator;
                CREATE TABLE organization_members (org_id uuid, user_id uuid, PRIMARY KEY(org_id,user_id));
                CREATE TABLE audit_events (
                    id uuid PRIMARY KEY, org_id uuid NOT NULL, created_at timestamptz NOT NULL,
                    action text, actor_id uuid, resource_type text, resource_id uuid, metadata jsonb);
                CREATE TABLE audit_logs (
                    id uuid PRIMARY KEY, org_id uuid NOT NULL, created_at timestamptz NOT NULL,
                    action text, user_id uuid, entity_type text, entity_id uuid, details jsonb);
                CREATE TABLE workflow_runs (id uuid PRIMARY KEY,org_id uuid,environment text,status text,
                    created_at timestamptz,workflow_id uuid,required_approvals int,approval_status text);
                CREATE TABLE workflow_steps (run_id uuid,org_id uuid,step_index int,step_name text,
                    step_type text,status text,error_code text);
                CREATE TABLE run_approvals (run_id uuid,org_id uuid,status text);
                CREATE TABLE rag_ingest_jobs (org_id uuid, created_at timestamptz, chunk_count int, status text);
                CREATE TABLE agent_jobs (org_id uuid, created_at timestamptz, kind text, status text);
                ALTER TABLE workflow_runs ADD COLUMN run_type text;
                ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
                ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
                ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
                CREATE POLICY own_membership ON organization_members FOR SELECT TO audit_member
                    USING (user_id = (current_setting('request.jwt.claims',true)::json->>'sub')::uuid);
                CREATE POLICY own_events ON audit_events FOR SELECT TO audit_member USING
                    (EXISTS (SELECT 1 FROM organization_members m WHERE m.org_id=audit_events.org_id));
                CREATE POLICY own_logs ON audit_logs FOR SELECT TO audit_member USING
                    (EXISTS (SELECT 1 FROM organization_members m WHERE m.org_id=audit_logs.org_id));
                GRANT USAGE ON SCHEMA public TO audit_member;
                GRANT SELECT ON organization_members,audit_events,audit_logs TO audit_member;
            """)
            for table in ('workflow_runs','workflow_steps','run_approvals','rag_ingest_jobs','agent_jobs'):
                conn.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
                conn.execute(f'CREATE POLICY own_rows ON {table} FOR SELECT TO audit_member USING '
                             f'(EXISTS (SELECT 1 FROM organization_members m WHERE m.org_id={table}.org_id))')
                conn.execute(f'GRANT SELECT ON {table} TO audit_member')
            conn.execute("INSERT INTO organization_members VALUES (%s,%s),(%s,%s)",
                         (ORG_A, ACTOR_A, ORG_B, ACTOR_B))
            conn.execute("INSERT INTO workflow_runs (id,org_id,environment,status,created_at,workflow_id,required_approvals,approval_status) VALUES (%s,%s,'default','completed',%s,NULL,0,NULL),"
                         "(%s,%s,'default','completed',%s,NULL,0,NULL)",
                         (RESOURCE,ORG_A,TIE,str(UUID(int=302)),ORG_B,TIE))
            fixtures = [event(90, NEW), *[event(i) for i in range(11, 16)], event(1, OLD),
                        event(99, NEW, ORG_B), event(16, TIE, ORG_B), event(2, OLD, ORG_B)]
            for row in fixtures:
                conn.execute("INSERT INTO audit_events VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                             (row['id'],row['org_id'],row['created_at'],row['action'],row['actor_id'],
                              row['resource_type'],row['resource_id'],Jsonb(row['metadata'])))
                conn.execute("INSERT INTO audit_logs VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                             (row['id'],row['org_id'],row['created_at'],row['action'],row['actor_id'],
                              row['resource_type'],row['resource_id'],Jsonb(row['metadata'])))
            # Execute the retained production RPC definition, not a replacement reader.
            conn.execute((REPO_ROOT / "supabase/migrations/20250204000005_audit_query_function.sql").read_text())
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1",0))
                port = reservation.getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            secret = secrets.token_urlsafe(48)
            env = {k:v for k,v in os.environ.items() if not k.startswith("PGRST_")}
            env.update(PGRST_DB_URI=f"postgresql://audit_authenticator@127.0.0.1:{pg.port}/postgres",
                       PGRST_DB_SCHEMAS="public", PGRST_JWT_SECRET=secret,
                       PGRST_SERVER_HOST="127.0.0.1", PGRST_SERVER_PORT=str(port))
            if getattr(request, "param", None) == "capped":
                env["PGRST_DB_MAX_ROWS"] = "2"
            token = jwt.encode({"role":"audit_member","sub":ACTOR_A,"exp":int(time.time())+300},
                               secret,algorithm="HS256")
            requests = []
            with (pg.root / "postgrest.log").open("wb") as log:
                process = subprocess.Popen([POSTGREST], env=env, stdout=log, stderr=log)
                try:
                    with httpx.Client(trust_env=False, timeout=5,
                                      event_hooks={"request":[lambda r: requests.append(str(r.url))]}) as http:
                        for _ in range(100):
                            assert process.poll() is None, (pg.root / "postgrest.log").read_text()
                            try:
                                r = http.get(base+"/audit_events?limit=0",headers={"Authorization":"Bearer "+token})
                                if r.status_code == 200: break
                            except httpx.TransportError:
                                pass
                            time.sleep(.1)
                        else: pytest.fail("real PostgREST did not become ready")
                        client = create_client(base,token,options=ClientOptions(httpx_client=http,
                            auto_refresh_token=False,persist_session=False))
                        # Standalone PostgREST has no Supabase /rest/v1 reverse-proxy prefix.
                        client.rest_url = base
                        monkeypatch.setattr(query,"shared_service_client",lambda *_:client)
                        yield SimpleNamespace(client=client,conn=conn,base=base,http=http,token=token,
                                              requests=requests,process=process)
                        counts = conn.execute("SELECT (SELECT count(*) FROM audit_events),"
                                              "(SELECT count(*) FROM audit_logs)").fetchone()
                        assert counts == (10,10), "read checks must retain both stores and all fixture rows"
                finally:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)


def collect(settings, page_size, *, rpc=False):
    result, cursor = [], None
    for _ in range(20):
        if rpc:
            rows,cursor = query.query_audit_events(settings,ORG_A,"conversation",RESOURCE,page_size,cursor)
        else:
            rows,cursor = query.query_audit_log(settings,ORG_A,page_size,cursor)
        result.extend(r['id'] for r in rows)
        if cursor is None: return result
    pytest.fail("pagination did not terminate")


@pytest.mark.parametrize("page_size",[1,2,3,5,7,10])
def test_real_postgrest_complete_seek_pages(real_audit_api,mock_settings,page_size):
    assert collect(mock_settings,page_size) == EXPECTED
    assert all('/rest/v1' not in url for url in real_audit_api.requests)


@pytest.mark.parametrize("page_size",[1,2,3])
def test_real_rpc_and_table_reader_agree(real_audit_api,mock_settings,page_size):
    assert collect(mock_settings,page_size,rpc=True) == collect(mock_settings,page_size) == EXPECTED
    assert any('/rpc/audit_query' in url for url in real_audit_api.requests)


def test_real_rls_denies_other_tenant_even_without_application_filter(real_audit_api,mock_settings):
    client = real_audit_api.client
    for table in ('audit_events','audit_logs'):
        assert len(client.table(table).select('id').execute().data) == 7
        assert client.table(table).select('id').eq('org_id',ORG_B).execute().data == []
    assert query.query_audit_log(mock_settings,ORG_B,10) == ([],None)
    assert query.query_audit_events(mock_settings,ORG_B,'conversation',RESOURCE,10) == ([],None)
    assert real_audit_api.http.get(real_audit_api.base+'/audit_events').status_code == 401


@pytest.mark.parametrize("payload",[[],None,{"created_at":TIE,"id":"x),org_id.neq.null"}])
def test_real_invalid_cursor_fallback_stays_scoped(real_audit_api,mock_settings,payload):
    import base64
    cursor=base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    rows,_=query.query_audit_log(mock_settings,ORG_A,10,cursor)
    assert [r['id'] for r in rows] == EXPECTED


def test_actual_customer_audit_store_reader(real_audit_api):
    from app.routers.audit import _fetch_rows
    rows=_fetch_rows(real_audit_api.client,ORG_A,None)
    assert {r['id'] for r in rows} == set(EXPECTED)
    assert {r['org_id'] for r in rows} == {ORG_A}
    assert _fetch_rows(real_audit_api.client,ORG_B,None) == []


def test_actual_audit_store_legacy_timestamp_fallback(real_audit_api):
    from app.routers.audit import _fetch_rows
    real_audit_api.conn.execute('ALTER TABLE audit_logs RENAME COLUMN created_at TO timestamp')
    rows=_fetch_rows(real_audit_api.client,ORG_A,None)
    assert {r['id'] for r in rows} == set(EXPECTED)
    assert {r['org_id'] for r in rows} == {ORG_A}
    assert all('timestamp' in r for r in rows)


def test_actual_operator_context_consumer_uses_retained_rpc(real_audit_api,mock_settings):
    from app.operator_module.services.context_packs import build_run_context
    real_audit_api.conn.execute("UPDATE audit_events SET resource_type='workflow_run' WHERE org_id=%s",(ORG_A,))
    context=build_run_context(real_audit_api.client,mock_settings,ORG_A,'default',RESOURCE)
    assert context['run']['id'] == RESOURCE
    assert context['audit']['total_events'] == 5  # Existing recent-five contract, not a full-history count.
    assert len(context['audit']['recent_events']) == 5
    assert any('/rpc/audit_query' in url for url in real_audit_api.requests)
    assert build_run_context(real_audit_api.client,mock_settings,ORG_B,'default',str(UUID(int=302))) is None


def test_actual_run_observability_consumer(real_audit_api):
    from app.services.run_observability_service import _audit_for_run
    assert {r['id'] for r in _audit_for_run(real_audit_api.client,ORG_A,RESOURCE)} == set(EXPECTED)
    assert _audit_for_run(real_audit_api.client,ORG_B,RESOURCE) == []


def test_member_cannot_write_either_store(real_audit_api):
    from postgrest.exceptions import APIError
    for table in ('audit_events','audit_logs'):
        with pytest.raises(APIError) as error:
            real_audit_api.client.table(table).insert({'id':str(UUID(int=999)),'org_id':ORG_A,'created_at':TIE}).execute()
        assert error.value.code == '42501'


def test_membership_revocation_removes_reader_visibility(real_audit_api,mock_settings):
    real_audit_api.conn.execute('DELETE FROM organization_members WHERE user_id=%s',(ACTOR_A,))
    assert collect(mock_settings,2) == []
    assert collect(mock_settings,2,rpc=True) == []
    assert real_audit_api.client.table('audit_logs').select('id').execute().data == []


def test_real_boundary_preserves_optional_filters(real_audit_api,mock_settings):
    cursor=query._encode_cursor(TIE,str(UUID(int=14)))
    rows,_=query.query_audit_log(mock_settings,ORG_A,10,cursor,
        action_prefix='tool.invoke',actor_id=ACTOR_A,resource_type='conversation',start_at=TIE,end_at=TIE)
    assert [r['id'] for r in rows] == [str(UUID(int=i)) for i in (13,12,11)]


@pytest.mark.parametrize("real_audit_api", ["capped"], indirect=True)
def test_capped_soc2_export_retains_compliance_store(real_audit_api, monkeypatch, mock_settings):
    from app.routers import enterprise
    api = real_audit_api
    # Deliberately different store semantics: only the compliance row changes.
    api.conn.execute("UPDATE audit_logs SET action='enterprise.settings.updated' WHERE id=%s",
                     (EXPECTED[0],))
    assert len(api.client.table("audit_logs").select("*").eq("org_id", ORG_A).execute().data) == 2
    monkeypatch.setattr(enterprise, "shared_service_client", lambda *_: api.client)
    monkeypatch.setattr(enterprise, "get_plan_for_org", lambda *_: {})
    monkeypatch.setattr(enterprise, "require_feature", lambda *_: None)
    report = enterprise.export_soc2_bundle({"user_id": ACTOR_A}, ORG_A, mock_settings)
    assert report["summary"]["auditLogCount"] == 7
    assert report["summary"]["toolInvocationCount"] == 6
    assert report["summary"]["adminActionCount"] == 1
    assert enterprise.export_soc2_bundle({"user_id": ACTOR_A}, ORG_B, mock_settings)["summary"]["auditLogCount"] == 0
    assert api.conn.execute("SELECT action FROM audit_events WHERE id=%s", (EXPECTED[0],)).fetchone()[0] == "tool.invoke.completed"


@pytest.mark.parametrize("real_audit_api", ["capped"], indirect=True)
def test_capped_workforce_analytics_uses_all_compliance_rows(real_audit_api, monkeypatch, mock_settings):
    from app.routers import enterprise
    api = real_audit_api
    api.conn.execute("UPDATE audit_logs SET action='agent.handoff.completed' WHERE id=%s", (EXPECTED[0],))
    api.conn.execute("UPDATE audit_logs SET action='tool.invoke.failed' WHERE id=%s", (EXPECTED[1],))
    monkeypatch.setattr(enterprise, "shared_service_client", lambda *_: api.client)
    report = enterprise.workforce_analytics({"user_id": ACTOR_A}, ORG_A, mock_settings)
    assert report["handoffs"] == 1
    assert report["toolSuccessRate"] == 83.33
    assert enterprise.workforce_analytics({"user_id": ACTOR_A}, ORG_B, mock_settings)["handoffs"] == 0


@pytest.mark.parametrize("real_audit_api", ["capped"], indirect=True)
def test_capped_connector_timeseries_matches_independent_sql(real_audit_api, monkeypatch, mock_settings):
    from datetime import datetime
    from app.metrics import service
    api = real_audit_api
    api.conn.execute("UPDATE audit_events SET action='slack.send.sent'")
    monkeypatch.setattr(service, "_client", lambda *_: api.client)
    monkeypatch.setattr(service, "parse_range", lambda *_: ("7d", datetime.fromisoformat(OLD), datetime.fromisoformat(NEW)))
    monkeypatch.setattr(service, "_rollup_enabled", lambda: False)
    report = service.timeseries_metrics(mock_settings, ORG_A, "7d", "connector_sends_total")
    expected = api.conn.execute("SELECT count(*) FROM audit_events WHERE org_id=%s AND action='slack.send.sent'", (ORG_A,)).fetchone()[0]
    assert report["points"] == [{"date": "2026-11-22", "value": expected}]
    assert expected == 7
    assert service.timeseries_metrics(mock_settings, ORG_B, "7d", "connector_sends_total")["points"] == []


@pytest.mark.parametrize("real_audit_api", ["capped"], indirect=True)
def test_capped_weekly_throughput_matches_independent_sql(real_audit_api, monkeypatch, mock_settings):
    from datetime import datetime, timezone
    from app.metrics import service
    api = real_audit_api
    api.conn.execute("UPDATE audit_events SET metadata=jsonb_build_object('records', 3)")
    monkeypatch.setattr(service, "_client", lambda *_: api.client)
    monkeypatch.setattr(service, "_start_of_week_utc", lambda: datetime(2026, 11, 16, tzinfo=timezone.utc))
    report = service.weekly_throughput_metrics(mock_settings, ORG_A)
    expected = api.conn.execute("SELECT sum((metadata->>'records')::int) FROM audit_events WHERE org_id=%s", (ORG_A,)).fetchone()[0]
    assert report["days"][-1]["records"] == expected == 21
    assert sum(day["records"] for day in service.weekly_throughput_metrics(mock_settings, ORG_B)["days"]) == 0


@pytest.mark.parametrize("real_audit_api", ["capped"], indirect=True)
def test_capped_scan_is_complete_unique_and_fails_closed_at_budget(real_audit_api, monkeypatch):
    from app.audit import consumer_pagination as reader
    api = real_audit_api
    for store in ("audit_logs", "audit_events"):
        rows = reader.scan_audit_rows(api.client, store, ORG_A)
        assert [row["id"] for row in rows] == sorted(EXPECTED)
        assert reader.scan_audit_rows(api.client, store, ORG_B) == []
    monkeypatch.setattr(reader, "_MAX_ROWS", 3)
    with pytest.raises(RuntimeError, match="safe synchronous limit"):
        reader.scan_audit_rows(api.client, "audit_logs", ORG_A)


@pytest.mark.parametrize("real_audit_api", ["capped"], indirect=True)
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("scan_limit", [6, 7, 8])
def test_capped_customer_reader_truthful_truncation(real_audit_api, monkeypatch, mock_settings, legacy, scan_limit):
    from app.routers import audit
    api = real_audit_api
    if legacy:
        api.conn.execute("ALTER TABLE audit_logs RENAME COLUMN created_at TO timestamp")
    monkeypatch.setattr(audit, "FETCH_MAX", scan_limit)
    monkeypatch.setattr(audit, "shared_service_client", lambda *_: api.client)
    monkeypatch.setattr(audit, "get_plan_for_org", lambda *_: {})
    monkeypatch.setattr(audit, "require_feature", lambda *_: None)
    monkeypatch.setattr(audit, "_resolve_actor_names", lambda *_: None)
    from datetime import datetime
    rows = audit._fetch_rows(api.client, ORG_A, "tool.invoke.completed",
                             from_dt=datetime.fromisoformat(OLD))
    assert [row["id"] for row in rows] == EXPECTED[:scan_limit+1]
    assert audit._fetch_rows(api.client, ORG_B, None) == []
    logs, truncated = audit._prepare_logs(api.client, ORG_A, action=None,
        user_id=None, entity_type=None, from_dt=None, to_dt=None,
        category=None, outcome=None, q=None)
    assert [log["id"] for log in logs] == EXPECTED[:scan_limit]
    assert truncated is (scan_limit < len(EXPECTED))
    summary = audit.audit_summary(_user={"user_id": ACTOR_A}, org_id=ORG_A, settings=mock_settings)
    assert summary["truncated"] is truncated and summary["scanLimit"] == scan_limit
    assert sum(summary["byAction"].values()) == min(scan_limit, len(EXPECTED))
    exported = audit.export_audit(exporter=({"user_id": ACTOR_A}, ORG_A), settings=mock_settings, format="json")
    body = json.loads(exported.body)
    assert body["truncated"] is truncated and body["total"] == min(scan_limit, len(EXPECTED))
    csv = audit.export_audit(exporter=({"user_id": ACTOR_A}, ORG_A), settings=mock_settings, format="csv")
    assert csv.headers["X-Audit-Truncated"] == str(truncated).lower()
