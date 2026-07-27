"""Helpers for conversation_messages inserts (capstone history integrity)."""
from __future__ import annotations

import uuid
from typing import Any


def build_conversation_turn_message_rows(
    *,
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    tool_results: list[dict[str, Any]],
    created_at: str,
    assistant_message_id: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Build user+assistant rows for conversation_messages insert.

    Both rows must carry explicit ids. PostgREST batch inserts unify columns: if
    only the assistant row has id, the user row is sent as id=null and overrides
    DEFAULT gen_random_uuid() → NOT NULL violation (silent history loss).
    """
    user_message_id = str(uuid.uuid4())
    assistant_id = (assistant_message_id or "").strip() or str(uuid.uuid4())
    tool_calls = (
        [
            {
                "name": tool.get("name"),
                "displayName": tool.get("displayName"),
                "input": tool.get("input"),
                "output": tool.get("output"),
                **(
                    {"error": tool.get("error")}
                    if tool.get("error") is not None
                    else {}
                ),
                **(
                    {"errorCode": tool.get("errorCode") or tool.get("error_code")}
                    if tool.get("errorCode") is not None or tool.get("error_code") is not None
                    else {}
                ),
            }
            for tool in tool_results
        ]
        if tool_results
        else None
    )
    rows = [
        {
            "id": user_message_id,
            "conversation_id": conversation_id,
            "role": "user",
            "content": user_text,
            "created_at": created_at,
        },
        {
            "id": assistant_id,
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": tool_calls,
            "created_at": created_at,
        },
    ]
    return rows, assistant_id
