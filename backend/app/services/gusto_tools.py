"""Gusto HR H3 read tools — demo-first (api.gusto-demo.com).

Default env is Gusto Demo. Production api.gusto.com requires separate sign-off.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolConnectorNotConnectedError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

GUSTO_DEMO_BASE = "https://api.gusto-demo.com/v1"
GUSTO_PRODUCTION_BASE = "https://api.gusto.com/v1"
TIMEOUT_SEC = 45.0

GUSTO_PARTNER_MSG = (
    "Gusto requires partner OAuth connection — request partner approval and connect "
    "Gusto from Connectors before invoking payroll/HRIS reads"
)


def resolve_gusto_api_base(
    *,
    settings: Any | None = None,
    connector_config: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (api_base, env_name). Defaults to demo — never silent production."""
    cfg = connector_config if isinstance(connector_config, dict) else {}
    p = params if isinstance(params, dict) else {}
    raw = (
        p.get("gusto_env")
        or p.get("env")
        or cfg.get("gusto_env")
        or cfg.get("env")
        or cfg.get("environment")
        or getattr(settings, "gusto_env", None)
        or "demo"
    )
    env_name = str(raw).strip().lower() or "demo"
    if env_name in {"production", "prod"}:
        return GUSTO_PRODUCTION_BASE, "production"
    return GUSTO_DEMO_BASE, "demo"


def _handle_http(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        msg = (exc.response.text or str(exc))[:500]
        if code == 429:
            return ToolRateLimitedError(msg)
        if code in {401, 403}:
            return ToolAuthExpiredError(msg)
        return ToolValidationError(msg)
    return ToolValidationError(str(exc))


def _resolve_gusto_session(
    ctx: ToolContext, params: dict[str, Any]
) -> tuple[str, str, str, str]:
    """Return (connector_id, token, api_base, gusto_env)."""
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
            ctx.client, ctx.org_id, "gusto", environment_name=ctx.environment_name
        )
    if not conn:
        raise ToolConnectorNotConnectedError(GUSTO_PARTNER_MSG)
    cid = str(conn["id"])
    status = str(conn.get("status") or "").lower()
    if status in {"needs_connection", "inactive", "disconnected", "pending"}:
        raise ToolConnectorNotConnectedError(GUSTO_PARTNER_MSG)
    token = (
        get_decrypted_secret(ctx.client, cid, "access_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "oauth_access_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "api_token", ctx.settings)
    )
    if not token:
        raise ToolConnectorNotConnectedError(GUSTO_PARTNER_MSG)
    conn_cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    api_base, gusto_env = resolve_gusto_api_base(
        settings=ctx.settings, connector_config=conn_cfg, params=params
    )
    enforce_rate_limit(ctx.client, ctx.org_id, "gusto", "gusto", cid)
    return cid, token.strip(), api_base, gusto_env


def _gusto_get(api_base: str, token: str, path: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/{path.lstrip('/')}"
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-Gusto-API-Version": "2024-04-01",
            },
        )
    if response.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"Gusto API {response.status_code}",
            request=response.request,
            response=response,
        )
    data = response.json()
    return data if isinstance(data, dict) else {"value": data}


def _exec_companies_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    try:
        cid, token, api_base, gusto_env = _resolve_gusto_session(ctx, params)
        company_id = str(params.get("company_id") or params.get("id") or "").strip()
        if company_id:
            data = _gusto_get(api_base, token, f"companies/{company_id}")
        else:
            # Token-scoped company listing / current company depending on partner app.
            data = _gusto_get(api_base, token, "companies")
    except (ToolValidationError, ToolConnectorNotConnectedError, ToolAuthExpiredError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise _handle_http(exc) from exc
    return NormalizedResult(
        success=True,
        action="gusto.companies.get",
        connector_id=cid,
        data={
            "company": data,
            "api_base": api_base,
            "gusto_env": gusto_env,
            "summary": f"Fetched Gusto company data via {gusto_env}",
        },
    )


def _exec_employees_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    try:
        cid, token, api_base, gusto_env = _resolve_gusto_session(ctx, params)
        employee_id = str(params.get("employee_id") or params.get("id") or "").strip()
        if not employee_id:
            raise ToolValidationError("gusto.employees.get requires employee_id")
        data = _gusto_get(api_base, token, f"employees/{employee_id}")
    except (ToolValidationError, ToolConnectorNotConnectedError, ToolAuthExpiredError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise _handle_http(exc) from exc
    return NormalizedResult(
        success=True,
        action="gusto.employees.get",
        connector_id=cid,
        data={
            "employee": data,
            "api_base": api_base,
            "gusto_env": gusto_env,
            "summary": f"Fetched Gusto employee {employee_id} via {gusto_env}",
        },
    )


def _exec_payrolls_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    try:
        cid, token, api_base, gusto_env = _resolve_gusto_session(ctx, params)
        company_id = str(params.get("company_id") or params.get("id") or "").strip()
        if not company_id:
            raise ToolValidationError("gusto.payrolls.list requires company_id")
        data = _gusto_get(api_base, token, f"companies/{company_id}/payrolls")
    except (ToolValidationError, ToolConnectorNotConnectedError, ToolAuthExpiredError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise _handle_http(exc) from exc
    return NormalizedResult(
        success=True,
        action="gusto.payrolls.list",
        connector_id=cid,
        data={
            "payrolls": data,
            "api_base": api_base,
            "gusto_env": gusto_env,
            "summary": f"Listed Gusto payrolls for company {company_id} via {gusto_env}",
        },
    )


GUSTO_TOOL_EXECUTORS: dict[str, Any] = {
    "gusto.companies.get": _exec_companies_get,
    "gusto.employees.get": _exec_employees_get,
    "gusto.payrolls.list": _exec_payrolls_list,
}
