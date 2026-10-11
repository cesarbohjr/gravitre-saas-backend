"""Best-effort provider-side token revocation when a connector is disconnected (Phase 2B).

Deleting our copy of a token stops Gravitre from using it, but the grant stays
alive at the provider until it expires. Where the provider offers a revoke
endpoint we call it before the stored tokens are dropped.

Never raises: disconnect must succeed even when the provider is down. Every call
returns a ``RevokeOutcome`` that the caller records in the audit trail.

Off unless CONNECTOR_PROVIDER_REVOKE_ON_DISCONNECT is true.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

REVOKE_TIMEOUT_SECONDS = 5.0

GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
HUBSPOT_REFRESH_TOKEN_URL = "https://api.hubapi.com/oauth/v1/refresh-tokens/{token}"
SLACK_REVOKE_URL = "https://slack.com/api/auth.revoke"
SALESFORCE_DEFAULT_LOGIN = "https://login.salesforce.com"

GOOGLE_FAMILY = frozenset(
    {
        "google_analytics",
        "google_calendar",
        "gmail",
        "google_drive",
        "google_docs",
        "google_sheets",
        "google_search_console",
        "google_ads",
    }
)

SUPPORTED_VENDORS = GOOGLE_FAMILY | {"hubspot", "slack", "salesforce"}


@dataclass(frozen=True)
class RevokeOutcome:
    status: str  # revoked | not_supported | no_token | skipped_shared_grant | failed | disabled
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"status": self.status, "detail": self.detail}


def canonical_vendor(vendor: str | None) -> str:
    v = str(vendor or "").strip().lower()
    if v in GOOGLE_FAMILY:
        return v
    try:
        from app.connectors.google_vendor_oauth import normalize_google_vendor

        g = normalize_google_vendor(v)
        if g:
            return g
    except Exception as exc:  # noqa: BLE001
        logger.debug("provider_revoke_vendor_alias_failed vendor=%s error=%s", v, exc)
    return v


def _post(http: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    return http.post(url, **kwargs)


def revoke_provider_tokens(
    vendor: str | None,
    tokens: dict[str, Any] | None,
    *,
    config: dict[str, Any] | None = None,
    shares_grant_with_live_connector: bool = False,
    http: httpx.Client | None = None,
) -> RevokeOutcome:
    """Revoke ``tokens`` at the provider for ``vendor``.

    ``shares_grant_with_live_connector``: Google revokes the whole user grant for
    our OAuth client, which would also break every other live Google connector
    in the org, so the caller passes True when one exists and nothing is sent.
    """
    v = canonical_vendor(vendor)
    if v not in SUPPORTED_VENDORS:
        return RevokeOutcome("not_supported", v or "unknown")
    tokens = tokens or {}
    refresh = str(tokens.get("refresh_token") or "").strip()
    access = str(tokens.get("access_token") or "").strip()
    if not refresh and not access:
        return RevokeOutcome("no_token", v)
    if v in GOOGLE_FAMILY and shares_grant_with_live_connector:
        return RevokeOutcome("skipped_shared_grant", v)

    owns_http = http is None
    http = http or httpx.Client(timeout=REVOKE_TIMEOUT_SECONDS)
    try:
        if v in GOOGLE_FAMILY:
            resp = _post(
                http,
                GOOGLE_REVOKE_URL,
                data={"token": refresh or access},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            # 400 invalid_token means it is already revoked or expired.
            if resp.status_code == 200 or (resp.status_code == 400 and "invalid_token" in resp.text):
                return RevokeOutcome("revoked", v)
            return RevokeOutcome("failed", f"{v} http {resp.status_code}")
        if v == "hubspot":
            if not refresh:
                return RevokeOutcome("no_token", v)
            resp = http.delete(HUBSPOT_REFRESH_TOKEN_URL.format(token=refresh))
            if resp.status_code in (200, 204, 404):
                return RevokeOutcome("revoked", v)
            return RevokeOutcome("failed", f"{v} http {resp.status_code}")
        if v == "slack":
            token = access or refresh
            resp = _post(http, SLACK_REVOKE_URL, headers={"Authorization": f"Bearer {token}"})
            body: dict[str, Any] = {}
            try:
                body = resp.json() if resp.content else {}
            except ValueError:
                body = {}
            if resp.status_code == 200 and (
                body.get("ok") is True or body.get("error") in {"invalid_auth", "token_revoked", "account_inactive"}
            ):
                return RevokeOutcome("revoked", v)
            return RevokeOutcome("failed", f"{v} http {resp.status_code} {body.get('error') or ''}".strip())
        if v == "salesforce":
            base = str((config or {}).get("instance_url") or tokens.get("instance_url") or SALESFORCE_DEFAULT_LOGIN)
            resp = _post(
                http,
                base.rstrip("/") + "/services/oauth2/revoke",
                data={"token": refresh or access},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            # 400 invalid_token means it is already revoked or expired.
            if resp.status_code == 200 or (resp.status_code == 400 and "invalid_token" in resp.text):
                return RevokeOutcome("revoked", v)
            return RevokeOutcome("failed", f"{v} http {resp.status_code}")
    except httpx.HTTPError as exc:
        logger.warning("provider_revoke_failed vendor=%s error=%s", v, type(exc).__name__)
        return RevokeOutcome("failed", f"{v} {type(exc).__name__}")
    finally:
        if owns_http:
            http.close()
    return RevokeOutcome("not_supported", v)
