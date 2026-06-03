from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.rag.department import resolve_department_id_for_agent, resolve_department_id_by_name


def test_resolve_department_id_by_name():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "dept-1"}]
    )
    assert resolve_department_id_by_name(client, "org-1", "Sales") == "dept-1"


def test_resolve_department_id_for_agent():
    client = MagicMock()
    agents_chain = MagicMock()
    agents_chain.execute.return_value = MagicMock(data=[{"id": "agent-1", "department": "Sales"}])
    dept_chain = MagicMock()
    dept_chain.execute.return_value = MagicMock(data=[{"id": "dept-1"}])

    def table_side_effect(name):
        chain = MagicMock()
        if name == "agents":
            chain.select.return_value.eq.return_value.eq.return_value.limit.return_value = agents_chain
        elif name == "departments":
            chain.select.return_value.eq.return_value.eq.return_value.limit.return_value = dept_chain
        return chain

    client.table.side_effect = table_side_effect
    dept_id, agent_id = resolve_department_id_for_agent(client, "org-1", "agent-1")
    assert dept_id == "dept-1"
    assert agent_id == "agent-1"


def test_search_chunks_passes_department_filter():
    from app.rag.retrieval import search_chunks

    settings = MagicMock(supabase_url="https://x.supabase.co", supabase_service_role_key="key")
    with patch("app.rag.retrieval.create_client") as mock_client:
        rpc = mock_client.return_value.rpc
        rpc.return_value.execute.return_value = MagicMock(data=[])
        search_chunks(
            settings,
            "org-1",
            [0.1, 0.2],
            department_id="dept-1",
            agent_id="agent-1",
        )
        payload = rpc.call_args[0][1]
        assert payload["p_department_id"] == "dept-1"
        assert payload["p_agent_id"] == "agent-1"
