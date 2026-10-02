"""Minimal Nango backend client for Gravitre-managed long-tail auth and proxying."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


DEFAULT_NANGO_API_BASE_URL = "https://api.nango.dev"


def nango_configured(settings: Settings) -> bool:
    return bool((settings.nango_secret_key or "").strip())


def _base_url(settings: Settings) -> str:
    return (settings.nango_api_base_url or DEFAULT_NANGO_API_BASE_URL).strip().rstrip("/")


def _auth_headers(settings: Settings) -> dict[str, str]:
    secret = (settings.nango_secret_key or "").strip()
    if not secret:
        raise ValueError("Nango is not configured")
    return {"Authorization": f"Bearer {secret}"}


def create_connect_session(
    settings: Settings,
    *,
    end_user_id: str,
    end_user_email: str | None,
    organization_id: str,
    organization_name: str | None,
    integration_ids: list[str],
    connector_id: str | None = None,
) -> dict[str, Any]:
    """Create a short-lived Connect UI session. Provider credentials never enter Gravitre."""
    tags: dict[str, str] = {
        "end_user_id": str(end_user_id),
        "organization_id": str(organization_id),
    }
    if end_user_email:
        tags["end_user_email"] = str(end_user_email)
    if connector_id:
        tags["connector_id"] = str(connector_id)

    payload: dict[str, Any] = {
        "tags": tags,
        "allowed_integrations": [str(value) for value in integration_ids if str(value).strip()],
    }
    if organization_name:
        payload["organization"] = {
            "id": str(organization_id),
            "display_name": str(organization_name),
        }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{_base_url(settings)}/connect/sessions",
            headers={**_auth_headers(settings), "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or not data.get("token"):
        raise ValueError("Nango connect session response did not include a token")
    return data


def proxy_request(
    settings: Settings,
    *,
    method: str,
    endpoint: str,
    connection_id: str,
    integration_id: str,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Proxy a provider request through Nango while keeping execution inside Gravitre."""
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    headers = {
        **_auth_headers(settings),
        "Connection-Id": connection_id,
        "Provider-Config-Key": integration_id,
        **(extra_headers or {}),
    }
    with httpx.Client(timeout=60.0) as client:
        return client.request(
            method.upper(),
            f"{_base_url(settings)}/proxy{path}",
            headers=headers,
            params=params,
            json=json_body,
        )
