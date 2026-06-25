"""Apollo.io REST API client (API key auth)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

APOLLO_API_BASE = "https://api.apollo.io/api/v1"
TIMEOUT_SEC = 30.0


class ApolloAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_apollo_api_key(
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
        conn = get_connector_by_type(client, org_id, "apollo", environment_name=environment_name)
    if not conn:
        raise ApolloAPIError("No active Apollo connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if not api_key:
        raise ApolloAPIError("Apollo API key not configured", status_code=401)
    return cid, api_key.strip()


def _request(
    api_key: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{APOLLO_API_BASE}{path}"
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise ApolloAPIError(
            f"Apollo API {response.status_code}: {path}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def verify_apollo_api_key(api_key: str) -> bool:
    """Lightweight health probe using people search with page size 1."""
    try:
        _request(api_key, "POST", "/mixed_people/api_search", params={"per_page": 1})
        return True
    except ApolloAPIError as exc:
        if exc.status_code in {401, 403}:
            return False
        raise


def apollo_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    try:
        _cid, api_key = resolve_apollo_api_key(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
        return "connected" if verify_apollo_api_key(api_key) else "auth_expired"
    except ApolloAPIError as exc:
        if exc.status_code in {401, 403, 404}:
            return "auth_expired" if exc.status_code != 404 else "misconfigured"
        return "misconfigured"


def search_people(api_key: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return _request(api_key, "POST", "/mixed_people/api_search", params=params or {})


def search_organizations(api_key: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return _request(api_key, "POST", "/mixed_companies/search", params=params or {})


def get_contact(api_key: str, contact_id: str) -> dict[str, Any]:
    if not contact_id:
        raise ApolloAPIError("contact_id is required")
    return _request(api_key, "GET", f"/contacts/{contact_id}")


def create_contact(api_key: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ApolloAPIError("contact payload is required")
    return _request(api_key, "POST", "/contacts", json_body=payload)


def add_contacts_to_sequence(
    api_key: str,
    *,
    sequence_id: str,
    contact_ids: list[str],
    email_account_id: str | None = None,
) -> dict[str, Any]:
    if not sequence_id or not contact_ids:
        raise ApolloAPIError("sequence_id and contact_ids are required")
    body: dict[str, Any] = {"contact_ids": contact_ids}
    if email_account_id:
        body["email_account_id"] = email_account_id
    return _request(api_key, "POST", f"/emailer_campaigns/{sequence_id}/add_contact_ids", json_body=body)


def bulk_enrich_people(api_key: str, *, details: list[dict[str, Any]]) -> dict[str, Any]:
    if not details:
        raise ApolloAPIError("details[] is required")
    return _request(api_key, "POST", "/people/bulk_match", json_body={"details": details})


def create_task(api_key: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ApolloAPIError("task payload is required")
    return _request(api_key, "POST", "/tasks", json_body=payload)


def subscribe_intent_signals(api_key: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ApolloAPIError("signal subscription payload is required")
    return _request(api_key, "POST", "/intent_signals/search", json_body=payload)


def update_contact(api_key: str, contact_id: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    if not contact_id:
        raise ApolloAPIError("contact_id is required")
    if not payload:
        raise ApolloAPIError("contact payload is required")
    return _request(api_key, "PATCH", f"/contacts/{contact_id}", json_body=payload)


def delete_contact(api_key: str, contact_id: str) -> dict[str, Any]:
    if not contact_id:
        raise ApolloAPIError("contact_id is required")
    return _request(api_key, "DELETE", f"/contacts/{contact_id}")


def remove_contacts_from_sequence(
    api_key: str,
    *,
    sequence_ids: list[str],
    contact_ids: list[str],
    mode: str = "remove",
) -> dict[str, Any]:
    if not sequence_ids or not contact_ids:
        raise ApolloAPIError("sequence_ids and contact_ids are required")
    if mode not in {"remove", "stop", "mark_as_finished"}:
        raise ApolloAPIError("mode must be remove, stop, or mark_as_finished")
    params: dict[str, Any] = {
        "emailer_campaign_ids[]": sequence_ids,
        "contact_ids[]": contact_ids,
        "mode": mode,
    }
    return _request(api_key, "POST", "/emailer_campaigns/remove_or_stop_contact_ids", params=params)
