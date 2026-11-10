"""PR611 real connector_chat route -> registry -> invoke_tool -> DB ledger acceptance.

Only the external provider adapter is replaced with a local HTTP receiver.
All claims/finalization use real acceptance Supabase RPCs. No HubSpot or
customer connector is contacted. Explicitly scoped to the dedicated QA org.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.approval_action_binding import digest_plan_args
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.tool_types import NormalizedResult
from app.services.write_invoke_idempotency import build_write_idempotency_key
from app.services.tool_types import ToolContext

EXPECTED_URL = "https://aadnwmjzrmbvadszroqt.supabase.co"
QA_NAME = "Gravitre MCP Acceptance QA"
ACTION = "hubspot.contacts.create"
TOOL = "hubspot_contacts_create"
ARGS = {"email": "pr611-ledger-fixture@example.com", "firstname": "QA", "lastname": "Ledger"}
REVIEWER = "pr611-ledger-reviewer"


def client():
    from supabase import create_client
    return create_client(os.environ["MCP_ACCEPTANCE_URL"], os.environ["MCP_ACCEPTANCE_SERVICE_KEY"])


def check_env():
    if os.environ.get("MCP_CRASH_ACCEPTANCE") != "1":
        raise SystemExit("Acceptance must be explicitly enabled")
    if os.environ.get("MCP_ACCEPTANCE_URL", "").rstrip("/") != EXPECTED_URL:
        raise SystemExit("Refusing non-acceptance Supabase project")
    if not os.environ.get("MCP_ACCEPTANCE_SERVICE_KEY") or not os.environ.get("MCP_ACCEPTANCE_ORG_ID"):
        raise SystemExit("Missing QA credentials or organization")


def run():
    check_env()
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
    from app.config import Settings, get_settings
    from app.routers import workflows as wf
    from app.services import chat_connector_execution_service as chat_module
    from app.services import tool_service
    from app.workflows import policy

    db = client()
    org_id = os.environ["MCP_ACCEPTANCE_ORG_ID"]
    org = db.table("organizations").select("name").eq("id", org_id).single().execute().data
    if (org or {}).get("name") != QA_NAME:
        raise SystemExit("Refusing non-isolated QA organization")
    approval_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    requester_id = str(uuid.uuid4())
    plan = ConnectorActionPlan(
        tool_name=TOOL, invoke_action=ACTION, integration="hubspot",
        kind="write", label="Isolated QA ledger contact",
        args=dict(ARGS), requires_approval=True,
    )
    writes = []
    race_approval_id = None
    race_entered_provider = threading.Event()
    race_resume_provider = threading.Event()
    race_ledger_key = None

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            writes.append(body)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings = Settings(
        app_env="dev", supabase_url=EXPECTED_URL, supabase_anon_key="a",
        supabase_service_role_key="s", supabase_jwt_secret="j",
        write_authority_mode="enforce", write_invoke_idempotency_enabled=False,
    )
    service = chat_module.ChatConnectorExecutionService(settings)
    service.plan_action = lambda *_a, **_kw: plan
    # Conversation-store and downstream notification are not the acceptance
    # subject. The route approval CAS and shared ledger remain unmocked.
    from app.services.conversation_state_service import ConversationStateService
    real_state = ConversationStateService(settings)
    # Preserve the real conversation-state persistence code and acceptance
    # database for this test, including calls that omit the client argument.
    service._state = MagicMock()
    async def qa_get_state(c, o, **_kw):
        return await real_state.get_task_state(c, o, client=db)
    async def qa_update_state(c, o, update, **kw):
        return await real_state.update_task_state(
            c, o, update, client=db,
            effect_record=bool(kw.get("effect_record", False)),
        )
    async def qa_update_state_from(c, o, builder, **kw):
        return await real_state.update_task_state_from(
            c, o, builder, client=db,
            effect_record=bool(kw.get("effect_record", False)),
        )
    service._state.get_task_state = qa_get_state
    service._state.update_task_state = qa_update_state
    service._state.update_task_state_from = qa_update_state_from
    service._claim_write_before_invoke = AsyncMock(return_value=None)
    service._replay_existing_write_result = AsyncMock(return_value=None)
    service._finalize_connector_outcome = MagicMock(return_value=None)
    service._persist_recent_connector_invocation = AsyncMock()
    service._persist_canonical_write_outcome = AsyncMock()
    service._external_url = MagicMock(return_value=None)
    service._summarize_result = MagicMock(return_value="Synthetic provider write recorded")
    def provider(ctx, params):
        if race_approval_id and ctx.turn_id == race_approval_id:
            race_entered_provider.set()
            if not race_resume_provider.wait(25):
                raise TimeoutError("In-flight race fixture was not released")
        req = Request(
            f"http://127.0.0.1:{server.server_port}/write",
            data=json.dumps({"email": params.get("email"), "turn_id": ctx.turn_id}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urlopen(req, timeout=10) as response:
            assert response.status == 200
        return NormalizedResult(success=True, action=ACTION, data={"id": "qa-local-1"})

    from app.services.write_invoke_idempotency import build_write_idempotency_key
    expected_ctx = ToolContext(
        settings=settings, client=db, org_id=org_id, actor_id=REVIEWER,
        conversation_id=conversation_id, turn_id=approval_id,
        write_idempotency_required=True,
    )
    expected_key, expected_logical = build_write_idempotency_key(expected_ctx, ACTION, ARGS)
    context = {
        "conversation_id": conversation_id,
        "parameters": {"args": ARGS},
        "binding": {
            "tool_name": TOOL, "invoke_action": ACTION,
            "integration": "hubspot", "args_digest": digest_plan_args(ARGS),
        },
        "qa": "PR611-canonical-ledger-acceptance",
    }
    negative_approval_ids = []
    try:
        # The acceptance schema enforces conversations.user_id -> users.id.
        # Seed a disposable user only inside the already-verified QA org;
        # do not weaken the FK or reuse a production account.
        db.table("users").insert({
            "id": requester_id, "org_id": org_id,
            "email": f"pr611-{requester_id}@example.invalid",
            "full_name": "PR611 synthetic Chat requester",
            "role": "member",
        }).execute()
        db.table("conversations").insert({
            "id": conversation_id, "org_id": org_id, "user_id": requester_id,
            "title": "PR611 isolated Chat approval acceptance",
        }).execute()
        # Run the real Chat connector intent-to-approval turn. Only upstream
        # cognitive/model/vendor discovery and notifications are fixtures:
        # process_turn and its queue writer persist the actual approval row.
        with (
            patch.object(chat_module, "emit_notification"),
            patch.object(service, "_org_approver_user_ids", return_value=[]),
            patch.object(service, "_live_connected_integrations", return_value=["hubspot"]),
            patch.object(service, "_try_inline_preview_turn", new_callable=AsyncMock, return_value=None),
            patch.object(service, "_evaluate_risk", new_callable=AsyncMock, return_value={
                "requires_approval": True, "approval_reason": "QA authorized human review",
            }),
            patch.object(service, "_resolve_hitl_decision", return_value=SimpleNamespace(
                requires_approval=True, reason="QA human review",
                action_kind="write", matched_policy_id=None,
            )),
            patch.object(service, "_user_can_approve_writes", return_value=False),
            patch.object(service, "_verify_plan_executable", return_value=None),
            patch("app.services.canonical_cognitive_resolution.resolution_already_applied", return_value=True),
            patch("app.services.analytics_traffic_overview_service.try_analytics_traffic_overview_turn",
                  new_callable=AsyncMock, return_value=None),
            patch("app.services.connector_action_workflows.resolve_assignee_disambiguation",
                  new_callable=AsyncMock, return_value=None),
            patch("app.services.activity_feed_service.record_activity_event"),
        ):
            turn = asyncio.run(service.process_turn(
                org_id=org_id, user_id=requester_id,
                conversation_id=conversation_id, message="Create this isolated HubSpot QA contact",
                classification={"intent": "crm_write", "risk_level": "high"},
                task_state={}, connected_integrations=["hubspot"],
                client=db, structured_plan=plan,
            ))
        assert turn is not None and turn.get("dialogue_mode") == "awaiting_approval", turn
        assert turn["pending_task"]["status"] == "awaiting_admin_approval"
        queued_id = turn.get("approval_id")
        assert queued_id == turn["pending_task"]["params"].get("approval_id")
        assert queued_id, "Real Chat queue writer failed to persist approval"
        approval_id = str(queued_id)
        expected_ctx = ToolContext(
            settings=settings, client=db, org_id=org_id, actor_id=REVIEWER,
            conversation_id=conversation_id, turn_id=approval_id,
            write_idempotency_required=True,
        )
        expected_key, expected_logical = build_write_idempotency_key(
            expected_ctx, ACTION, ARGS
        )
        queued_row = db.table("approvals").select(
            "id,type,status,requested_by,context"
        ).eq("org_id", org_id).eq("id", approval_id).single().execute().data
        assert queued_row["type"] == "connector_chat"
        assert queued_row["status"] == "pending"
        assert queued_row["requested_by"] == requester_id
        assert queued_row["context"]["binding"] == context["binding"]
        assert queued_row["context"]["parameters"]["args"] == ARGS
        context = queued_row["context"]
        pending_persisted = db.table("conversations").select(
            "task_state"
        ).eq("org_id", org_id).eq(
            "id", conversation_id
        ).single().execute().data["task_state"]
        assert pending_persisted["pending_task"]["status"] == "awaiting_admin_approval"
        assert pending_persisted["pending_task"]["params"]["approval_id"] == approval_id
        app.dependency_overrides[get_current_user] = lambda: {"user_id": REVIEWER}
        app.dependency_overrides[get_org_context] = lambda: org_id
        app.dependency_overrides[get_environment_context] = lambda: "production"
        app.dependency_overrides[get_settings] = lambda: settings
        proof = SimpleNamespace(ok=True, compiled_parameters=dict(ARGS))
        with (
            patch.object(wf, "get_supabase_client", return_value=db),
            patch.object(wf, "get_plan_for_org", return_value={"features": {"approvals": True}}),
            patch.object(wf, "require_feature"),
            patch.object(wf, "has_capability", return_value=True),
            patch.object(wf, "write_audit_event"),
            patch.object(policy, "get_user_role", return_value="admin"),
            patch.object(chat_module, "get_chat_connector_execution_service", return_value=service),
            patch("app.services.object_resolution.revalidate_bound_targets", return_value=None),
            patch("app.services.write_preflight.compile_write_for_context", return_value=proof),
            patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda ctx, action, params: params),
            patch("app.services.conversation_write_guard.assert_org_write_allowed"),
            patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"),
            patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"),
            patch.object(tool_service, "assert_agent_tool_permission"),
            patch.object(tool_service, "_resolve_tool_executor", return_value=provider),
            patch.object(tool_service, "_write_tool_audit"),
            patch("app.workers.workflow_queue.assert_current_workflow_claim_live"),
        ):
            response = TestClient(app).post(f"/api/approvals/{approval_id}/approve", json={})
            assert response.status_code == 200, f"Approval failed {response.status_code}: {response.text[-1200:]}"
            assert response.json().get("success") is True, f"Provider success was not propagated: {response.text[-1200:]}"
            retry = TestClient(app).post(f"/api/approvals/{approval_id}/approve", json={})
            assert retry.status_code == 409, f"Replay not blocked: {retry.status_code}"

            # The same REAL HTTP decision route and REAL acceptance database
            # must refuse a denied actor before claim or provider dispatch.
            denied_id = str(uuid.uuid4())
            negative_approval_ids.append(denied_id)
            db.table("approvals").insert({
                "id": denied_id, "org_id": org_id, "type": "connector_chat",
                "title": "PR611 denied-authority no-write control",
                "status": "pending", "context": dict(context),
            }).execute()
            with patch.object(wf, "has_capability", return_value=False):
                denied = TestClient(app).post(f"/api/approvals/{denied_id}/approve", json={})
            assert denied.status_code == 403, f"Authorization bypass: {denied.status_code}"
            denied_row = db.table("approvals").select("status,reviewed_at").eq(
                "org_id", org_id
            ).eq("id", denied_id).single().execute().data
            assert denied_row["status"] == "pending" and denied_row["reviewed_at"] is None
            # Rejection/cancellation of an undelivered approval must be a
            # persisted no-write decision, never an implicit approval.
            rejected_id = str(uuid.uuid4())
            negative_approval_ids.append(rejected_id)
            reject_context = dict(context)
            reject_context["conversation_id"] = ""  # no actual conversation to clear
            db.table("approvals").insert({
                "id": rejected_id, "org_id": org_id, "type": "connector_chat",
                "title": "PR611 rejected approval no-write control",
                "status": "pending", "context": reject_context,
            }).execute()
            rejected = TestClient(app).post(f"/api/approvals/{rejected_id}/reject", json={})
            assert rejected.status_code == 200, f"Rejection failed: {rejected.text[-800:]}"
            assert rejected.json()["status"] == "rejected"
            rejected_retry = TestClient(app).post(
                f"/api/approvals/{rejected_id}/approve", json={}
            )
            assert rejected_retry.status_code == 409
            rejected_row = db.table("approvals").select("status").eq(
                "org_id", org_id
            ).eq("id", rejected_id).single().execute().data
            assert rejected_row["status"] == "rejected"

            # In-flight revocation race: after durable approval claim and
            # canonical ledger claim, provider dispatch is deliberately paused.
            # A concurrent reject MUST lose the CAS; it cannot pretend that an
            # already-started provider call has been revoked or cancelled.
            race_approval_id = str(uuid.uuid4())
            # This action IS authorized and must acquire a ledger claim;
            # do not include it in the deny/reject zero-claim assertion.
            db.table("approvals").insert({
                "id": race_approval_id, "org_id": org_id,
                "type": "connector_chat", "status": "pending",
                "title": "PR611 in-flight revocation race",
                "context": dict(context),
            }).execute()
            race_ctx = ToolContext(
                settings=settings, client=db, org_id=org_id, actor_id=REVIEWER,
                conversation_id=conversation_id, turn_id=race_approval_id,
                write_idempotency_required=True,
            )
            race_ledger_key, race_logical_id = build_write_idempotency_key(
                race_ctx, ACTION, ARGS
            )
            race_outcome = {}
            def execute_racing_approval():
                try:
                    race_outcome["response"] = TestClient(app).post(
                        f"/api/approvals/{race_approval_id}/approve", json={}
                    )
                except BaseException as exc:
                    race_outcome["error"] = repr(exc)
            racing_thread = threading.Thread(target=execute_racing_approval, daemon=True)
            racing_thread.start()
            try:
                assert race_entered_provider.wait(25), "Provider dispatch never reached"
                claimed_approval = db.table("approvals").select(
                    "status,context"
                ).eq("org_id", org_id).eq(
                    "id", race_approval_id
                ).single().execute().data
                assert claimed_approval["status"] == "approved"
                assert claimed_approval["context"]["dispatch"]["state"] == "claimed"
                claimed_ledger = db.table("write_invoke_idempotency").select(
                    "status,logical_action_id"
                ).eq("org_id", org_id).eq(
                    "idempotency_key", race_ledger_key
                ).single().execute().data
                assert claimed_ledger["status"] == "in_progress"
                assert claimed_ledger["logical_action_id"] == race_logical_id
                revoke = TestClient(app).post(
                    f"/api/approvals/{race_approval_id}/reject", json={}
                )
                assert revoke.status_code == 409, (
                    f"Claimed approval overwritten by revocation: {revoke.text}"
                )
            finally:
                race_resume_provider.set()
                racing_thread.join(timeout=25)
            assert not racing_thread.is_alive(), "Racing approval did not finish"
            assert "error" not in race_outcome, race_outcome
            assert race_outcome["response"].status_code == 200, race_outcome["response"].text
            race_replay = TestClient(app).post(
                f"/api/approvals/{race_approval_id}/approve", json={}
            )
            assert race_replay.status_code == 409

        assert writes == [
            {"email": ARGS["email"], "turn_id": approval_id},
            {"email": ARGS["email"], "turn_id": race_approval_id},
        ], f"Provider writes: {writes}"
        ledger = (
            db.table("write_invoke_idempotency")
            .select("idempotency_key,invoke_action,logical_action_id,status,result,claim_token")
            .eq("org_id", org_id).eq("idempotency_key", expected_key)
            .limit(2).execute().data or []
        )
        assert len(ledger) == 1, f"Missing or duplicate canonical ledger row: {ledger}"
        assert ledger[0]["status"] == "completed", ledger
        assert ledger[0]["invoke_action"] == ACTION and ledger[0]["logical_action_id"] == expected_logical
        assert (ledger[0].get("result") or {}).get("success") is True, ledger
        race_terminal = db.table("write_invoke_idempotency").select(
            "status,result,logical_action_id"
        ).eq("org_id", org_id).eq(
            "idempotency_key", race_ledger_key
        ).single().execute().data
        assert race_terminal["status"] == "completed", race_terminal
        assert race_terminal["logical_action_id"] == race_logical_id
        assert (race_terminal["result"] or {}).get("success") is True
        # Independent database checks: denied and rejected approvals never
        # acquire canonical ledger claims or produce a second provider write.
        no_write_ledger = db.table("write_invoke_idempotency").select(
            "idempotency_key"
        ).eq("org_id", org_id).in_(
            "logical_action_id", [
                build_write_idempotency_key(
                    ToolContext(
                        settings=settings, client=db, org_id=org_id, actor_id=REVIEWER,
                        conversation_id=conversation_id, turn_id=blocked_id,
                        write_idempotency_required=True,
                    ), ACTION, ARGS
                )[1] for blocked_id in negative_approval_ids
            ],
        ).execute().data or []
        assert not no_write_ledger, f"Unauthorized ledger claims: {no_write_ledger}"
        approval = (
            db.table("approvals").select("status,context")
            .eq("id", approval_id).eq("org_id", org_id).single().execute().data
        )
        assert approval["status"] == "approved"
        assert approval["context"]["dispatch"]["state"] in {"reported_success_unverified", "verified"}, approval
        after_approval_state = db.table("conversations").select(
            "task_state"
        ).eq("org_id", org_id).eq(
            "id", conversation_id
        ).single().execute().data["task_state"]
        assert after_approval_state.get("pending_task") is None, after_approval_state
        print(json.dumps({
            "result": "PASS", "canonical_ledger": "completed",
            "provider_writes": len(writes), "approval_replay_http": 409,
            "inflight_revocation_http": 409,
            "inflight_ledger_terminal": "completed",
            "ledger_rows": len(ledger), "approval_id": approval_id,
            "provider_is_synthetic": True,
            "conversation_pending_persisted": True,
            "conversation_pending_cleared_after_approval": True,
            "denied_approval_http": 403, "rejected_approval_http": 200,
            "rejected_replay_http": 409, "unauthorized_ledger_rows": 0,
        }))
    finally:
        app.dependency_overrides.clear()
        try:
            db.table("write_invoke_idempotency").delete().eq("org_id", org_id).eq("idempotency_key", expected_key).execute()
            if race_ledger_key:
                db.table("write_invoke_idempotency").delete().eq(
                    "org_id", org_id
                ).eq("idempotency_key", race_ledger_key).execute()
            db.table("approvals").delete().eq("org_id", org_id).eq("id", approval_id).execute()
            for negative_id in negative_approval_ids:
                db.table("approvals").delete().eq("org_id", org_id).eq("id", negative_id).execute()
            if race_approval_id:
                db.table("approvals").delete().eq("org_id", org_id).eq(
                    "id", race_approval_id
                ).execute()
            db.table("conversations").delete().eq(
                "org_id", org_id
            ).eq("id", conversation_id).execute()
            db.table("users").delete().eq(
                "org_id", org_id
            ).eq("id", requester_id).execute()
            remaining = db.table("write_invoke_idempotency").select("id").eq("org_id", org_id).eq("idempotency_key", expected_key).execute().data or []
            remaining_approval = db.table("approvals").select("id").eq("org_id", org_id).eq("id", approval_id).execute().data or []
            race_remaining = db.table("write_invoke_idempotency").select("id").eq(
                "org_id", org_id
            ).eq("idempotency_key", race_ledger_key).execute().data if race_ledger_key else []
            race_approval_remaining = db.table("approvals").select("id").eq(
                "org_id", org_id
            ).eq("id", race_approval_id).execute().data if race_approval_id else []
            negative_remaining = db.table("approvals").select("id").eq(
                "org_id", org_id
            ).in_("id", negative_approval_ids).execute().data if negative_approval_ids else []
            remaining_conversation = db.table("conversations").select("id").eq(
                "org_id", org_id
            ).eq("id", conversation_id).execute().data or []
            remaining_requester = db.table("users").select("id").eq(
                "org_id", org_id
            ).eq("id", requester_id).execute().data or []
            if (remaining or remaining_approval or negative_remaining or
                    race_remaining or race_approval_remaining or remaining_conversation or
                    remaining_requester):
                raise RuntimeError("Isolated test rows not cleaned up")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    run()
