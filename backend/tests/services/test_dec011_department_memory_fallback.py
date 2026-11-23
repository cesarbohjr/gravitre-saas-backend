"""Department recall must not use alternate reads after RPC denial/outage."""
from unittest.mock import MagicMock, patch

import httpx
from postgrest.exceptions import APIError
import pytest
from supabase import ClientOptions, create_client

from app.services.agent_memory_service import search_department_memories


@pytest.mark.parametrize("code,status", [
    ("42501", 403), ("PGRST301", 401), ("57014", 500),
    ("08006", 500), ("42703", 400), ("42883", 404),
])
def test_nonmissing_rpc_error_never_triggers_table_read(mock_settings, code, status):
    requests = []

    def respond(request):
        requests.append(request)
        if "/rpc/" in request.url.path:
            return httpx.Response(status, json={
                "code": code, "message": "synthetic database error", "details": None, "hint": None,
            })
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = create_client("https://synthetic.test", "synthetic", options=ClientOptions(httpx_client=http))
        with patch("app.services.agent_memory_service.get_embedding", return_value=[0.1]):
            with pytest.raises(APIError) as error:
                search_department_memories(mock_settings, client, "org-a", "dept-a", query="policy")
    assert error.value.code == code
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/rpc/agent_memory_search_by_department")


def test_repository_outage_never_triggers_table_fallback(mock_settings):
    client = MagicMock()
    client.rpc.return_value.execute.side_effect = RuntimeError("synthetic outage")
    with patch("app.services.agent_memory_service.get_embedding", return_value=[0.1]):
        with pytest.raises(RuntimeError, match="synthetic outage"):
            search_department_memories(mock_settings, client, "org-a", "dept-a", query="policy")
    client.table.assert_not_called()


def test_successful_rpc_retains_existing_payload_and_results(mock_settings):
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = [{
        "memory_id": "memory-a", "agent_id": "agent-a", "department_id": "dept-a",
        "content": "current policy", "category": "fact", "score": 0.9,
    }]
    with (
        patch("app.services.agent_memory_service.get_embedding", return_value=[0.1]),
        patch("app.services.agent_memory_service.increment_memory_usage") as usage,
    ):
        rows = search_department_memories(mock_settings, client, "org-a", "dept-a", query="policy")
    assert [r["id"] for r in rows] == ["memory-a"]
    assert rows[0]["score"] == 0.9
    assert client.rpc.call_args.args[1]["p_org_id"] == "org-a"
    assert client.rpc.call_args.args[1]["p_department_id"] == "dept-a"
    usage.assert_called_once_with(client, ["memory-a"], org_id="org-a")
    client.table.assert_not_called()
