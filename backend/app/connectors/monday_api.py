"""Monday.com GraphQL API client."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

MONDAY_API_URL = "https://api.monday.com/v2"
TIMEOUT_SEC = 30.0


class MondayAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _graphql(access_token: str, query: str, variables: dict[str, Any] | None = None) -> Any:
    headers = {
        "Authorization": access_token,
        "Content-Type": "application/json",
        "API-Version": "2024-10",
    }
    body: dict[str, Any] = {"query": query}
    if variables:
        body["variables"] = variables
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(MONDAY_API_URL, headers=headers, json=body)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise MondayAPIError(
            f"Monday API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    payload = response.json()
    if payload.get("errors"):
        raise MondayAPIError("Monday GraphQL error", status_code=400, details=payload["errors"])
    return payload.get("data")


def ensure_monday_session(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "monday", environment_name=environment_name)
    if not conn:
        raise MondayAPIError("No active Monday.com connector found", status_code=404)
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="monday",
        environment_name=environment_name,
    )
    if not token:
        raise MondayAPIError(err or "Monday.com OAuth not connected", status_code=401)
    return cid, token


def list_boards(access_token: str, *, limit: int = 50) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "query ($limit: Int!) { boards(limit: $limit) { id name state } }",
        {"limit": limit},
    )
    return data if isinstance(data, dict) else {"boards": data}


def get_item(access_token: str, item_id: str) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "query ($ids: [ID!]!) { items(ids: $ids) { id name state column_values { id title type value text } } }",
        {"ids": [str(item_id)]},
    )
    return data if isinstance(data, dict) else {"items": data}


def list_users(access_token: str) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "query { users(kind: all) { id name email title is_admin } }",
    )
    return data if isinstance(data, dict) else {"users": data}


def create_item(access_token: str, *, board_id: str, item_name: str, group_id: str | None = None) -> dict[str, Any]:
    variables: dict[str, Any] = {"boardId": str(board_id), "itemName": item_name}
    query = "mutation ($boardId: ID!, $itemName: String!, $groupId: String) { create_item(board_id: $boardId, item_name: $itemName, group_id: $groupId) { id name } }"
    if group_id:
        variables["groupId"] = str(group_id)
    else:
        variables["groupId"] = None
    data = _graphql(access_token, query, variables)
    return data if isinstance(data, dict) else {"create_item": data}


def update_item_column(
    access_token: str,
    *,
    board_id: str,
    item_id: str,
    column_id: str,
    value: Any,
) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "mutation ($boardId: ID!, $itemId: ID!, $columnId: String!, $value: JSON!) { change_column_value(board_id: $boardId, item_id: $itemId, column_id: $columnId, value: $value) { id } }",
        {
            "boardId": str(board_id),
            "itemId": str(item_id),
            "columnId": str(column_id),
            "value": value,
        },
    )
    return data if isinstance(data, dict) else {"change_column_value": data}


def create_update(access_token: str, *, item_id: str, body: str) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "mutation ($itemId: ID!, $body: String!) { create_update(item_id: $itemId, body: $body) { id } }",
        {"itemId": str(item_id), "body": body},
    )
    return data if isinstance(data, dict) else {"create_update": data}


def trigger_automation_via_column(
    access_token: str,
    *,
    board_id: str,
    item_id: str,
    column_id: str,
    value: Any,
) -> dict[str, Any]:
    return update_item_column(
        access_token,
        board_id=board_id,
        item_id=item_id,
        column_id=column_id,
        value=value,
    )


def batch_create_items(
    access_token: str,
    *,
    board_id: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    for item in items:
        name = str(item.get("name") or item.get("item_name") or "")
        if not name:
            continue
        result = create_item(
            access_token,
            board_id=board_id,
            item_name=name,
            group_id=item.get("group_id") or item.get("groupId"),
        )
        created.append(result.get("create_item") or result)
    return {"items": created}


def delete_item(access_token: str, item_id: str) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "mutation ($itemId: ID!) { delete_item(id: $itemId) { id } }",
        {"itemId": str(item_id)},
    )
    return {"item_id": str(item_id), "deleted": True, "result": data}


def get_board(access_token: str, board_id: str) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "query ($ids: [ID!]!) { boards(ids: $ids) { id name description state columns { id title type } groups { id title } } }",
        {"ids": [str(board_id)]},
    )
    return data if isinstance(data, dict) else {"boards": data}


def list_workspaces(access_token: str) -> dict[str, Any]:
    data = _graphql(
        access_token,
        "query { me { id name email account { id name slug plan { tier } } } }",
    )
    return data if isinstance(data, dict) else {"me": data}
