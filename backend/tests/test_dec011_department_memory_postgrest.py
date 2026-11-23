"""Actual SDK -> PostgREST -> disposable PG; no deployed/RLS certification.

The fixture deliberately omits the RPC to exercise the real missing-RPC fallback.
Embedding I/O alone is stubbed. No external database/provider credentials used.
"""
import os
import secrets
import socket
import subprocess
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import httpx
import jwt
import psycopg
import pytest
from supabase import ClientOptions, create_client

from app.services.agent_memory_service import search_department_memories
from tests.audit_reader_pg_transport import tcp_pg_cluster
from tests.db.pg_harness import PG_BIN

POSTGREST = os.environ.get("GRAVITRE_POSTGREST_BIN")
pytestmark = pytest.mark.skipif(not POSTGREST or PG_BIN is None,
                                reason="Real PostgREST and PostgreSQL binaries required")
ORG, OTHER_ORG, DEPT, OTHER_DEPT, AGENT = [str(UUID(int=i)) for i in range(101, 106)]
NOW = datetime(2026, 11, 23, 7, 0, tzinfo=timezone.utc)


@pytest.fixture
def memory_api(monkeypatch):
    from app.services import agent_memory_service as service

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz else NOW.replace(tzinfo=None)

    monkeypatch.setattr(service, "datetime", Clock)
    with tcp_pg_cluster() as pg:
        with psycopg.connect(host=pg.sock, port=pg.port, user="postgres", dbname="postgres", autocommit=True) as conn:
            conn.execute("""
                CREATE ROLE memory_reader NOLOGIN;
                CREATE ROLE memory_authenticator LOGIN NOINHERIT;
                GRANT memory_reader TO memory_authenticator;
                CREATE TABLE agent_memories (
                    id uuid PRIMARY KEY,org_id uuid,agent_id uuid,department_id uuid,
                    content text,category text,provenance text,confidence int,usage_count int,
                    editable boolean,created_at timestamptz,is_active boolean,is_current boolean,expires_at timestamptz);
                GRANT USAGE ON SCHEMA public TO memory_reader;
                GRANT SELECT ON agent_memories TO memory_reader;
            """)
            # Invalid rows are newer: filtering must happen BEFORE the limit.
            fixtures = [
                (1, ORG, DEPT, True, True, None, "fact"),
                (2, ORG, DEPT, None, None, None, "fact"),
                (3, ORG, DEPT, True, True, "2099-01-01T00:00:00Z", "fact"),
                (4, ORG, DEPT, True, True, None, "preference"),
                (5, ORG, DEPT, False, True, None, "fact"),
                (6, ORG, DEPT, True, False, None, "fact"),
                (7, ORG, DEPT, True, True, "2020-01-01T00:00:00Z", "fact"),
                (8, ORG, DEPT, True, True, NOW.isoformat(), "fact"),
                (9, OTHER_ORG, DEPT, True, True, None, "fact"),
                (10, ORG, OTHER_DEPT, True, True, None, "fact"),
            ]
            for number,org,dept,active,current,expiry,category in fixtures:
                conn.execute("INSERT INTO agent_memories VALUES (%s,%s,%s,%s,%s,%s,'synthetic',90,0,true,%s,%s,%s,%s)",
                             (str(UUID(int=number)),org,AGENT,dept,f"memory-{number}",category,
                              f"2026-01-{number:02}T00:00:00Z",active,current,expiry))
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1",0));port=reservation.getsockname()[1]
            base=f"http://127.0.0.1:{port}"
            secret=secrets.token_urlsafe(48)
            token=jwt.encode({"role":"memory_reader","exp":int(time.time())+300},secret,algorithm="HS256")
            env={k:v for k,v in os.environ.items() if not k.startswith("PGRST_")}
            env.update(PGRST_DB_URI=f"postgresql://memory_authenticator@127.0.0.1:{pg.port}/postgres",
                       PGRST_DB_SCHEMAS="public",PGRST_DB_ANON_ROLE="memory_reader",
                       PGRST_JWT_SECRET=secret,
                       PGRST_SERVER_HOST="127.0.0.1",PGRST_SERVER_PORT=str(port))
            requests=[]
            with (pg.root/"postgrest.log").open("wb") as log:
                process=subprocess.Popen([POSTGREST],env=env,stdout=log,stderr=log)
                try:
                    with httpx.Client(trust_env=False,timeout=5,
                                      event_hooks={"request":[lambda r:requests.append(str(r.url))]}) as http:
                        for _ in range(100):
                            assert process.poll() is None,(pg.root/"postgrest.log").read_text()
                            try:
                                if http.get(base+"/agent_memories?limit=0").status_code==200:break
                            except httpx.TransportError:pass
                            time.sleep(.1)
                        else:pytest.fail("PostgREST did not become ready")
                        requests.clear()
                        client=create_client(base,token,options=ClientOptions(
                            httpx_client=http,auto_refresh_token=False,persist_session=False))
                        # Standalone PostgREST has no Supabase /rest/v1 proxy.
                        client.rest_url=base
                        with patch.object(service,"get_embedding",return_value=[0.1]):
                            yield SimpleNamespace(client=client,conn=conn,requests=requests,root=pg.root)
                        assert conn.execute("SELECT count(*) FROM agent_memories").fetchone()[0]==10
                finally:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


