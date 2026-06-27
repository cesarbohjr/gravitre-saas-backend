"""Pipedrive API v1 client — OAuth via generic_oauth registry."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.hubspot_oauth import load_oauth_tokens
from app.connectors.repository import get_connector, get_connector_by_type

DEFAULT_API_DOMAIN = "https://api.pipedrive.com"
TIMEOUT_SEC = 30.0


class PipedriveAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _api_base_from_tokens(tokens: dict[str, Any] | None) -> str:
    domain = str((tokens or {}).get("api_domain") or DEFAULT_API_DOMAIN).strip().rstrip("/")
    return domain or DEFAULT_API_DOMAIN


def ensure_pipedrive_session(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str, str]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "pipedrive", environment_name=environment_name)
    if not conn:
        raise PipedriveAPIError("No active Pipedrive connector found", status_code=404)
    cid = str(conn["id"])
    env = conn.get("environment") or environment_name
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="pipedrive",
        environment_name=env,
    )
    if not token:
        raise PipedriveAPIError(err or "Pipedrive OAuth not connected", status_code=401)
    tokens = load_oauth_tokens(client, cid, settings)
    return cid, token, _api_base_from_tokens(tokens)


def test_pipedrive_connection(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[bool, str]:
    try:
        _cid, token, api_base = ensure_pipedrive_session(
            client,
            org_id,
            connector_id,
            settings,
            environment_name=environment_name,
        )
        profile = get_current_user(token, api_base=api_base)
        name = profile.get("data", {}).get("name") or profile.get("data", {}).get("email")
        if name:
            return True, f"Pipedrive connection is valid ({name})"
        return True, "Pipedrive connection is valid"
    except PipedriveAPIError as exc:
        return False, str(exc)
    except httpx.HTTPError as exc:
        return False, f"Pipedrive connection failed: {type(exc).__name__}"


def _request(
    method: str,
    path: str,
    access_token: str,
    *,
    api_base: str = DEFAULT_API_DOMAIN,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    base = api_base.rstrip("/")
    url = f"{base}/api/v1/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise PipedriveAPIError(
            f"Pipedrive API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def get_current_user(access_token: str, *, api_base: str = DEFAULT_API_DOMAIN) -> dict[str, Any]:
    return _request("GET", "users/me", access_token, api_base=api_base)


def search_persons(
    access_token: str,
    *,
    api_base: str,
    term: str,
    limit: int = 10,
) -> dict[str, Any]:
    return _request(
        "GET",
        "persons/search",
        access_token,
        api_base=api_base,
        params={"term": term, "limit": max(1, min(limit, 50))},
    )


def get_person(access_token: str, *, api_base: str, person_id: str | int) -> dict[str, Any]:
    return _request("GET", f"persons/{person_id}", access_token, api_base=api_base)


def list_deals(
    access_token: str,
    *,
    api_base: str,
    status: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
    if status:
        params["status"] = status
    return _request("GET", "deals", access_token, api_base=api_base, params=params)


def get_deal(access_token: str, *, api_base: str, deal_id: str | int) -> dict[str, Any]:
    return _request("GET", f"deals/{deal_id}", access_token, api_base=api_base)


def list_organizations(
    access_token: str,
    *,
    api_base: str,
    limit: int = 10,
) -> dict[str, Any]:
    return _request(
        "GET",
        "organizations",
        access_token,
        api_base=api_base,
        params={"limit": max(1, min(limit, 100))},
    )


def list_pipelines(access_token: str, *, api_base: str) -> dict[str, Any]:
    return _request("GET", "pipelines", access_token, api_base=api_base)


def create_person(
    access_token: str,
    *,
    api_base: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _request("POST", "persons", access_token, api_base=api_base, json_body=payload)


def update_person(
    access_token: str,
    *,
    api_base: str,
    person_id: str | int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _request("PUT", f"persons/{person_id}", access_token, api_base=api_base, json_body=payload)


def create_deal(
    access_token: str,
    *,
    api_base: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _request("POST", "deals", access_token, api_base=api_base, json_body=payload)


def update_deal(
    access_token: str,
    *,
    api_base: str,
    deal_id: str | int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _request("PUT", f"deals/{deal_id}", access_token, api_base=api_base, json_body=payload)
