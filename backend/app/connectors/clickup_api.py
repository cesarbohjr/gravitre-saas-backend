"""ClickUp API v2 client."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

CLICKUP_API_BASE = "https://api.clickup.com/api/v2"
TIMEOUT_SEC = 30.0


class ClickUpAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    method: str,
    path: str,
    access_token: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{CLICKUP_API_BASE}{path}"
    headers = {
        "Authorization": access_token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise ClickUpAPIError(
            f"ClickUp API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def ensure_clickup_session(
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
        conn = get_connector_by_type(client, org_id, "clickup", environment_name=environment_name)
    if not conn:
        raise ClickUpAPIError("No active ClickUp connector found", status_code=404)
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="clickup",
        environment_name=environment_name,
    )
    if not token:
        raise ClickUpAPIError(err or "ClickUp OAuth not connected", status_code=401)
    return cid, token


def resolve_team_id(access_token: str, team_id: str | None = None) -> str:
    if team_id:
        return str(team_id)
    data = _request("GET", "/team", access_token)
    teams = data.get("teams") if isinstance(data, dict) else None
    if not teams or not isinstance(teams, list):
        raise ClickUpAPIError("No ClickUp teams found for this account")
    first = teams[0]
    tid = first.get("id") if isinstance(first, dict) else None
    if not tid:
        raise ClickUpAPIError("ClickUp team id missing from API response")
    return str(tid)


def get_task(access_token: str, task_id: str) -> dict[str, Any]:
    data = _request("GET", f"/task/{task_id}", access_token)
    return data if isinstance(data, dict) else {"task": data}


def get_list(access_token: str, list_id: str) -> dict[str, Any]:
    data = _request("GET", f"/list/{list_id}", access_token)
    return data if isinstance(data, dict) else {"list": data}


def list_spaces(access_token: str, *, team_id: str | None = None) -> dict[str, Any]:
    tid = resolve_team_id(access_token, team_id)
    data = _request("GET", f"/team/{tid}/space", access_token)
    return data if isinstance(data, dict) else {"spaces": data}


def list_tasks(
    access_token: str,
    *,
    team_id: str | None = None,
    list_id: str | None = None,
    include_closed: bool = False,
) -> dict[str, Any]:
    """List ClickUp tasks for a team (or a specific list when list_id is set)."""
    if list_id:
        data = _request(
            "GET",
            f"/list/{list_id}/task",
            access_token,
            params={"include_closed": str(bool(include_closed)).lower()},
        )
        return data if isinstance(data, dict) else {"tasks": data}
    tid = resolve_team_id(access_token, team_id)
    data = _request(
        "GET",
        f"/team/{tid}/task",
        access_token,
        params={"include_closed": str(bool(include_closed)).lower()},
    )
    return data if isinstance(data, dict) else {"tasks": data}


def create_task(access_token: str, list_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", f"/list/{list_id}/task", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"task": data}


def update_task(access_token: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("PUT", f"/task/{task_id}", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"task": data}


def create_comment(access_token: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", f"/task/{task_id}/comment", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"comment": data}


def create_time_entry(
    access_token: str,
    *,
    team_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    tid = resolve_team_id(access_token, team_id)
    data = _request("POST", f"/team/{tid}/time", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"time_entry": data}


def update_goal(access_token: str, goal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("PUT", f"/goal/{goal_id}", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"goal": data}


def create_webhook(
    access_token: str,
    *,
    team_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    tid = resolve_team_id(access_token, team_id)
    data = _request("POST", f"/team/{tid}/webhook", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"webhook": data}


def delete_task(access_token: str, task_id: str) -> dict[str, Any]:
    _request("DELETE", f"/task/{task_id}", access_token)
    return {"task_id": str(task_id), "deleted": True}


def bulk_update_tasks(access_token: str, list_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("PUT", f"/list/{list_id}/task/bulk", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"tasks": data}


def list_team_members(access_token: str, *, team_id: str | None = None) -> dict[str, Any]:
    tid = resolve_team_id(access_token, team_id)
    data = _request("GET", f"/team/{tid}/member", access_token)
    return data if isinstance(data, dict) else {"members": data}
