"""ECO-001 joined HTTP Chat -> governed invoke -> independent receiver -> SQL ledger.

The mounted FastAPI route, signed JWT verification, real Chat execution adapter,
ToolContext, tool_service.invoke_tool and Postgres claim/finalize are exercised.
The provider is an isolated *test* process, not a third-party live account.
Only Supabase transport, HITL lookup, external provider credentials and ancillary
notification/state stores are adapted. This is not production deployment proof.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
import time
import urllib.request
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
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
ACTOR = "joined-chat-approver"


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


def test_signed_approved_chat_http_matches_independent_receiver_and_durable_ledger(tmp_path):
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
        with pg_cluster(BOOTSTRAP_SQL, migration, grants) as pg:
            keys = []

            def claim(_client, *, org_id, idempotency_key, **_kw):
                assert org_id == ORG_A
                keys.append(idempotency_key)
                row = _claim(pg, org_id, idempotency_key)
                return WriteClaimResult(
                    outcome=row["outcome"], claim_token=row.get("claim_token"),
                    status=row.get("status"), reason=row.get("reason"),
                    replay=NormalizedResult(success=True, action=ACTION, data={"id": "joined-qa"})
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
                    success=True, action=ACTION, data={"id": "joined-qa"},
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
            connector._claim_write_before_invoke = AsyncMock(return_value=None)
            connector._replay_existing_write_result = AsyncMock(return_value=None)
            connector._finalize_connector_outcome = MagicMock()
            connector._persist_recent_connector_invocation = AsyncMock()
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
                    http = TestClient(app)
                    responses = [
                        http.post(
                            f"/api/assistant/conversation/{CONVERSATION}/execute",
                            json={"confirm": True},
                            headers={"Authorization": f"Bearer {token}"},
                        ) for _ in range(2)
                    ]
                assert all(r.status_code == 200 for r in responses), [
                    (r.status_code, r.text) for r in responses
                ]
                assert all(r.json()["success"] for r in responses)
                assert all(r.json()["history_persisted"] for r in responses)
                assert len(db.lookups) == 2
                assert keys and len(keys) == 2 and keys[0] == keys[1]
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
