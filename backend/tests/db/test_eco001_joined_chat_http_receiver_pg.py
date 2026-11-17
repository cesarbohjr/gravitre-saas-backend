"""ECO-001 joined HTTP Chat -> governed invoke -> independent receiver -> SQL ledger.

The mounted FastAPI route, signed JWT verification, real Chat execution adapter,
ToolContext, tool_service.invoke_tool and Postgres claim/finalize are exercised.
The provider is an isolated *test* process, not a third-party live account.
The durable variants additionally exercise the actual claim/replay, connector run
finalizer, conversation outcome builders, declared entity verifier and core SQL
writers, then relay the actual terminal outbox to a durable synthetic consumer.
Supabase and conversation persistence use narrow SQL transport adapters; HITL
lookup, vendor credentials/read transport and optional channels are adapted.
This is not production, real HubSpot, production CAS/RLS or physical voice proof.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
import time
import urllib.request
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import psycopg
from psycopg.types.json import Jsonb
import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.main import app
from app.routers import assistant
from app.services import chat_connector_execution_service, conversation_state_service, tool_service
from app.services.chat_connector_execution_service import ChatConnectorExecutionService, ConnectorActionPlan
from app.services.tool_registry import get_tool_registry
from app.services.tool_types import NormalizedResult
from app.services.write_invoke_idempotency import WriteClaimResult, WriteFinalizeResult
from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_write_invoke_idempotency_pg import BOOTSTRAP_SQL, ORG_A, _claim, _finalize
from tests.db.test_autonomous_independent_write_pg import IndependentFixture

pytestmark = requires_pg
ACTION = "hubspot.contacts.create"
CONVERSATION = "joined-chat-conversation"
ACTOR = "44444444-4444-4444-8444-444444444444"


class ScopedQuery:
    def __init__(self):
        self.filters = []

    def select(self, *_):
        return self

    def eq(self, name, value):
        self.filters.append((name, value))
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return SimpleNamespace(data=[{"id": CONVERSATION}] if all(
            item in self.filters for item in (
                ("id", CONVERSATION), ("org_id", ORG_A), ("user_id", ACTOR)
            )
        ) else [])


class OrgSettingsQuery:
    def __init__(self):
        self.filters = []

    def select(self, *_):
        return self

    def eq(self, name, value):
        self.filters.append((name, value))
        return self

    def limit(self, *_):
        return self

    def execute(self):
        assert ("id", ORG_A) in self.filters
        return SimpleNamespace(data=[{"settings": {}}])


class ScopedDb:
    def __init__(self):
        self.lookups = []

    def table(self, table):
        if table == "organizations":
            return OrgSettingsQuery()
        assert table == "conversations", "Unexpected Supabase read at the tested boundary"
        query = ScopedQuery()
        self.lookups.append(query)
        return query


class DurableScopedDb(ScopedDb):
    """Conversation ownership transport plus unmodified canonical SQL repository."""
    def __init__(self, pg):
        super().__init__()
        from tests.master_qa.canonical_pg_repository import PgRepositoryClient
        self.canonical = PgRepositoryClient(pg)

    def table(self, table):
        if table in {"organizations", "conversations"}:
            return super().table(table)
        return self.canonical.table(table)

    def rpc(self, name, params):
        return self.canonical.rpc(name, params)


class SqlConversationState:
    """SQL transport adapter; production claim, outcome builders and merge execute.

    This does not certify production PostgREST/RLS or its concurrent CAS RPC.
    Each state mutation below takes a real SQL row lock in the disposable DB.
    """
    def __init__(self, pg, state):
        self.pg = pg
        pg.psql("CREATE TABLE public.qa_chat_state (id text, org_id uuid, state jsonb, PRIMARY KEY(id, org_id))")
        with self.connect() as conn:
            conn.execute("INSERT INTO public.qa_chat_state VALUES (%s,%s,%s)",
                         (CONVERSATION, ORG_A, Jsonb(state)))

    def connect(self):
        return psycopg.connect(host=str(self.pg.sock), port=self.pg.port, dbname="postgres", user="postgres")

    async def get_task_state(self, conversation_id, org_id, **_kwargs):
        with self.connect() as conn:
            row = conn.execute("SELECT state FROM public.qa_chat_state WHERE id=%s AND org_id=%s",
                               (conversation_id, org_id)).fetchone()
        assert row is not None
        return row[0]

    async def update_task_state_from(self, conversation_id, org_id, build, **_kwargs):
        from app.services.conversation_state_service import ConversationStateService
        with self.connect() as conn:
            row = conn.execute("SELECT state FROM public.qa_chat_state WHERE id=%s AND org_id=%s FOR UPDATE",
                               (conversation_id, org_id)).fetchone()
            assert row is not None
            patch_value = build(row[0])
            state = ConversationStateService._merge_task_state(row[0], patch_value) if patch_value else row[0]
            conn.execute("UPDATE public.qa_chat_state SET state=%s WHERE id=%s AND org_id=%s",
                         (Jsonb(state), conversation_id, org_id))
        return state

    async def update_task_state(self, conversation_id, org_id, updates, **kwargs):
        return await self.update_task_state_from(conversation_id, org_id, lambda _: updates, **kwargs)

    async def compare_and_set_pending_status(self, conversation_id, org_id, *, expected_status, updates, **_kwargs):
        accepted = []
        def claim(state):
            if (state.get("pending_task") or {}).get("status") != expected_status:
                return None
            accepted.append(True)
            return updates
        await self.update_task_state_from(conversation_id, org_id, claim)
        return bool(accepted)


@pytest.mark.parametrize("journey", ["ledger", "durable", "cancel_before_verify", "revoked_before_dispatch", "foreign_actor"])
def test_signed_approved_chat_http_matches_independent_receiver_and_durable_ledger(tmp_path, journey):
    settings = Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test", supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test", write_authority_mode="enforce",
        write_invoke_idempotency_enabled=True,
        private_connector_runtime_enabled=False,
    )
    now = int(time.time())
    token = jwt.encode(
        {"sub": ACTOR, "aud": settings.jwt_audience, "iss": settings.jwt_issuer,
         "iat": now, "exp": now + 300},
        settings.supabase_jwt_secret, algorithm="HS256",
    )
    plan = ConnectorActionPlan(
        tool_name="hubspot_contacts_create", invoke_action=ACTION,
        integration="hubspot", kind="write", label="Create contact",
        args={"properties": {"firstname": "Joined QA"}},
        requires_approval=True,
    )
    approved = {
        **ChatConnectorExecutionService.plan_to_dict(plan),
        "_approval_queue_id": "eco001-joined-chat-approval",
        "hitl_action_kind": "write",
    }
    state = {"pending_task": {
        "type": "connector_action", "status": "awaiting_confirm",
        "params": approved,
    }}
    if journey == "revoked_before_dispatch":
        state["pending_task"]["status"] = "cancelled"
    elif journey == "foreign_actor":
        state["pending_task"]["actor_id"] = "55555555-5555-4555-8555-555555555555"
    store = MagicMock()
    store.get_task_state = AsyncMock(return_value=state)
    store.update_task_state = AsyncMock(return_value=state)
    store.update_task_state_from = AsyncMock(return_value=state)
    db = ScopedDb()
    receiver = IndependentFixture(
        tmp_path / "eco001-joined-chat-provider.sqlite3",
        b"<h1>Independent QA</h1>", capability="eco001-joined-chat-cap",
    )
    migration = (MIGRATIONS / "20261016032018_write_invoke_idempotency.sql").read_text()
    grants = (MIGRATIONS / "20261016032029_write_invoke_idempotency_grants.sql").read_text()
    try:
        from tests.master_qa.canonical_pg_repository import canonical_pg_cluster
        durable = journey != "ledger"
        cluster = canonical_pg_cluster() if durable else pg_cluster(BOOTSTRAP_SQL, migration, grants)
        with cluster as pg:
            if durable:
                pg.psql(f"INSERT INTO public.organizations VALUES ('{ORG_A}')")
                # Production supports the nonterminal verification state; the
                # older minimal fixture omitted it. Do not relax other states.
                pg.psql("ALTER TABLE public.workflow_runs DROP CONSTRAINT workflow_runs_status_check")
                pg.psql("ALTER TABLE public.workflow_runs ADD CONSTRAINT workflow_runs_status_check CHECK (status IN ('running','completed','failed','cancelled','pending_approval','awaiting_approval','paused','partial_success','flagged_for_review','verification_inconclusive','verifying'))")
                pg.psql(migration); pg.psql(grants)
                from tests.master_qa.test_canonical_repository_persistence_pg import _core_effect_tables
                _core_effect_tables(pg)
                db = DurableScopedDb(pg)
                store = SqlConversationState(pg, state)
            keys = []
            verification_work = []

            def claim(_client, *, org_id, idempotency_key, **_kw):
                assert org_id == ORG_A
                keys.append(idempotency_key)
                row = _claim(pg, org_id, idempotency_key)
                return WriteClaimResult(
                    outcome=row["outcome"], claim_token=row.get("claim_token"),
                    status=row.get("status"), reason=row.get("reason"),
                    replay=NormalizedResult(success=True, action=ACTION, data={"id": "1"})
                    if row["outcome"] == "replay" else None,
                )

            def finalize(_client, *, org_id, idempotency_key, claim_token, status, **_kw):
                assert org_id == ORG_A and status == "completed"
                row = _finalize(pg, org_id, idempotency_key, claim_token, status)
                return WriteFinalizeResult(outcome=row["outcome"])

            def provider(_ctx, _params):
                request = urllib.request.Request(
                    receiver.origin + "/write",
                    data=json.dumps({"cap": "eco001-joined-chat-cap"}).encode(),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=7) as response:
                    assert response.status == 204
                return NormalizedResult(
                    success=True, action=ACTION, data={"id": "1"},
                )

            async def registry_invoke(*, ctx, invoke_action, args, tool_name, **_kwargs):
                assert invoke_action == ACTION and tool_name == plan.tool_name
                observed = tool_service.invoke_tool(ctx, invoke_action, args)
                return {
                    "success": observed.success, "connector_id": "isolated-qa",
                    "result": observed.data or {},
                }

            connector = ChatConnectorExecutionService(settings)
            connector._state = store
            registry = get_tool_registry()
            connector._registry = registry
            if not durable:
                connector._claim_write_before_invoke = AsyncMock(return_value=None)
                connector._replay_existing_write_result = AsyncMock(return_value=None)
                connector._finalize_connector_outcome = MagicMock()
            connector._persist_recent_connector_invocation = AsyncMock()
            if not durable:
                connector._persist_canonical_write_outcome = AsyncMock()
            connector._record_outcomes = AsyncMock()
            connector._session_updates_after_execution = MagicMock(return_value={})
            connector._summarize_result = MagicMock(return_value="Created joined QA contact")
            connector._external_url = MagicMock(return_value=None)
            policy = MagicMock()
            policy.can_approve.return_value = True
            policy_service = MagicMock()
            policy_service.resolve.return_value = policy
            proof = MagicMock()
            proof.ok = True
            proof.compiled_parameters = dict(plan.args)
            proof.user_message.return_value = ""

            def read_record(ctx, action, params):
                assert action == "hubspot.contacts.get"
                assert ctx.org_id == ORG_A and ctx.environment_name == "synthetic"
                record_id = params.get("contact_id") or params.get("id")
                request = urllib.request.Request(receiver.origin + "/records/" + str(record_id),
                    headers={"X-QA-Capability": "eco001-joined-chat-cap"})
                with urllib.request.urlopen(request, timeout=7) as response:
                    payload = json.load(response)
                return NormalizedResult(success=True, action=action, data=payload)

            app.dependency_overrides.clear()
            app.dependency_overrides[get_org_context] = lambda: ORG_A
            app.dependency_overrides[get_environment_context] = lambda: "synthetic"
            app.dependency_overrides[get_settings] = lambda: settings
            try:
                with ExitStack() as patch_stack:
                    for context in (
                    patch.object(assistant, "get_supabase_client", return_value=db),
                    patch.object(conversation_state_service, "get_conversation_state_service", return_value=store),
                    patch.object(chat_connector_execution_service, "get_chat_connector_execution_service", return_value=connector),
                    patch("app.workflows.policy.get_user_role", return_value="admin"),
                    patch("app.services.org_membership.list_member_org_ids", return_value=[ORG_A]),
                    patch("app.services.hitl_policy_service.get_hitl_policy_service", return_value=policy_service),
                    patch.object(assistant, "_persist_conversation_turn", return_value=(True, "qa-message")),
                    patch("app.services.response_composer.compose_user_reply",
                          new_callable=AsyncMock, return_value="Created joined QA contact"),
                    patch.object(registry, "execute_invoke_action", side_effect=registry_invoke),
                    patch("app.services.object_resolution.revalidate_bound_targets", return_value=None),
                    patch("app.services.write_preflight.compile_write_for_context", return_value=proof),
                    patch("app.services.write_preflight.enforce_invoke_write_preflight",
                          side_effect=lambda _ctx, _action, params: params),
                    patch.object(tool_service, "_resolve_tool_executor", return_value=provider),
                    patch.object(tool_service, "assert_agent_tool_permission"),
                    patch.object(tool_service, "_write_tool_audit"),
                    patch("app.services.conversation_write_guard.assert_org_write_allowed"),
                    patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"),
                    patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"),
                    patch("app.services.capability_availability.is_capability_action", return_value=False),
                    patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None),
                    patch("app.services.write_invoke_idempotency.claim_write_invoke", side_effect=claim),
                    patch("app.services.write_invoke_idempotency.finalize_write_invoke", side_effect=finalize),
                    ):
                        patch_stack.enter_context(context)
                    if durable:
                        for context in (
                            patch("app.services.write_success_verification._dispatch_background",
                                  side_effect=lambda work, _name: verification_work.append(work)),
                            patch("app.services.sealed_read_execution.invoke_compiled_read", side_effect=read_record),
                            patch("app.workflows.audit._get_org_pii_mode", return_value="standard"),
                            patch("app.workflows.audit._schedule_siem_dispatch"),
                            patch("app.services.notification_preference_service.channel_enabled", return_value=False),
                        ):
                            patch_stack.enter_context(context)
                    http = TestClient(app)
                    def confirm():
                        return http.post(f"/api/assistant/conversation/{CONVERSATION}/execute",
                            json={"confirm": True}, headers={"Authorization": f"Bearer {token}"})
                    responses = [confirm()]
                    if journey in {"revoked_before_dispatch", "foreign_actor"}:
                        responses.append(confirm())
                        assert all(response.status_code == 200 for response in responses)
                        assert all(response.json()["success"] is False for response in responses)
                        assert receiver.writes == 0
                        assert keys == []
                        for table in ("workflow_runs", "runs", "write_invoke_idempotency", "domain_event_outbox",
                                      "audit_logs", "audit_events", "notifications", "intelligence_outcome_events"):
                            assert pg.value(f"SELECT count(*) FROM public.{table}") == "0"
                        return
                    if durable:
                        assert responses[0].status_code == 200, responses[0].text
                        assert receiver.writes == 1
                        assert pg.value("SELECT count(*) FROM public.workflow_runs") == "1"
                        assert pg.value("SELECT status FROM public.workflow_runs") == "verifying"
                        assert pg.value("SELECT status FROM public.runs") == "running"
                        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"
                        assert len(verification_work) == 1
                        run_id = pg.value("SELECT id FROM public.workflow_runs")
                        if journey == "cancel_before_verify":
                            from app.services.execution_outcome import finalize_execution_outcome
                            finalize_execution_outcome(db, org_id=ORG_A, run_id=run_id,
                                status="cancelled", source="api", actor_id=ACTOR)
                        # Execute the real scheduled verifier body, retaining the
                        # real entity GET adapter and canonical finalizer.
                        verification_work.pop()()
                        expected = "cancelled" if journey == "cancel_before_verify" else "completed"
                        assert pg.value("SELECT status FROM public.workflow_runs") == expected
                        assert pg.value("SELECT status FROM public.runs") == expected
                        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"
                        assert pg.value("SELECT parameters->>'outcome_finalized' FROM public.workflow_runs") == "true"
                        for table in ("audit_logs", "audit_events", "notifications", "intelligence_outcome_events"):
                            assert pg.value(f"SELECT count(*) FROM public.{table}") == "1"
                        assert pg.value("SELECT count(*) FROM public.workflow_steps") == "1"
                        assert pg.value("SELECT count(*) FROM public.run_steps") == "1"
                        assert pg.value("SELECT jsonb_array_length(state->'execution_observations') FROM public.qa_chat_state") == "1"
                        if journey == "durable":
                            assert pg.value("SELECT parameters->'verification'->>'verified' FROM public.workflow_runs") == "true"
                            assert pg.value("SELECT state->'pending_task'->>'lifecycle' FROM public.qa_chat_state") == "COMPLETED"
                        assert pg.value("SELECT environment FROM public.workflow_runs") == "synthetic"
                        # Consume the event actually emitted by the HTTP-origin
                        # run's terminal transaction, not a separately seeded event.
                        from app.services import domain_events as events
                        from tests.db.test_domain_event_outbox_pg import _PsqlRpcClient
                        pg.psql("CREATE TABLE public.qa_chat_consumer_effect (event_id bigint PRIMARY KEY)")
                        saved_handlers = {key: list(value) for key, value in events._handlers.items()}
                        events.reset_domain_event_handlers_for_tests()
                        def consume(_client, event):
                            pg.psql(f"INSERT INTO public.qa_chat_consumer_effect VALUES ({int(event['id'])})")
                        events.register_domain_event_handler(events.EVENT_EXECUTION_OUTCOME_FINALIZED,
                                                             "joined-chat-sql-consumer", consume)
                        try:
                            relay = events.DomainEventRelay(_PsqlRpcClient(pg), worker_id="joined-chat-relay")
                            assert relay.run_once().delivered == 1
                            assert relay.run_once().claimed == 0
                        finally:
                            events.reset_domain_event_handlers_for_tests()
                            events._handlers.update(saved_handlers)
                        assert pg.value("SELECT count(*) FROM public.qa_chat_consumer_effect") == "1"
                        assert pg.value("SELECT status FROM public.domain_event_outbox") == "delivered"
                    responses.append(confirm())
                    if durable:
                        assert pg.value("SELECT count(*) FROM public.workflow_runs") == "1"
                        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"
                        assert pg.value("SELECT status FROM public.workflow_runs") == expected
                assert all(r.status_code == 200 for r in responses), [
                    (r.status_code, r.text) for r in responses
                ]
                assert all(r.json()["success"] for r in responses)
                assert all(r.json()["history_persisted"] for r in responses)
                assert len(db.lookups) == 2
                assert keys and len(keys) == (1 if durable else 2)
                if not durable:
                    assert keys[0] == keys[1]
                assert receiver.pid != __import__("os").getpid()
                assert receiver.writes == 1, "Duplicate Chat confirmation reached provider"
                assert pg.value(
                    "SELECT status FROM public.write_invoke_idempotency "
                    f"WHERE org_id='{ORG_A}' AND idempotency_key='{keys[0]}'"
                ) == "completed", "Provider effect has no matching durable completed ledger"
                assert pg.value(
                    "SELECT count(*) FROM public.write_invoke_idempotency "
                    f"WHERE org_id='{ORG_A}' AND idempotency_key='{keys[0]}'"
                ) == "1"
                policy.can_approve.assert_called()
            finally:
                app.dependency_overrides.clear()
    finally:
        receiver.close()
