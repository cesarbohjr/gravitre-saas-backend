"""Customer SIEM export — signed webhook delivery (STA-83)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.compliance_service import redact_metadata

logger = logging.getLogger(__name__)


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_siem_event(
    *,
    org_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any] | None = None,
    pii_mode: str = "strict",
) -> dict[str, Any]:
    return {
        "orgId": org_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "resourceType": resource_type,
        "resourceId": resource_id,
        "metadata": redact_metadata(metadata or {}, mode=pii_mode),
    }


def dispatch_siem_event(
    *,
    endpoint: str,
    secret: str,
    event: dict[str, Any],
    timeout_seconds: float = 10.0,
    max_retries: int = 2,
) -> dict[str, Any]:
    body = json.dumps(event, separators=(",", ":"), default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Gravitre-Signature": sign_payload(secret, body),
        "X-Gravitre-Timestamp": str(int(time.time())),
    }
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(endpoint, content=body, headers=headers)
            if response.status_code >= 500 and attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            return {
                "delivered": 200 <= response.status_code < 300,
                "statusCode": response.status_code,
                "attempt": attempt + 1,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
                continue
    logger.warning("siem_export_failed endpoint=%s error=%s", endpoint, last_error)
    return {"delivered": False, "error": last_error or "delivery_failed", "attempt": max_retries + 1}
