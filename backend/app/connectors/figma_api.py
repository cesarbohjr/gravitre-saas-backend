"""Figma REST API client (OAuth 2)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

FIGMA_API_BASE = "https://api.figma.com/v1"
TIMEOUT_SEC = 30.0


class FigmaAPIError(Exception):
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
    url = f"{FIGMA_API_BASE}{path}"
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
        raise FigmaAPIError(
            f"Figma API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def ensure_figma_session(
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
        conn = get_connector_by_type(client, org_id, "figma", environment_name=environment_name)
    if not conn:
        raise FigmaAPIError("No active Figma connector found", status_code=404)
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="figma",
        environment_name=environment_name,
    )
    if not token:
        raise FigmaAPIError(err or "Figma OAuth not connected", status_code=401)
    return cid, token


def get_me(access_token: str) -> dict[str, Any]:
    data = _request("GET", "/me", access_token)
    return data if isinstance(data, dict) else {"user": data}


def get_file(
    access_token: str,
    file_key: str,
    *,
    version: str | None = None,
    depth: int | None = None,
    geometry: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if version:
        params["version"] = version
    if depth is not None:
        params["depth"] = depth
    if geometry:
        params["geometry"] = geometry
    data = _request("GET", f"/files/{file_key}", access_token, params=params or None)
    return data if isinstance(data, dict) else {"file": data}


def get_file_meta(access_token: str, file_key: str) -> dict[str, Any]:
    data = _request("GET", f"/files/{file_key}/meta", access_token)
    return data if isinstance(data, dict) else {"meta": data}


def list_team_projects(access_token: str, team_id: str) -> dict[str, Any]:
    data = _request("GET", f"/teams/{team_id}/projects", access_token)
    return data if isinstance(data, dict) else {"projects": data}


def list_project_files(
    access_token: str,
    project_id: str,
    *,
    branch_data: bool = False,
) -> dict[str, Any]:
    params = {"branch_data": "true" if branch_data else "false"}
    data = _request("GET", f"/projects/{project_id}/files", access_token, params=params)
    return data if isinstance(data, dict) else {"files": data}


def list_comments(access_token: str, file_key: str) -> dict[str, Any]:
    data = _request("GET", f"/files/{file_key}/comments", access_token)
    return data if isinstance(data, dict) else {"comments": data}


def create_comment(access_token: str, file_key: str, body: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", f"/files/{file_key}/comments", access_token, json_body=body)
    return data if isinstance(data, dict) else {"comment": data}


def delete_comment(access_token: str, file_key: str, comment_id: str) -> dict[str, Any]:
    data = _request("DELETE", f"/files/{file_key}/comments/{comment_id}", access_token)
    return data if isinstance(data, dict) else {}


def create_dev_resource(access_token: str, file_key: str, body: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", f"/files/{file_key}/dev_resources", access_token, json_body=body)
    return data if isinstance(data, dict) else {"dev_resource": data}


def list_file_versions(access_token: str, file_key: str) -> dict[str, Any]:
    data = _request("GET", f"/files/{file_key}/versions", access_token)
    return data if isinstance(data, dict) else {"versions": data}


def export_images(
    access_token: str,
    file_key: str,
    *,
    ids: str,
    format: str = "png",
    scale: float | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"ids": ids, "format": format}
    if scale is not None:
        params["scale"] = scale
    data = _request("GET", f"/images/{file_key}", access_token, params=params)
    return data if isinstance(data, dict) else {"images": data}


def batch_export_images(
    access_token: str,
    *,
    file_key: str,
    node_id_groups: list[list[str]],
    format: str = "png",
    scale: float | None = None,
) -> dict[str, Any]:
    exports: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, node_ids in enumerate(node_id_groups):
        ids = ",".join(str(n) for n in node_ids if n)
        if not ids:
            errors.append({"index": index, "error": "empty node_ids"})
            continue
        try:
            result = export_images(
                access_token,
                file_key,
                ids=ids,
                format=format,
                scale=scale,
            )
            exports.append({"index": index, "node_ids": node_ids, "result": result})
        except FigmaAPIError as exc:
            errors.append({"index": index, "node_ids": node_ids, "error": str(exc), "details": exc.details})
    return {"exports": exports, "errors": errors}
