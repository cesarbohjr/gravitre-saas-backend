"""Greenhouse Harvest API client (STA-88)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

HARVEST_API_BASE = "https://harvest.greenhouse.io/v1"
TIMEOUT_SEC = 30.0


class GreenhouseAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_greenhouse_api_key(
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
        conn = get_connector_by_type(client, org_id, "greenhouse", environment_name=environment_name)
    if not conn:
        raise GreenhouseAPIError("No active Greenhouse connector found for org")
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_key", settings) or get_decrypted_secret(
        client, cid, "harvest_api_key", settings
    )
    if not api_key:
        raise GreenhouseAPIError("Greenhouse Harvest API key missing", status_code=401)
    return cid, api_key.strip()


def _request(method: str, api_key: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
    url = f"{HARVEST_API_BASE}/{path.lstrip('/')}"
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(
            method,
            url,
            auth=(api_key, ""),
            headers={"Accept": "application/json"},
            params=params,
        )
    if response.status_code >= 400:
        raise GreenhouseAPIError(
            f"Greenhouse API {response.status_code}",
            status_code=response.status_code,
            details=response.text[:500],
        )
    if not response.text:
        return {}
    return response.json()


def get_candidate(api_key: str, candidate_id: str) -> dict[str, Any]:
    return _request("GET", api_key, f"candidates/{candidate_id}")


def list_applications(api_key: str, *, job_id: str | None = None) -> dict[str, Any]:
    params = {"job_id": job_id} if job_id else None
    return _request("GET", api_key, "applications", params=params)


def list_jobs(api_key: str) -> dict[str, Any]:
    return _request("GET", api_key, "jobs")
