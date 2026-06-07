"""Segment HTTP API client — identify / track / group (STA-68)."""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_decrypted_secret
from app.core.crypto import decrypt_value

SEGMENT_API_BASE = "https://api.segment.io/v1"
TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class SegmentAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_segment_write_key(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> str:
    row = (
        client.table("connectors")
        .select("id, org_id, type, config, api_key_encrypted")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise SegmentAPIError("Connector not found", status_code=404)
    connector = dict(row.data[0])
    if str(connector.get("type") or "").lower() != "segment":
        raise SegmentAPIError("Not a Segment connector", status_code=400)

    for key_name in ("write_key", "api_key", "segment_write_key"):
        value = get_decrypted_secret(client, connector_id, key_name, settings)
        if value and value.strip():
            return value.strip()

    encrypted = connector.get("api_key_encrypted")
    if encrypted and (settings.encryption_key or "").strip():
        try:
            legacy = decrypt_value(encrypted, settings.encryption_key)
            if legacy and legacy.strip():
                return legacy.strip()
        except Exception:
            pass

    raise SegmentAPIError(
        "Segment write key not configured on connector",
        status_code=401,
    )


def _request(
    method: str,
    path: str,
    write_key: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{SEGMENT_API_BASE}{path}"
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(
                    method,
                    url,
                    json=json_body,
                    auth=(write_key, ""),
                    headers={"Content-Type": "application/json"},
                )
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise SegmentAPIError(
                    f"Segment API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if not response.text:
                return {"success": True}
            try:
                return response.json()
            except Exception:
                return {"success": True, "body": response.text[:500]}
        except SegmentAPIError:
            raise
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise SegmentAPIError(str(exc)) from exc
    raise SegmentAPIError(str(last_error or "Segment request failed"))


def identify(write_key: str, *, user_id: str, traits: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"userId": user_id}
    if traits:
        body["traits"] = traits
    return _request("POST", "/identify", write_key, json_body=body)


def track(
    write_key: str,
    *,
    user_id: str | None = None,
    anonymous_id: str | None = None,
    event: str,
    properties: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not user_id and not anonymous_id:
        raise SegmentAPIError("user_id or anonymous_id required")
    body: dict[str, Any] = {"event": event}
    if user_id:
        body["userId"] = user_id
    if anonymous_id:
        body["anonymousId"] = anonymous_id
    if properties:
        body["properties"] = properties
    if context:
        body["context"] = context
    return _request("POST", "/track", write_key, json_body=body)


def group(
    write_key: str,
    *,
    user_id: str,
    group_id: str,
    traits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"userId": user_id, "groupId": group_id}
    if traits:
        body["traits"] = traits
    return _request("POST", "/group", write_key, json_body=body)
