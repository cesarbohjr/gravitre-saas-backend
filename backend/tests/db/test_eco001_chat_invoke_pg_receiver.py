"""Production Chat invoke_tool with real PostgreSQL and independent provider receiver.

Only external Supabase RPC transport, provider credentials and unrelated guards
are substituted. This does not certify mounted HTTP or Agent ingress.
"""
from contextlib import ExitStack

import pytest
import json
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import tool_service
from app.services.tool_types import ToolContext, NormalizedResult
from app.services.write_authority import write_authority
from app.services.write_invoke_idempotency import WriteClaimResult, WriteFinalizeResult
from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_write_invoke_idempotency_pg import BOOTSTRAP_SQL, ORG_A, _claim, _finalize
from tests.db.test_autonomous_independent_write_pg import IndependentFixture

pytestmark = requires_pg


def test_authorized_chat_invoke_real_ledger_and_receiver(tmp_path):
    action = "hubspot.contacts.update"
    receiver = IndependentFixture(tmp_path / "provider.sqlite3", b"<h1>QA</h1>", capability="chat-cap")
    migration = (MIGRATIONS / "20261016032018_write_invoke_idempotency.sql").read_text()
    grants = (MIGRATIONS / "20261016032029_write_invoke_idempotency_grants.sql").read_text()
    context_migration = (MIGRATIONS / "20261118030000_write_recovery_context.sql").read_text()
    auth_role = """CREATE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE
        AS 'SELECT nullif(current_setting(''request.jwt.claim.role'', true), '''')';"""
    try:
        with pg_cluster(BOOTSTRAP_SQL + auth_role, migration, grants, context_migration) as pg:
            keys = []
            def claim(_client, *, org_id, idempotency_key, **_kw):
                assert org_id == ORG_A
                keys.append(idempotency_key)
                row = _claim(pg, org_id, idempotency_key)
                return WriteClaimResult(
                    outcome=row["outcome"], claim_token=row.get("claim_token"),
                    status=row.get("status"), reason=row.get("reason"),
                    replay=NormalizedResult(success=True, action=action, data={"id": "qa"})
                    if row["outcome"] == "replay" else None,
                )
            def finalize(_client, *, org_id, idempotency_key, claim_token, status, **_kw):
                assert status == "completed"
                row = _finalize(pg, org_id, idempotency_key, claim_token, status)
                return WriteFinalizeResult(outcome=row["outcome"])
            def bind(_client, *, org_id, idempotency_key, claim_token,
                     invoke_action, connector_id, original_args):
                # Fenced context is persisted through the actual PostgreSQL
                # RPC, rather than bypassed in this joined-ingress test.
                assert org_id == ORG_A
                assert connector_id == "qa-hubspot"
                safe = lambda value: "'" + str(value).replace("'", "''") + "'"
                payload = json.dumps(original_args)
                sql = (
                    "SET ROLE service_role; SET request.jwt.claim.role = 'service_role'; "
                    "SELECT public.bind_write_recovery_context("
                    f"'{ORG_A}'::uuid,{safe(idempotency_key)},"
                    f"{safe(claim_token)}::uuid,{safe(invoke_action)},"
                    f"{safe(connector_id)},{safe(payload)}::jsonb)::text;"
                )
                row = json.loads(pg.psql(sql).stdout.strip())
                return row.get("outcome") == "bound"
            def provider(_ctx, _params):
                request = urllib.request.Request(
                    receiver.origin + "/write",
                    data=json.dumps({"cap": "chat-cap"}).encode(),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=7) as response:
                    assert response.status == 204
                return NormalizedResult(success=True, action=action, data={"id": "qa"})
            ctx = ToolContext(
                settings=SimpleNamespace(
                    write_authority_mode="enforce", write_invoke_idempotency_enabled=True,
                    private_connector_runtime_enabled=False,
                ),
                client=MagicMock(), org_id=ORG_A, actor_id="actor",
                conversation_id="conversation", turn_id="approved-turn",
                write_idempotency_required=True,
                connector_id="qa-hubspot",
            )
            with ExitStack() as stack:
                for target in (
                    "app.services.conversation_write_guard.assert_org_write_allowed",
                    "app.services.hipaa_service.enforce_hipaa_for_tool_invoke",
                    "app.services.agent_guardrail_limits.enforce_agent_guardrail_limits",
                ):
                    stack.enter_context(patch(target))
                stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
                stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
                stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c,a,p:p))
                stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
                stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
                stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
                stack.enter_context(patch("app.services.write_invoke_idempotency.claim_write_invoke", side_effect=claim))
                stack.enter_context(patch("app.services.write_invoke_idempotency.finalize_write_invoke", side_effect=finalize))
                stack.enter_context(patch("app.services.write_invoke_idempotency.bind_write_recovery_context", side_effect=bind))
                with write_authority("human", "approval:approved-turn"):
                    first = tool_service.invoke_tool(ctx, action, {"id": "qa"})
                    second = tool_service.invoke_tool(ctx, action, {"id": "qa"})
            assert first.success and second.success
            assert keys[0] == keys[1]
            assert receiver.writes == 1
            ledger = pg.value(
                "SELECT status FROM public.write_invoke_idempotency "
                f"WHERE org_id = '{ORG_A}' AND idempotency_key = '{keys[0]}';"
            )
            assert ledger == "completed"
            assert pg.value(
                "SELECT connector_id FROM public.write_invoke_idempotency "
                f"WHERE org_id = '{ORG_A}' AND idempotency_key = '{keys[0]}';"
            ) == "qa-hubspot"
    finally:
        receiver.close()
