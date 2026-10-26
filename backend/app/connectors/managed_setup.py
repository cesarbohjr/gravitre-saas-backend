"""Server-side provider readiness. API keys alone do not make a provider ready."""
from __future__ import annotations

import hashlib
import time
from threading import Lock
from typing import Any

import httpx

from app.connectors.nango_client import _auth_headers, _base_url, nango_configured

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_lock = Lock()


def integration_inventory(settings: Any, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return only allowlisted configuration metadata, never OAuth credentials."""
    key = hashlib.sha256((_base_url(settings) + settings.nango_secret_key).encode()).hexdigest()
    with _lock:
        cached = _cache.get(key)
        if not force_refresh and cached and time.monotonic() - cached[0] < 30:
            return cached[1]
    with httpx.Client(timeout=15) as client:
        response = client.get(f"{_base_url(settings)}/integrations", headers=_auth_headers(settings))
        response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ValueError("Invalid managed integration inventory")
    rows = [{"key": item.get("unique_key"), "provider": item.get("provider"),
             "missing_fields": item.get("missing_fields")} for item in body["data"] if isinstance(item, dict)]
    with _lock:
        if len(_cache) >= 16:
            _cache.clear()
        _cache[key] = (time.monotonic(), rows)
    return rows


def provider_readiness(spec: Any, inventory: list[dict[str, Any]]) -> tuple[bool, str | None]:
    if not spec.provider:
        return False, "provider_not_supported"
    # Interactive account consent only: client-credentials is not user OAuth.
    if spec.auth_mode not in {"OAUTH1", "OAUTH2", "API_KEY"}:
        return False, "interactive_oauth_unavailable"
    integration = next((r for r in inventory if r["key"] == spec.integration_id), None)
    if not integration:
        return False, "integration_missing"
    if integration["provider"] != spec.provider:
        return False, "provider_mismatch"
    if integration["missing_fields"] != []:
        return False, "provider_credentials_required"
    return True, None


def managed_setup_catalog(settings: Any) -> dict[str, Any]:
    from app.connectors.managed_oauth_inputs import oauth_input_fields
    from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY, NANGO_FALLBACK_REGISTRY
    from app.services.managed_service_desk_tools import MANAGED_SERVICE_DESK_TOOL_EXECUTORS
    from app.services.managed_security_tools import MANAGED_SECURITY_TOOL_EXECUTORS
    from app.services.managed_business_tools import MANAGED_BUSINESS_TOOL_EXECUTORS

    configured = nango_configured(settings) and bool(settings.nango_webhook_signing_key.strip())
    inventory: list[dict[str, Any]] = []
    failure = "platform_not_configured"
    if configured:
        try:
            inventory = integration_inventory(settings)
            failure = ""
        except (httpx.HTTPError, ValueError):
            failure = "setup_check_unavailable"
    actions = set(MANAGED_SERVICE_DESK_TOOL_EXECUTORS) | set(MANAGED_SECURITY_TOOL_EXECUTORS) | set(MANAGED_BUSINESS_TOOL_EXECUTORS)
    connectors = []
    for spec in (*NANGO_CONNECTOR_REGISTRY.values(), *NANGO_FALLBACK_REGISTRY.values()):
        available, reason = (False, failure) if failure else provider_readiness(spec, inventory)
        supported = sorted(a for a in actions if a.startswith(spec.vendor + "."))
        connectors.append({"vendor": spec.vendor, "available": available, "setupReason": reason,
                           "nativeFallback": spec.native_fallback, "authMode": spec.auth_mode,
                           "inputFields": oauth_input_fields(spec.vendor),
                           "actions": supported, "support": "native_actions" if spec.native_fallback else
                           "actions_supported" if supported else "authorization_only"})
    return {"configured": configured, "inventoryChecked": not bool(failure), "connectors": connectors}
