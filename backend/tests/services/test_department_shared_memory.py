"""Department shared memory + sub-agent spawn/list."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cognitive_turn_kernel import CognitiveTurnKernel, CognitiveTurnRequest
from app.services.department_subagent_service import DepartmentSubagentService


def _settings(**kwargs) -> MagicMock:
    s = MagicMock()
    s.cognitive_turn_kernel_enabled = True
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


@pytest.mark.asyncio
async def test_kernel_recall_includes_department_shared_pack():
    kernel = CognitiveTurnKernel(_settings())
    client = MagicMock()
    # Org scan empty
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

    dept_row = {
        "id": "m-dept",
        "org_id": "org-1",
        "agent_id": "agent-peer",
        "department_id": "dept-1",
        "category": "fact",
        "content": "shared department SOP",
        "source": "department_shared_memory",
    }

    with (
        patch(
            "app.services.hybrid_memory_service.HybridMemoryService.query_all_memory",
            new_callable=AsyncMock,
            return_value={"episodic_memories": [], "graph_context": []},
        ),
        patch(
            "app.services.agent_memory_service.search_agent_memories",
            return_value=[],
        ),
        patch(
            "app.rag.department.resolve_department_id_for_agent",
            return_value=("dept-1", "agent-1"),
        ),
        patch(
            "app.services.agent_memory_service.search_department_memories",
            return_value=[dept_row],
        ),
        patch(
            "app.services.cross_conversation_ledger_memory.feature_enabled",
            return_value=False,
        ),
    ):
        pack = await kernel._recall(
            CognitiveTurnRequest(org_id="org-1", message="SOP?", agent_id="agent-1", client=client),
            client,
        )

    episodic = pack.get("episodic") or []
    contents = [str(r.get("content")) for r in episodic if isinstance(r, dict)]
    assert "shared department SOP" in contents
    assert any(
        isinstance(r, dict) and r.get("source") == "department_shared_memory" for r in episodic
    )


def test_spawn_and_list_department_subagents():
    svc = DepartmentSubagentService(settings=_settings())
    umbrella = {
        "id": "umbrella-1",
        "org_id": "org-1",
        "name": "Sales Lead",
        "role": "Lead",
        "department": "Sales",
        "status": "active",
        "config": {},
        "parent_agent_id": None,
        "purpose": "Umbrella",
        "model": "gpt-4.1",
        "capabilities": [],
        "systems": [],
        "guardrails": [],
    }
    child = {
        "id": "child-1",
        "org_id": "org-1",
        "name": "SDR",
        "role": "Specialist",
        "department": "Sales",
        "status": "active",
        "config": {"departmentSubAgent": True},
        "parent_agent_id": "umbrella-1",
        "purpose": "Outbound",
    }
    client = MagicMock()

    def _table(name: str):
        t = MagicMock()
        if name == "agents":
            # get umbrella
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                umbrella
            ]
            # list children
            t.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
                child
            ]
            t.insert.return_value.execute.return_value.data = [child]
        elif name == "departments":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"id": "dept-sales"}
            ]
        return t

    client.table.side_effect = _table

    with (
        patch.object(svc, "_client", return_value=client),
        patch(
            "app.services.department_subagent_service.resolve_department_id_by_name",
            return_value="dept-sales",
        ),
        patch(
            "app.services.department_subagent_service.resolve_department_id_for_agent",
            return_value=("dept-sales", "umbrella-1"),
        ),
    ):
        spawned = svc.spawn_department_subagent(
            "org-1",
            "umbrella-1",
            name="SDR",
            purpose="Outbound",
            actor_id="admin-1",
        )
        listed = svc.list_department_subagents("org-1", "umbrella-1")

    assert spawned["sharedDepartmentMemory"] is True
    assert spawned["agent"]["parentAgentId"] == "umbrella-1"
    assert listed["count"] >= 1
    assert listed["departmentId"] == "dept-sales"
