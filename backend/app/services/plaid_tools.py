"""Plaid read stubs (Finance F3 — if entitled).

Connect path is Plaid Link public_token exchange (see plaid_link.py), not generic OAuth.
Keep vendor shipped=False until a full connect UI path is wired; executors still register
so pack tips fail closed with a clear message when no access_token is stored.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

PLAID_SANDBOX_BASE = "https://sandbox.plaid.com"
PLAID_PRODUCTION_BASE = "https://production.plaid.com"
# Legacy alias — prefer resolve_plaid_api_base().
PLAID_API_BASE = PLAID_SANDBOX_BASE
TIMEOUT_SEC = 45.0


class PlaidAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def resolve_plaid_api_base(
    *,
    settings: Any | None = None,
    connector_config: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (api_base, env_name). Defaults to sandbox — never silent production."""
    cfg = connector_config if isinstance(connector_config, dict) else {}
    p = params if isinstance(params, dict) else {}
    raw = (
        p.get("plaid_env")
        or p.get("env")
        or cfg.get("plaid_env")
        or cfg.get("env")
        or cfg.get("environment")
        or getattr(settings, "plaid_env", None)
        or "sandbox"
    )
    env_name = str(raw).strip().lower() or "sandbox"
    if env_name in {"production", "prod"}:
        return PLAID_PRODUCTION_BASE, "production"
    return PLAID_SANDBOX_BASE, "sandbox"


def _handle_http(exc: Exception) -> Exception:
    if isinstance(exc, PlaidAPIError):
        if exc.status_code == 429:
            return ToolRateLimitedError(str(exc))
        if exc.status_code in {401, 403}:
            return ToolAuthExpiredError(str(exc))
        return ToolValidationError(str(exc))
    return ToolValidationError(str(exc))


def _resolve_plaid_access(
    ctx: ToolContext, params: dict[str, Any]
) -> tuple[str, str, str | None, str | None, str, str]:
    """Return (connector_id, access_token, client_id, secret, api_base, plaid_env)."""
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(
            ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name
        )
    else:
        conn = get_connector_by_type(
            ctx.client, ctx.org_id, "plaid", environment_name=ctx.environment_name
        )
    if not conn:
        raise ToolValidationError(
            "Plaid not connected / exchange public_token first "
            "(Plaid Link — not generic OAuth; see docs/connectors plaid_link)"
        )
    cid = str(conn["id"])
    access_token = (
        get_decrypted_secret(ctx.client, cid, "access_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "plaid_access_token", ctx.settings)
    )
    if not access_token:
        raise ToolValidationError(
            "Plaid not connected / exchange public_token first "
            "(no access_token on connector — complete Plaid Link exchange)"
        )
    client_id = get_decrypted_secret(ctx.client, cid, "client_id", ctx.settings) or getattr(
        ctx.settings, "plaid_client_id", None
    )
    secret = get_decrypted_secret(ctx.client, cid, "secret", ctx.settings) or getattr(
        ctx.settings, "plaid_secret", None
    )
    conn_cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    api_base, plaid_env = resolve_plaid_api_base(
        settings=ctx.settings, connector_config=conn_cfg, params=params
    )
    enforce_rate_limit(ctx.client, ctx.org_id, "plaid", "plaid", cid)
    return (
        cid,
        access_token.strip(),
        (str(client_id).strip() if client_id else None),
        (str(secret).strip() if secret else None),
        api_base,
        plaid_env,
    )


def _plaid_post(
    path: str,
    *,
    access_token: str,
    client_id: str | None,
    secret: str | None,
    api_base: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not client_id or not secret:
        raise ToolValidationError(
            "Plaid client_id/secret missing — set platform PLAID_CLIENT_ID/PLAID_SECRET "
            "or store on the connector (if entitled)"
        )
    body: dict[str, Any] = {
        "client_id": client_id,
        "secret": secret,
        "access_token": access_token,
    }
    if extra:
        body.update(extra)
    url = f"{api_base.rstrip('/')}{path}"
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.post(url, json=body, headers={"Content-Type": "application/json"})
    if response.status_code >= 400:
        raise PlaidAPIError(
            (response.text or f"Plaid API error {response.status_code}")[:500],
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        raise PlaidAPIError("Invalid JSON from Plaid", status_code=502) from exc
    return data if isinstance(data, dict) else {"value": data}


def _exec_accounts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    try:
        cid, access_token, client_id, secret, api_base, plaid_env = _resolve_plaid_access(
            ctx, params
        )
        data = _plaid_post(
            "/accounts/get",
            access_token=access_token,
            client_id=client_id,
            secret=secret,
            api_base=api_base,
        )
    except ToolValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _handle_http(exc) from exc
    return NormalizedResult(
        success=True,
        action="plaid.accounts.get",
        connector_id=cid,
        data={**data, "api_base": api_base, "plaid_env": plaid_env},
    )


def _exec_balances_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    try:
        cid, access_token, client_id, secret, api_base, plaid_env = _resolve_plaid_access(
            ctx, params
        )
        data = _plaid_post(
            "/accounts/balance/get",
            access_token=access_token,
            client_id=client_id,
            secret=secret,
            api_base=api_base,
        )
    except ToolValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _handle_http(exc) from exc
    return NormalizedResult(
        success=True,
        action="plaid.balances.get",
        connector_id=cid,
        data={**data, "api_base": api_base, "plaid_env": plaid_env},
    )


def _exec_transactions_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    try:
        cid, access_token, client_id, secret, api_base, plaid_env = _resolve_plaid_access(
            ctx, params
        )
        start = str(params.get("start_date") or params.get("startDate") or "2024-01-01").strip()
        end = str(params.get("end_date") or params.get("endDate") or "2026-12-31").strip()
        data = _plaid_post(
            "/transactions/get",
            access_token=access_token,
            client_id=client_id,
            secret=secret,
            api_base=api_base,
            extra={"start_date": start, "end_date": end},
        )
    except ToolValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _handle_http(exc) from exc
    return NormalizedResult(
        success=True,
        action="plaid.transactions.list",
        connector_id=cid,
        data={**data, "api_base": api_base, "plaid_env": plaid_env},
    )


PLAID_TOOL_EXECUTORS: dict[str, Any] = {
    "plaid.accounts.get": _exec_accounts_get,
    "plaid.balances.get": _exec_balances_get,
    "plaid.transactions.list": _exec_transactions_list,
}
