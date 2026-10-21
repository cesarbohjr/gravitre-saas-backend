"""Decide resolved MCP writes through existing approvals and execution contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.core.io_pool import run_io
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.mcp_client_service import (
    get_mcp_client_service, mcp_approval_target_digest, mcp_input_sha256, mcp_openai_tool_name,
)


def _claim_decision(client: Any, org_id: str, approval_id: str, reviewer_id: str, decision: str) -> None:
    claimed = (client.table("approvals")
               .update({"status": decision, "reviewed_by": reviewer_id,
                        "reviewed_at": datetime.now(timezone.utc).isoformat()})
               .eq("id", approval_id).eq("org_id", org_id).eq("status", "pending")
               .is_("reviewed_at", "null").execute().data or [])
    if not claimed:
        raise HTTPException(409, "Approval already being decided")


async def decide_mcp_approval(
    client: Any, settings: Any, *, org_id: str, approval_id: str,
    reviewer_id: str, approve: bool,
) -> dict[str, Any]:
    """Admin consent refers to persisted arguments, never a caller-supplied payload.

    Already-approved but unconsumed proposals can resume after a crash or rate
    limit. execute_tool's atomic consume admits at most one provider dispatch.
    Consent, dispatch and independently verified success remain distinct.
    """
    from app.auth.org_role_permissions import capability_denied_detail, has_capability
    from app.workflows.audit import write_audit_event
    from app.workflows.policy import PolicyResolutionError, get_user_role, widen_to_member_role

    try:
        role = await run_io(widen_to_member_role, get_user_role, client, org_id, reviewer_id)
    except PolicyResolutionError as exc:
        raise HTTPException(403, "Organization administrator required") from exc
    if not await run_io(has_capability, client, org_id, role, "approve_writes"):
        raise HTTPException(403, capability_denied_detail("approve_writes"))
    rows = await run_io(lambda: (client.table("approvals")
        .select("id,type,status,context,reviewed_at,consumed_at")
        .eq("id", approval_id).eq("org_id", org_id).limit(1).execute().data or []))
    if not rows or rows[0].get("type") != "mcp_tool":
        raise HTTPException(404, "Approval not found")
    row = rows[0]
    resume = approve and row.get("status") == "approved" and row.get("reviewed_at") and not row.get("consumed_at")
    if not resume and (row.get("status") != "pending" or row.get("reviewed_at")):
        raise HTTPException(409, "Approval already decided or consumed")
    context = safe_normalize_stored_dict(row, key="context")
    execution_id, tool_id = str(context.get("mcp_execution_id") or ""), str(context.get("mcp_tool_id") or "")
    decision = "approved" if approve else "rejected"
    if not approve:
        # Rejection must also work for obsolete/orphaned proposals. Never dispatch.
        await run_io(_claim_decision, client, org_id, approval_id, reviewer_id, decision)
        if execution_id:
            await run_io(lambda: (client.table("mcp_tool_executions").update({"status": "rejected"})
                .eq("id", execution_id).eq("org_id", org_id).eq("approval_id", approval_id)
                .eq("status", "pending_approval").execute()))
        await run_io(write_audit_event, client, org_id=org_id, actor_id=reviewer_id,
            action="mcp.approval.decided", resource_type="approval", resource_id=approval_id,
            metadata={"decision": decision, "execution_id": execution_id})
        return {"success": True, "approval_id": approval_id, "status": "rejected"}
    if not execution_id or not tool_id:
        raise HTTPException(409, "Proposal is incomplete; request fresh approval")
    executions = await run_io(lambda: (client.table("mcp_tool_executions")
        .select("id,tool_id,approval_id,input,status,agent_id,workflow_run_id")
        .eq("id", execution_id).eq("org_id", org_id).limit(1).execute().data or []))
    if (not executions or executions[0].get("status") not in {"pending_approval", "approved"}
            or str(executions[0].get("tool_id")) != tool_id
            or str(executions[0].get("approval_id")) != approval_id):
        raise HTTPException(409, "Proposal no longer matches this approval")
    execution = executions[0]
    args = safe_normalize_stored_dict(execution, key="input")
    reviewed = safe_normalize_stored_dict(context, key="parameters")
    expected_hash = context.get("input_sha256")
    if not expected_hash or mcp_input_sha256(args) != expected_hash or mcp_input_sha256(reviewed) != expected_hash:
        raise HTTPException(409, "Proposal arguments changed; request fresh approval")
    service = get_mcp_client_service(settings)
    tool = await service._load_tool(tool_id, org_id)
    server = await service._load_server(str(tool["server_id"]), org_id)
    if context.get("target_digest") != mcp_approval_target_digest(tool, server):
        raise HTTPException(409, "MCP target changed; request fresh approval")
    if execution.get("agent_id"):
        from app.services.tool_service import assert_agent_tool_permission
        from app.services.tool_types import ToolContext, ToolPermissionDeniedError

        ctx = ToolContext(settings=settings, client=client, org_id=org_id, actor_id=reviewer_id,
                          agent_id=execution["agent_id"], run_id=execution.get("workflow_run_id"))
        action = "mcp." + mcp_openai_tool_name(str(server.get("server_name") or ""), str(tool["tool_name"]))
        try:
            await run_io(assert_agent_tool_permission, ctx, action, None, "mcp")
        except ToolPermissionDeniedError as exc:
            raise HTTPException(403, "This agent no longer permits the proposed tool") from exc
    if not resume:
        await run_io(_claim_decision, client, org_id, approval_id, reviewer_id, decision)
    await run_io(write_audit_event, client, org_id=org_id, actor_id=reviewer_id,
        action="mcp.approval.resumed" if resume else "mcp.approval.decided",
        resource_type="approval", resource_id=approval_id,
        metadata={"decision": decision, "tool_id": tool_id, "execution_id": execution_id,
                  "input_sha256": expected_hash, "target_digest": context.get("target_digest")})
    try:
        result = await service.execute_tool(
            tool_id, org_id, args, approval_id=approval_id, actor_id=reviewer_id,
            agent_id=execution.get("agent_id"), workflow_run_id=execution.get("workflow_run_id"),
        )
    except ValueError as exc:
        raise HTTPException(409, "Approved proposal could not start; review its current target") from exc
    final = result.get("status")
    if final in {"completed", "failed", "verification_inconclusive"}:
        await run_io(lambda: (client.table("mcp_tool_executions").update({"status": final})
            .eq("id", execution_id).eq("org_id", org_id).eq("approval_id", approval_id).execute()))
    return {"success": True, "approval_id": approval_id,
            "message": "Approval recorded. Check the execution result for provider confirmation.",
            "status": decision, "execution_result": result,
            "provider_accepted": bool(safe_normalize_stored_dict(result, key="verification").get("providerAccepted")),
            "verified": False}