@pytest.mark.parametrize("category,top_k,expected", [
    (None,10,[4,3,2,1]), ("fact",10,[3,2,1]), ("preference",10,[4]),
    ("fact",2,[3,2]), ("all",10,[4,3,2,1]),
])
def test_real_missing_rpc_fallback_excludes_stale_and_foreign_rows(memory_api,mock_settings,category,top_k,expected):
    rows=search_department_memories(mock_settings,memory_api.client,ORG,DEPT,
                                    query="policy",category=category,top_k=top_k)
    assert [r["id"] for r in rows]==[str(UUID(int=i)) for i in expected]
    assert all(r["org_id"]==ORG and r["department_id"]==DEPT for r in rows)
    assert all(r["source"]=="department_shared_memory" and r["score"]==0 for r in rows)
    assert len(memory_api.requests)==2
    assert "/rpc/agent_memory_search_by_department" in memory_api.requests[0]
    assert "/agent_memories?" in memory_api.requests[1]


@pytest.mark.asyncio
async def test_actual_kernel_department_recall_consumes_only_live_fallback_rows(memory_api,mock_settings):
    from app.services.cognitive_turn_kernel import CognitiveTurnKernel, CognitiveTurnRequest

    # Exercise the department reader independently of the optional later
    # governance snapshot. Other stores are isolated, not substituted readers.
    mock_settings.dialogue_memory_governance_v1=False
    with (
        patch("app.services.hybrid_memory_service.HybridMemoryService.query_all_memory",
              new_callable=AsyncMock,return_value={"episodic_memories":[],"graph_context":[]}),
        patch("app.services.agent_memory_service.search_agent_memories",return_value=[]),
        patch("app.rag.department.resolve_department_id_for_agent",return_value=(DEPT,AGENT)),
        patch("app.services.workspace_memory_service.recall_workspace",return_value=[]),
        patch("app.services.cross_conversation_ledger_memory.feature_enabled",return_value=False),
    ):
        pack=await CognitiveTurnKernel(mock_settings)._recall(
            CognitiveTurnRequest(org_id=ORG,agent_id=AGENT,message="policy",client=memory_api.client),
            memory_api.client)
    actual={r["id"] for bucket in pack.values() if isinstance(bucket,list)
            for r in bucket if isinstance(r,dict) and r.get("id")}
    assert actual=={str(UUID(int=i)) for i in [1,2,3,4]}
    for i in range(5,11):
        assert f"memory-{i}" not in pack["prompt_section"]
