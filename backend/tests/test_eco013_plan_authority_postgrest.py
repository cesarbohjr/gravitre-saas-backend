"""Actual conversation writer -> SDK HTTP -> PostgREST -> disposable PostgreSQL.

Synthetic local roles/rows; independent SQL readback, not production RLS,
provider execution, customer ingress, or deployed cancellation timing proof.
"""
import os
import secrets
import socket
import subprocess
import time
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import httpx
import jwt
import psycopg
from psycopg.types.json import Jsonb
import pytest
from supabase import ClientOptions, create_client

from app.services.conversation_state_service import ConversationStateService
from app.services.execution_plan_service import ExecutionPlan
from app.services.react_execution_strategy import ReactPlanRuntime
from tests.audit_reader_pg_transport import tcp_pg_cluster
from tests.db.pg_harness import PG_BIN
from tests.services.test_eco013_unfinished_write_authority import _terminal_from_actual_producer

POSTGREST = os.environ.get("GRAVITRE_POSTGREST_BIN")
pytestmark = pytest.mark.skipif(not POSTGREST or PG_BIN is None,
                                reason="Real PostgREST/PostgreSQL binaries required")
ORG, OTHER_ORG, CONV, OTHER_CONV = [str(UUID(int=i)) for i in range(201, 205)]


@pytest.fixture
def plan_api():
    with tcp_pg_cluster() as pg:
        with psycopg.connect(host=pg.sock, port=pg.port, user="postgres", dbname="postgres",
                             autocommit=True) as conn:
            conn.execute("""
                CREATE ROLE plan_writer NOLOGIN;
                CREATE ROLE plan_reader NOLOGIN;
                CREATE ROLE plan_anonymous NOLOGIN;
                CREATE ROLE plan_authenticator LOGIN NOINHERIT;
                GRANT plan_writer, plan_reader, plan_anonymous TO plan_authenticator;
                CREATE TABLE conversations (id uuid PRIMARY KEY, org_id uuid NOT NULL, task_state jsonb NOT NULL);
                GRANT USAGE ON SCHEMA public TO plan_writer,plan_reader,plan_anonymous;
                GRANT SELECT ON conversations TO plan_writer,plan_reader,plan_anonymous;
                GRANT UPDATE ON conversations TO plan_writer;
            """)
            terminal = _terminal_from_actual_producer("cancelled")
            stored = {"execution_plan": terminal.as_dict(), "task_revision": 9,
                      "other_writer": "preserved"}
            conn.execute("INSERT INTO conversations VALUES (%s,%s,%s),(%s,%s,%s)",
                         (CONV,ORG,Jsonb(stored),OTHER_CONV,OTHER_ORG,Jsonb({"task_revision":3,"foreign":"kept"})))
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0)); port = reservation.getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            secret = secrets.token_urlsafe(48)
            env = {k:v for k,v in os.environ.items() if not k.startswith("PGRST_")}
            env.update(PGRST_DB_URI=f"postgresql://plan_authenticator@127.0.0.1:{pg.port}/postgres",
                       PGRST_DB_SCHEMAS="public", PGRST_DB_ANON_ROLE="plan_anonymous", PGRST_JWT_SECRET=secret,
                       PGRST_SERVER_HOST="127.0.0.1", PGRST_SERVER_PORT=str(port))
            api = SimpleNamespace(conn=conn, requests=[], responses=[], before_patch=None)

            def request_hook(request):
                api.requests.append((request.method, str(request.url)))
                if request.method == "PATCH" and api.before_patch is not None:
                    callback, api.before_patch = api.before_patch, None
                    callback()  # independent committed SQL writer, before actual HTTP CAS

            def read(conversation=CONV):
                return conn.execute("SELECT task_state FROM conversations WHERE id=%s", (conversation,)).fetchone()[0]

            def write(state, conversation=CONV):
                conn.execute("UPDATE conversations SET task_state=%s WHERE id=%s", (Jsonb(state),conversation))

            api.read, api.write = read, write
            with (pg.root/"postgrest.log").open("wb") as log:
                process = subprocess.Popen([POSTGREST], env=env, stdout=log, stderr=log)
                try:
                    with httpx.Client(trust_env=False, timeout=5, event_hooks={
                        "request":[request_hook], "response":[lambda response:api.responses.append(response.status_code)],
                    }) as http:
                        for _ in range(100):
                            assert process.poll() is None
                            try:
                                if http.get(base+"/conversations?limit=0").status_code == 200:break
                            except httpx.TransportError:pass
                            time.sleep(.1)
                        else:pytest.fail("Local PostgREST did not become ready")

                        def client(role="plan_writer"):
                            token = jwt.encode({"role":role,"exp":int(time.time())+300}, secret, algorithm="HS256")
                            sdk = create_client(base, token, options=ClientOptions(
                                httpx_client=http, auto_refresh_token=False, persist_session=False))
                            sdk.rest_url = base  # standalone PostgREST, no Supabase /rest/v1 proxy
                            return sdk

                        api.client, api.make_client = client(), client
                        api.requests.clear(); api.responses.clear()
                        yield api
                        assert conn.execute("SELECT count(*) FROM conversations").fetchone()[0] == 2
                finally:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


