"""Greenhouse Harvest API client (STA-88)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.connectors.managed_oauth import ManagedOAuthAccessToken, managed_oauth_tokens
from app.core.safe_dict import safe_normalize_stored_dict

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
    if safe_normalize_stored_dict(conn, key="config").get("auth_provider") == "managed":
        try:
            tokens = managed_oauth_tokens(client, org_id, cid, settings, environment_name=environment_name, expected_vendor="greenhouse")
            if not tokens:
                raise ValueError("Managed authorization unavailable")
        except ValueError as exc:
            raise GreenhouseAPIError("Greenhouse authorization unavailable; reconnect", status_code=401) from exc
        return cid, ManagedOAuthAccessToken(tokens["access_token"])
    api_key = get_decrypted_secret(client, cid, "api_key", settings, org_id=org_id) or get_decrypted_secret(
        client, cid, "harvest_api_key", settings,
        org_id=org_id,
    )
    if not api_key:
        raise GreenhouseAPIError("Greenhouse Harvest API key missing", status_code=401)
    return cid, api_key.strip()


def _request(method: str, api_key: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
    managed = isinstance(api_key, ManagedOAuthAccessToken)
    base = "https://harvest.greenhouse.io/v3" if managed else HARVEST_API_BASE
    url = f"{base}/{path.lstrip('/')}"
    headers = {"Accept": "application/json"}
    if managed:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(
            method,
            url,
            auth=None if managed else (api_key, ""),
            headers=headers,
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
    if isinstance(api_key, ManagedOAuthAccessToken):
        if not candidate_id.isascii() or not candidate_id.isdigit() or int(candidate_id) < 1:
            raise GreenhouseAPIError("candidate_id must be a positive integer", status_code=400)
        data = _request("GET", api_key, "candidates", params={"ids": candidate_id, "per_page": 1})
        rows = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
        candidate = next((row for row in rows if isinstance(row, dict) and str(row.get("id")) == candidate_id), None)
        if candidate is None:
            raise GreenhouseAPIError("Candidate not found", status_code=404)
        return candidate
    return _request("GET", api_key, f"candidates/{candidate_id}")


def list_applications(api_key: str, *, job_id: str | None = None) -> dict[str, Any]:
    params = {"job_ids" if isinstance(api_key, ManagedOAuthAccessToken) else "job_id": job_id} if job_id else None
    return _request("GET", api_key, "applications", params=params)


def list_jobs(api_key: str) -> dict[str, Any]:
    return _request("GET", api_key, "jobs")
