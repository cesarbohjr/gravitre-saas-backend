"""Apollo.io REST API client (OAuth partner flow + legacy API key fallback)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import (
    ensure_generic_session,
    generic_connection_auth_status,
    generic_oauth_configured,
)
from app.connectors.hubspot_oauth import load_oauth_tokens
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

APOLLO_API_BASE = "https://api.apollo.io/api/v1"
TIMEOUT_SEC = 30.0


class ApolloAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _format_apollo_error_detail(detail: Any) -> str:
    """Extract a short human-readable reason from Apollo error payloads."""
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail.strip()[:300]
    if not isinstance(detail, dict):
        return str(detail)[:300]
    for key in ("error", "message", "error_message", "detail"):
        value = detail.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:300]
        if isinstance(value, list) and value:
            return "; ".join(str(item) for item in value[:3])[:300]
    errors = detail.get("errors")
    if isinstance(errors, list) and errors:
        return "; ".join(str(item) for item in errors[:3])[:300]
    if isinstance(errors, dict) and errors:
        parts = [f"{k}: {v}" for k, v in list(errors.items())[:3]]
        return "; ".join(parts)[:300]
    return ""


def _connector_auth_type(client: Any, org_id: str, connector_id: str) -> str:
    row = (
        client.table("connectors")
        .select("config")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    config = dict((row.data or [{}])[0].get("config") or {})
    return str(config.get("auth_type") or "").strip().lower()


def resolve_apollo_connector(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, dict[str, Any]]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "apollo", environment_name=environment_name)
    if not conn:
        raise ApolloAPIError("No active Apollo connector found", status_code=404)
    cid = str(conn["id"])

    oauth_tokens = load_oauth_tokens(client, cid, settings)
    if oauth_tokens and oauth_tokens.get("access_token"):
        access, err = ensure_generic_session(
            client,
            org_id,
            cid,
            settings,
            vendor="apollo",
            environment_name=environment_name,
        )
        if access:
            return cid, {"Authorization": f"Bearer {access}"}
        if err and _connector_auth_type(client, org_id, cid) == "oauth":
            raise ApolloAPIError(err, status_code=401)

    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if api_key:
        return cid, {"X-Api-Key": api_key.strip()}

    raise ApolloAPIError("Apollo OAuth or API key not configured", status_code=401)


def resolve_apollo_api_key(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str]:
    """Legacy helper — returns API key when present, otherwise OAuth bearer token string."""
    cid, headers = resolve_apollo_connector(
        client, org_id, connector_id, settings, environment_name=environment_name
    )
    if "X-Api-Key" in headers:
        return cid, str(headers["X-Api-Key"])
    auth = str(headers.get("Authorization") or "")
    if auth.lower().startswith("bearer "):
        return cid, auth[7:].strip()
    raise ApolloAPIError("Apollo credentials not configured", status_code=401)


def _request(
    auth_headers: dict[str, str],
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{APOLLO_API_BASE}{path}"
    headers = {
        **auth_headers,
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
        detail_text = _format_apollo_error_detail(detail)
        message = f"Apollo API {response.status_code}: {path}"
        if detail_text:
            message = f"{message} — {detail_text}"
        raise ApolloAPIError(
            message,
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def verify_apollo_credentials(auth_headers: dict[str, str]) -> bool:
    """Lightweight health probe for OAuth bearer or API key."""
    try:
        if "Authorization" in auth_headers:
            _request(auth_headers, "GET", "/users/api_profile")
            return True
        api_key = auth_headers.get("X-Api-Key")
        if api_key:
            _request({"X-Api-Key": api_key}, "POST", "/mixed_people/api_search", params={"per_page": 1})
            return True
        return False
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
    if generic_oauth_configured(settings, "apollo", environment_name):
        tokens = load_oauth_tokens(client, connector_id, settings)
        if tokens and tokens.get("access_token"):
            return generic_connection_auth_status(
                client,
                org_id,
                connector_id,
                settings,
                vendor="apollo",
                environment_name=environment_name,
            )
        if _connector_auth_type(client, org_id, connector_id) == "oauth":
            return generic_connection_auth_status(
                client,
                org_id,
                connector_id,
                settings,
                vendor="apollo",
                environment_name=environment_name,
            )

    try:
        cid, headers = resolve_apollo_connector(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
        _ = cid
        return "connected" if verify_apollo_credentials(headers) else "auth_expired"
    except ApolloAPIError as exc:
        if exc.status_code in {401, 403, 404}:
            return "auth_expired" if exc.status_code != 404 else "misconfigured"
        return "misconfigured"


def search_people(
    auth_headers: dict[str, str],
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _request(auth_headers, "POST", "/mixed_people/api_search", params=params or {})


def search_organizations(
    auth_headers: dict[str, str],
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _request(auth_headers, "POST", "/mixed_companies/search", params=params or {})


def get_contact(auth_headers: dict[str, str], contact_id: str) -> dict[str, Any]:
    if not contact_id:
        raise ApolloAPIError("contact_id is required")
    return _request(auth_headers, "GET", f"/contacts/{contact_id}")


def create_contact(auth_headers: dict[str, str], *, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ApolloAPIError("contact payload is required")
    return _request(auth_headers, "POST", "/contacts", json_body=payload)


def list_labels(auth_headers: dict[str, str]) -> dict[str, Any]:
    """List Apollo labels (contact/account lists)."""
    return _request(auth_headers, "GET", "/labels")


def create_label(
    auth_headers: dict[str, str],
    *,
    name: str,
    modality: str = "contacts",
) -> dict[str, Any]:
    """Create an Apollo label (contact list). Uses POST /labels.

    If Apollo returns 422 because the label already exists, return the existing
    label (idempotent create) so chat re-runs of the same name succeed.
    """
    label_name = str(name or "").strip()
    if not label_name:
        raise ApolloAPIError("label name is required")
    normalized_modality = str(modality or "contacts").strip().lower()
    if normalized_modality not in {"contacts", "accounts"}:
        raise ApolloAPIError("modality must be contacts or accounts")
    try:
        return _request(
            auth_headers,
            "POST",
            "/labels",
            json_body={"name": label_name, "modality": normalized_modality},
        )
    except ApolloAPIError as exc:
        if exc.status_code != 422:
            raise
        if not _is_duplicate_label_error(exc):
            raise
        existing = _find_existing_label(
            auth_headers,
            name=label_name,
            modality=normalized_modality,
        )
        if existing is None:
            # GET /labels often fails or omits the row (auth/pagination), but Apollo
            # already confirmed the name exists — treat as idempotent success.
            existing = {"name": label_name, "modality": normalized_modality}
        return {"label": existing, "already_existed": True}


def _is_duplicate_label_error(exc: ApolloAPIError) -> bool:
    """True when Apollo 422 means the list/label name is already taken."""
    haystacks: list[str] = [str(exc).casefold()]
    detail = exc.details
    if isinstance(detail, dict):
        for key in ("error", "message", "error_message", "detail"):
            value = detail.get(key)
            if isinstance(value, str):
                haystacks.append(value.casefold())
            elif isinstance(value, list):
                haystacks.extend(str(item).casefold() for item in value)
    elif isinstance(detail, str):
        haystacks.append(detail.casefold())
    joined = " ".join(haystacks)
    markers = (
        "already exists",
        "already been taken",
        "has already been taken",
        "duplicate",
        "name taken",
        "already taken",
    )
    return any(marker in joined for marker in markers)


def _extract_label_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("labels", "label", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict) and key == "label":
            return [value]
    return []


def _find_existing_label(
    auth_headers: dict[str, str],
    *,
    name: str,
    modality: str,
) -> dict[str, Any] | None:
    """Best-effort lookup when create returns 422 (often duplicate name)."""
    try:
        payload = list_labels(auth_headers)
    except ApolloAPIError:
        return None
    labels = _extract_label_rows(payload)
    if not labels:
        return None
    target = name.strip().casefold()
    for row in labels:
        row_name = str(row.get("name") or "").strip().casefold()
        if row_name != target:
            continue
        row_modality = str(row.get("modality") or "").strip().lower()
        if row_modality and row_modality != modality:
            continue
        return row
    return None


def add_contacts_to_sequence(
    auth_headers: dict[str, str],
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
    return _request(auth_headers, "POST", f"/emailer_campaigns/{sequence_id}/add_contact_ids", json_body=body)


def bulk_enrich_people(auth_headers: dict[str, str], *, details: list[dict[str, Any]]) -> dict[str, Any]:
    if not details:
        raise ApolloAPIError("details[] is required")
    return _request(auth_headers, "POST", "/people/bulk_match", json_body={"details": details})


def create_task(auth_headers: dict[str, str], *, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ApolloAPIError("task payload is required")
    return _request(auth_headers, "POST", "/tasks", json_body=payload)


def subscribe_intent_signals(auth_headers: dict[str, str], *, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ApolloAPIError("signal subscription payload is required")
    return _request(auth_headers, "POST", "/intent_signals/search", json_body=payload)


def update_contact(auth_headers: dict[str, str], contact_id: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    if not contact_id:
        raise ApolloAPIError("contact_id is required")
    if not payload:
        raise ApolloAPIError("contact payload is required")
    return _request(auth_headers, "PATCH", f"/contacts/{contact_id}", json_body=payload)


def delete_contact(auth_headers: dict[str, str], contact_id: str) -> dict[str, Any]:
    if not contact_id:
        raise ApolloAPIError("contact_id is required")
    return _request(auth_headers, "DELETE", f"/contacts/{contact_id}")


def remove_contacts_from_sequence(
    auth_headers: dict[str, str],
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
    return _request(auth_headers, "POST", "/emailer_campaigns/remove_or_stop_contact_ids", params=params)


def verify_apollo_api_key(api_key: str) -> bool:
    """Legacy API-key probe."""
    return verify_apollo_credentials({"X-Api-Key": api_key})