async def _save(api, settings, patch, *, org=ORG, client=None):
    await ConversationStateService(settings).update_task_state(CONV, org, patch, client=client or api.client)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,step_status,incoming_revision", [("cancelled","pending",4),("blocked","running",5)])
async def test_persisted_unfinished_terminal_survives_late_approval(plan_api,mock_settings,status,step_status,incoming_revision):
    terminal = _terminal_from_actual_producer(status, step_status)
    plan_api.write({"execution_plan":terminal.as_dict(),"task_revision":9})
    foreign = plan_api.read(OTHER_CONV)
    delayed = replace(terminal,terminal_status="waiting_for_approval",revision=incoming_revision)
    await _save(plan_api,mock_settings,{"execution_plan":delayed.as_dict(),"pending_task":{"status":"awaiting_confirm"}})
    stored = plan_api.read()
    assert stored["execution_plan"] == terminal.as_dict() and stored["task_revision"] == 10
    assert stored["pending_task"]["status"] == "cancelled"
    assert plan_api.read(OTHER_CONV) == foreign
    loaded = await ConversationStateService(mock_settings).get_task_state(CONV,ORG,client=plan_api.client)
    assert loaded["execution_plan"]["terminal_status"] == status
    if status == "cancelled":
        with pytest.raises(RuntimeError,match="react_dispatch_blocked:cancelled"):
            ReactPlanRuntime(ExecutionPlan.from_dict(loaded["execution_plan"])).next_step_id("gmail_send_email",0,is_write=True)


@pytest.mark.asyncio
async def test_actual_http_cas_conflict_reloads_independent_committed_cancellation(plan_api,mock_settings):
    cancelled = plan_api.read()
    delayed = replace(ExecutionPlan.from_dict(cancelled["execution_plan"]),terminal_status="waiting_for_approval",revision=4)
    plan_api.write({"execution_plan":delayed.as_dict(),"task_revision":8})
    plan_api.before_patch = lambda:plan_api.write(cancelled)
    await _save(plan_api,mock_settings,{"execution_plan":delayed.as_dict(),"pending_task":{"status":"awaiting_confirm"}})
    stored = plan_api.read()
    assert stored["execution_plan"] == cancelled["execution_plan"]
    assert stored["task_revision"] == 10 and stored["other_writer"] == "preserved"
    assert stored["pending_task"]["status"] == "cancelled"
    patches = [httpx.URL(url) for method,url in plan_api.requests if method == "PATCH"]
    assert len(patches) == 2
    assert [url.params["task_state->>task_revision"] for url in patches] == ["eq.8","eq.9"]
    assert all(url.params["org_id"] == "eq."+ORG and url.params["id"] == "eq."+CONV for url in patches)


@pytest.mark.asyncio
async def test_legacy_unrevisioned_terminal_uses_null_cas_without_reopening(plan_api,mock_settings):
    terminal = plan_api.read()["execution_plan"]
    plan_api.write({"execution_plan":terminal})
    delayed = {**terminal,"terminal_status":"running","revision":4}
    await _save(plan_api,mock_settings,{"execution_plan":delayed})
    assert plan_api.read()["execution_plan"] == terminal and plan_api.read()["task_revision"] == 1
    patch = next(httpx.URL(url) for method,url in plan_api.requests if method == "PATCH")
    assert patch.params["task_state->>task_revision"] == "is.null"


@pytest.mark.asyncio
async def test_foreign_org_cannot_patch_same_conversation_id(plan_api,mock_settings):
    before, foreign = plan_api.read(), plan_api.read(OTHER_CONV)
    await _save(plan_api,mock_settings,{"execution_plan":{**before["execution_plan"],"terminal_status":"running"}},org=OTHER_ORG)
    assert plan_api.read() == before and plan_api.read(OTHER_CONV) == foreign
    assert any(method == "PATCH" for method,_url in plan_api.requests)
    assert all(httpx.URL(url).params["org_id"] == "eq."+OTHER_ORG for _method,url in plan_api.requests)


@pytest.mark.asyncio
async def test_distinct_new_action_can_wait_for_its_own_approval(plan_api,mock_settings):
    old = ExecutionPlan.from_dict(plan_api.read()["execution_plan"])
    new = replace(old,plan_id=str(UUID(int=300)),terminal_status="waiting_for_approval",revision=1)
    await _save(plan_api,mock_settings,{"execution_plan":new.as_dict()})
    assert plan_api.read()["execution_plan"] == new.as_dict() and plan_api.read()["task_revision"] == 10


@pytest.mark.asyncio
async def test_newer_terminal_evidence_can_resolve_inconclusive_plan(plan_api,mock_settings):
    terminal = _terminal_from_actual_producer("verification_inconclusive")
    plan_api.write({"execution_plan":terminal.as_dict(),"task_revision":9})
    verified = replace(terminal,terminal_status="completed",revision=6)
    await _save(plan_api,mock_settings,{"execution_plan":verified.as_dict()})
    assert plan_api.read()["execution_plan"] == verified.as_dict()


@pytest.mark.asyncio
async def test_actual_postgrest_permission_denial_does_not_mutate_stored_state(plan_api,mock_settings):
    before = deepcopy(plan_api.read())
    reader = plan_api.make_client("plan_reader")
    await _save(plan_api,mock_settings,{"clarified_params":{"synthetic":"denied"}},client=reader)
    assert 403 in plan_api.responses
    assert plan_api.read() == before
