"""Stripe API client for org connectors (STA-35).

Distinct from platform billing in `app.billing.stripe` — never uses
`settings.stripe_secret_key` for agent tools.
"""
from __future__ import annotations

from typing import Any

import stripe

from app.config import Settings
from app.connectors.repository import get_decrypted_secret
from app.core.crypto import decrypt_value


class StripeAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _map_stripe_error(exc: Exception) -> StripeAPIError:
    status = getattr(exc, "http_status", None)
    if isinstance(exc, stripe.error.AuthenticationError):
        return StripeAPIError(str(exc), status_code=status or 401, details=exc)
    if isinstance(exc, stripe.error.PermissionError):
        return StripeAPIError(str(exc), status_code=status or 403, details=exc)
    if isinstance(exc, stripe.error.RateLimitError):
        return StripeAPIError(str(exc), status_code=status or 429, details=exc)
    if isinstance(exc, stripe.error.InvalidRequestError):
        return StripeAPIError(str(exc), status_code=status or 400, details=exc)
    return StripeAPIError(str(exc), status_code=status, details=exc)


def resolve_stripe_credentials(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> tuple[str, str | None]:
    """Return (secret_api_key, optional connected account id for Stripe-Account header)."""
    row = (
        client.table("connectors")
        .select("id, org_id, type, config, api_key_encrypted")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise StripeAPIError("Connector not found", status_code=404)
    connector = dict(row.data[0])
    if str(connector.get("type") or "").lower() != "stripe":
        raise StripeAPIError("Not a Stripe connector", status_code=400)

    config = connector.get("config") or {}
    stripe_account = (
        config.get("stripe_account_id")
        or config.get("connected_account_id")
        or config.get("account_id")
    )
    stripe_account = str(stripe_account).strip() if stripe_account else None

    for key_name in ("secret_key", "api_key", "stripe_secret_key"):
        value = get_decrypted_secret(client, connector_id, key_name, settings)
        if value and value.strip():
            return value.strip(), stripe_account

    encrypted = connector.get("api_key_encrypted")
    if encrypted and (settings.encryption_key or "").strip():
        try:
            legacy = decrypt_value(encrypted, settings.encryption_key)
            if legacy and legacy.strip():
                return legacy.strip(), stripe_account
        except Exception:
            pass

    raise StripeAPIError(
        "Stripe secret key not configured on connector",
        status_code=401,
    )


def list_invoices(
    api_key: str,
    *,
    stripe_account: str | None = None,
    customer_id: str | None = None,
    status: str | None = None,
    limit: int = 10,
    starting_after: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": max(1, min(int(limit), 100))}
    if customer_id:
        params["customer"] = customer_id
    if status:
        params["status"] = status
    if starting_after:
        params["starting_after"] = starting_after
    try:
        result = stripe.Invoice.list(
            api_key=api_key,
            stripe_account=stripe_account,
            **params,
        )
    except stripe.error.StripeError as exc:
        raise _map_stripe_error(exc) from exc
    return result.to_dict() if hasattr(result, "to_dict") else dict(result)


def get_subscription(
    api_key: str,
    subscription_id: str,
    *,
    stripe_account: str | None = None,
) -> dict[str, Any]:
    try:
        result = stripe.Subscription.retrieve(
            subscription_id,
            api_key=api_key,
            stripe_account=stripe_account,
        )
    except stripe.error.StripeError as exc:
        raise _map_stripe_error(exc) from exc
    return result.to_dict() if hasattr(result, "to_dict") else dict(result)
