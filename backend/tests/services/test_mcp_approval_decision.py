"""Shared decision queue consent binds the persisted proposal, never caller args."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services import mcp_approval_service as decisions
from app.services.mcp_client_service import mcp_approval_target_digest, mcp_input_sha256

TOOL = {"id": "tool", "server_id": "server", "tool_name": "send_email", "capability_tier": "write"}
SERVER = {"id": "server", "server_url": "https://93.184.216.34/mcp", "transport": "streamable_http", "auth_config": {}}
ARGS = {"to": "recipient@example.test", "body": "Synthetic approval test"}


class Query:
    def __init__(self, rows):
        self.rows, self.filters, self.patch = rows, [], None

    def select(self, _): return self
    def eq(self, key, value):
        self.filters.append(lambda row: row.get(key) == value)
        return self
    def is_(self, key, value):
        assert value == "null"
        self.filters.append(lambda row: row.get(key) is None)
        return self
    def limit(self, _): return self
    def update(self, patch):
        self.patch = patch
        return self
    def execute(self):
        rows = [r for r in self.rows if all(f(r) for f in self.filters)]
        for row in rows:
            if self.patch: row.update(deepcopy(self.patch))
        return SimpleNamespace(data=deepcopy(rows))


@pytest.fixture
def state(monkeypatch):
    context = {"mcp_tool_id": "tool", "mcp_execution_id": "execution", "parameters": ARGS,
               "input_sha256": mcp_input_sha256(ARGS), "target_digest": mcp_approval_target_digest(TOOL, SERVER)}
    approval = {"id": "approval", "org_id": "org", "type": "mcp_tool", "status": "pending", "reviewed_at": None, "context": context}
    execution = {"id": "execution", "org_id": "org", "tool_id": "tool", "approval_id": "approval",
                 "input": deepcopy(ARGS), "status": "pending_approval"}
    tables = {"approvals": [approval], "mcp_tool_executions": [execution]}
    client = SimpleNamespace(table=lambda name: Query(tables[name]))
    service = SimpleNamespace(_load_tool=AsyncMock(return_value=TOOL), _load_server=AsyncMock(return_value=SERVER),
                              execute_tool=AsyncMock(return_value={"status": "verification_inconclusive", "verification": {"providerAccepted": True}}))
    role = ["admin"]
    monkeypatch.setattr("app.workflows.policy.get_user_role", lambda *args: role[0])
    monkeypatch.setattr(decisions, "get_mcp_client_service", lambda _: service)
    audits = []
    monkeypatch.setattr("app.workflows.audit.write_audit_event", lambda *args, **kw: audits.append(kw))
    return SimpleNamespace(client=client, service=service, approval=approval, execution=execution, role=role, audits=audits)


async def decide(state, **changes):
    return await decisions.decide_mcp_approval(state.client, None, **{
        "org_id": "org", "approval_id": "approval", "reviewer_id": "reviewer", "approve": True, **changes,
    })


@pytest.mark.asyncio
async def test_admin_approves_exact_stored_payload_once_and_does_not_claim_verified(state):
    result = await decide(state)
    assert result["success"] and result["verified"] is False
    assert result["provider_accepted"] is True
    state.service.execute_tool.assert_awaited_once_with("tool", "org", ARGS, approval_id="approval", actor_id="reviewer", agent_id=None, workflow_run_id=None)
    assert state.approval["reviewed_by"] == "reviewer"
    assert state.audits[0]["metadata"]["input_sha256"] == mcp_input_sha256(ARGS)
    with pytest.raises(HTTPException) as error: await decide(state)
    assert error.value.status_code == 409
    assert state.service.execute_tool.await_count == 1


@pytest.mark.asyncio
async def test_rejection_never_dispatches(state):
    result = await decide(state, approve=False)
    assert result["status"] == state.execution["status"] == "rejected"
    state.service.execute_tool.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("change,code", [("member", 403), ("other_org", 404), ("args", 409), ("reviewed_args", 409), ("target", 409), ("old_contract", 409)])
async def test_no_unauthorized_or_changed_proposal_dispatches(state, change, code):
    org = "org"
    if change == "member": state.role[0] = "member"
    elif change == "other_org": org = "other"
    elif change == "args": state.execution["input"]["to"] = "changed@example.test"
    elif change == "reviewed_args": state.approval["context"]["parameters"] = {"to": "changed@example.test"}
    elif change == "target": state.service._load_server.return_value = {**SERVER, "server_url": "https://93.184.216.35/mcp"}
    else: state.approval["context"].pop("target_digest")
    with pytest.raises(HTTPException) as error: await decide(state, org_id=org)
    assert error.value.status_code == code
    assert state.approval["status"] == "pending"
    state.service.execute_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejecting_orphaned_legacy_proposal_is_possible_without_dispatch(state):
    state.approval["context"] = {}
    assert (await decide(state, approve=False))["status"] == "rejected"
    state.service.execute_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_approved_unconsumed_proposal_can_resume_after_crash(state):
    state.approval.update(status="approved", reviewed_at="2026-10-16T00:00:00Z", consumed_at=None)
    result = await decide(state)
    assert result["verified"] is False
    state.service.execute_tool.assert_awaited_once()
    assert state.audits[0]["action"] == "mcp.approval.resumed"


@pytest.mark.asyncio
async def test_already_consumed_approval_cannot_resume(state):
    state.approval.update(status="approved", reviewed_at="2026-10-16T00:00:00Z", consumed_at="2026-10-16T00:00:01Z")
    with pytest.raises(HTTPException) as error: await decide(state)
    assert error.value.status_code == 409
    state.service.execute_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoked_agent_tool_permission_blocks_admin_dispatch(state, monkeypatch):
    from app.services.tool_types import ToolPermissionDeniedError

    state.execution["agent_id"] = "agent"
    def refuse(*args):
        raise ToolPermissionDeniedError("tool no longer permitted")
    monkeypatch.setattr("app.services.tool_service.assert_agent_tool_permission", refuse)
    with pytest.raises(HTTPException) as error:
        await decide(state)
    assert error.value.status_code == 403
    assert state.approval["status"] == "pending"
    state.service.execute_tool.assert_not_awaited()
