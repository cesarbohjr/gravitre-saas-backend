from unittest.mock import MagicMock

from app.capabilities.usage import record_mcp_execution, record_reasoning_selection


def test_reasoning_usage_never_stores_prompt_or_content() -> None:
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock()
    record_reasoning_selection(
        client,
        org_id="org-1",
        package_ids=["pkg-1", "pkg-1", "pkg-2"],
        user_id="user-1",
        conversation_id="conv-1",
        surface="chat",
    )
    rows = client.table.return_value.insert.call_args.args[0]
    assert len(rows) == 2
    assert all(row["metadata"] == {"contentStored": False} for row in rows)
    assert all("prompt" not in row and "content" not in row for row in rows)


def test_mcp_usage_stores_only_attribution_metadata() -> None:
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock()
    record_mcp_execution(
        client,
        org_id="org-1",
        package_id="pkg-1",
        workflow_run_id="run-1",
    )
    row = client.table.return_value.insert.call_args.args[0]
    assert row["event_type"] == "mcp_tool_executed"
    assert row["package_id"] == "pkg-1"
    assert row["metadata"] == {
        "contentStored": False,
        "workflowRunId": "run-1",
    }
    assert "input" not in row
    assert "output" not in row
