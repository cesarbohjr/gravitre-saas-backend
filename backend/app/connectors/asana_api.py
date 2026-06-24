"""Asana REST API client."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

ASANA_API_BASE = "https://app.asana.com/api/1.0"
TIMEOUT_SEC = 30.0


class AsanaAPIError(Exception):
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
    url = f"{ASANA_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
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
        raise AsanaAPIError(
            f"Asana API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    payload = response.json()
    return payload.get("data", payload)


def ensure_asana_session(
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
        conn = get_connector_by_type(client, org_id, "asana", environment_name=environment_name)
    if not conn:
        raise AsanaAPIError("No active Asana connector found", status_code=404)
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="asana",
        environment_name=environment_name,
    )
    if not token:
        raise AsanaAPIError(err or "Asana OAuth not connected", status_code=401)
    return cid, token


def get_task(access_token: str, task_id: str) -> dict[str, Any]:
    data = _request("GET", f"/tasks/{task_id}", access_token)
    return data if isinstance(data, dict) else {"task": data}


def list_projects(
    access_token: str,
    *,
    workspace_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if workspace_id:
        params["workspace"] = workspace_id
    if limit is not None:
        params["limit"] = limit
    data = _request("GET", "/projects", access_token, params=params or None)
    return {"projects": data if isinstance(data, list) else [data]}


def list_users(access_token: str, *, workspace_id: str | None = None) -> dict[str, Any]:
    params = {"workspace": workspace_id} if workspace_id else None
    data = _request("GET", "/users", access_token, params=params)
    return {"users": data if isinstance(data, list) else [data]}


def create_task(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/tasks", access_token, json_body={"data": payload})
    return data if isinstance(data, dict) else {"task": data}


def update_task(access_token: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("PUT", f"/tasks/{task_id}", access_token, json_body={"data": payload})
    return data if isinstance(data, dict) else {"task": data}


def create_story(access_token: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", f"/tasks/{task_id}/stories", access_token, json_body={"data": payload})
    return data if isinstance(data, dict) else {"story": data}


def add_task_to_project(
    access_token: str,
    task_id: str,
    *,
    project_id: str,
    section_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"project": project_id}
    if section_id:
        body["section"] = section_id
    data = _request("POST", f"/tasks/{task_id}/addProject", access_token, json_body={"data": body})
    return data if isinstance(data, dict) else {"membership": data}


def move_task_to_section(access_token: str, section_id: str, task_id: str) -> dict[str, Any]:
    data = _request(
        "POST",
        f"/sections/{section_id}/addTask",
        access_token,
        json_body={"data": {"task": task_id}},
    )
    return data if isinstance(data, dict) else {"section": data}


def batch_task_updates(access_token: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    data = _request("POST", "/batch", access_token, json_body={"data": {"actions": actions}})
    return data if isinstance(data, dict) else {"batch": data}


def delete_task(access_token: str, task_id: str) -> dict[str, Any]:
    _request("DELETE", f"/tasks/{task_id}", access_token)
    return {"task_id": str(task_id), "deleted": True}


def list_workspaces(access_token: str) -> dict[str, Any]:
    data = _request("GET", "/workspaces", access_token)
    return {"workspaces": data if isinstance(data, list) else [data]}


def search_tasks(
    access_token: str,
    workspace_id: str,
    *,
    text: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if text:
        params["text"] = text
    if limit is not None:
        params["limit"] = limit
    data = _request("GET", f"/workspaces/{workspace_id}/tasks/search", access_token, params=params or None)
    return {"tasks": data if isinstance(data, list) else [data]}
