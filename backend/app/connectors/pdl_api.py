"""People Data Labs API client (BYO API key).

Docs: https://docs.peopledatalabs.com/
Base: https://api.peopledatalabs.com/v5/
Auth: X-Api-Key header (tenant key only — never a shared Gravitree key).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.intelligence_packs.shared.auth_mode import assert_byo_never_uses_platform_key

PDL_API_BASE = "https://api.peopledatalabs.com/v5"
TIMEOUT_SEC = 45.0
RESULT_URL = "https://dashboard.peopledatalabs.com/"


class PdlAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_pdl_connector(
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
        conn = get_connector_by_type(client, org_id, "pdl", environment_name=environment_name)
    if not conn:
        raise PdlAPIError("No active People Data Labs connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if not api_key:
        raise PdlAPIError(
            "People Data Labs API key not configured (BYO — connect your own key)",
            status_code=401,
        )
    assert_byo_never_uses_platform_key("pdl", resolved_from="org_secret")
    return cid, api_key.strip()


def _request(api_key: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
    url = f"{PDL_API_BASE}{path}"
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.get(url, headers=headers, params=params or {})
    body_text = response.text or ""
    if response.status_code >= 400:
        raise PdlAPIError(
            body_text[:500] or f"PDL API error {response.status_code}",
            status_code=response.status_code,
            details=body_text,
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001
        raise PdlAPIError("Invalid JSON from People Data Labs", status_code=502, details=body_text) from exc


def person_enrich(api_key: str, *, params: dict[str, Any]) -> dict[str, Any]:
    """One-to-one person enrich. Pass any PDL person match params (email, profile, name+company, …)."""
    clean = {k: v for k, v in (params or {}).items() if v is not None and str(v).strip() != ""}
    if not clean:
        raise PdlAPIError(
            "pdl.person.enrich requires at least one match field (email, profile, name+company, …)",
            status_code=400,
        )
    data = _request(api_key, "/person/enrich", params=clean)
    return {"data": data, "result_url": RESULT_URL}


def company_enrich(api_key: str, *, params: dict[str, Any]) -> dict[str, Any]:
    """One-to-one company enrich. Requires name, website, ticker, or profile."""
    clean = {k: v for k, v in (params or {}).items() if v is not None and str(v).strip() != ""}
    if not any(k in clean for k in ("name", "website", "ticker", "profile")):
        raise PdlAPIError(
            "pdl.company.enrich requires name, website, ticker, or profile",
            status_code=400,
        )
    data = _request(api_key, "/company/enrich", params=clean)
    return {"data": data, "result_url": RESULT_URL}
