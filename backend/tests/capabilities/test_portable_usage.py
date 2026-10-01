from unittest.mock import MagicMock

from app.capabilities.usage import record_reasoning_selection


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
