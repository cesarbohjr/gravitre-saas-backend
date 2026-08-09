"""Twilio REST executor — real Accounts/{Sid}/Calls|Messages paths + Basic auth.

External telephony (inbound/outbound call-center). Distinct from internal
staff voice mode (Deepgram/ElevenLabs chat modality).
"""
from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlencode

import httpx

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolConnectorNotConnectedError,
    ToolContext,
    ToolValidationError,
)

BASE = "https://api.twilio.com/2010-04-01"
TIMEOUT_SEC = 30.0

# Canonical Twilio REST routes (2026) — not the generic catalog_http pluralizer.
_ROUTES: dict[str, tuple[str, str]] = {
    "twilio.accounts.get": ("GET", "/Accounts/{account_sid}.json"),
    "twilio.calls.list": ("GET", "/Accounts/{account_sid}/Calls.json"),
    "twilio.calls.get": ("GET", "/Accounts/{account_sid}/Calls/{call_sid}.json"),
    "twilio.calls.create": ("POST", "/Accounts/{account_sid}/Calls.json"),
    "twilio.messages.list": ("GET", "/Accounts/{account_sid}/Messages.json"),
    "twilio.messages.get": ("GET", "/Accounts/{account_sid}/Messages/{message_sid}.json"),
    "twilio.messages.create": ("POST", "/Accounts/{account_sid}/Messages.json"),
}


def _account_sid(conn: dict[str, Any], ctx: ToolContext, cid: str) -> str:
    cfg = conn.get("config") or {}
    sid = str(cfg.get("account_sid") or cfg.get("AccountSid") or "").strip()
    if not sid:
        sid = (get_decrypted_secret(ctx.client, cid, "account_sid", ctx.settings) or "").strip()
    if not sid:
        raise ToolValidationError("Twilio account_sid is required on the connector")
    return sid


def _auth_header(ctx: ToolContext, cid: str, account_sid: str) -> str:
    token = (
        get_decrypted_secret(ctx.client, cid, "auth_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "api_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "token", ctx.settings)
        or ""
    ).strip()
    if not token:
        raise ToolAuthExpiredError("Twilio auth_token not configured")
    raw = f"{account_sid}:{token}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _resolve_connector(ctx: ToolContext, params: dict[str, Any]) -> dict[str, Any]:
    connector_id = params.get("connector_id") or ctx.connector_id
    if connector_id:
        conn = get_connector(
            ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name
        )
    else:
        conn = get_connector_by_type(
            ctx.client, ctx.org_id, "twilio", environment_name=ctx.environment_name
        )
    if not conn:
        raise ToolConnectorNotConnectedError("No active Twilio connector")
    return conn


def make_twilio_executor(action: str):
    if action not in _ROUTES:
        raise ValueError(f"Unsupported Twilio action: {action}")
    method, path_template = _ROUTES[action]

    def _exec(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
        conn = _resolve_connector(ctx, params)
        cid = str(conn["id"])
        enforce_rate_limit(ctx.client, ctx.org_id, "twilio", "twilio", cid)
        account_sid = _account_sid(conn, ctx, cid)
        path = path_template.format(
            account_sid=account_sid,
            call_sid=str(params.get("call_sid") or params.get("CallSid") or ""),
            message_sid=str(params.get("message_sid") or params.get("MessageSid") or ""),
        )
        if "{call_sid}" in path_template and not params.get("call_sid") and not params.get("CallSid"):
            raise ToolValidationError("call_sid is required")
        if "{message_sid}" in path_template and not params.get("message_sid") and not params.get(
            "MessageSid"
        ):
            raise ToolValidationError("message_sid is required")

        url = f"{BASE}{path}"
        headers = {
            "Authorization": _auth_header(ctx, cid, account_sid),
            "Accept": "application/json",
        }
        # Twilio Create uses form-urlencoded; GETs use query params.
        form_keys = {
            "To",
            "From",
            "Url",
            "Twiml",
            "StatusCallback",
            "StatusCallbackEvent",
            "StatusCallbackMethod",
            "Timeout",
            "Record",
            "Body",
            "MediaUrl",
            "MessagingServiceSid",
        }
        form: dict[str, Any] = {}
        for key in form_keys:
            # Accept snake_case from catalog params.
            snake = "".join(["_" + c.lower() if c.isupper() else c for c in key]).lstrip("_")
            val = params.get(key)
            if val is None:
                val = params.get(snake)
            if val is not None:
                form[key] = val

        query = {}
        for k in ("PageSize", "Status", "To", "From", "page_size", "status"):
            if params.get(k) is not None:
                query["PageSize" if k == "page_size" else ("Status" if k == "status" else k)] = (
                    params[k]
                )

        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            if method == "GET":
                response = client.get(url, headers=headers, params=query or None)
            else:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                response = client.post(url, headers=headers, content=urlencode(form))

        if response.status_code >= 400:
            raise ToolValidationError(
                f"{action} failed ({response.status_code}): {response.text[:500]}"
            )
        data: Any = {}
        if response.text:
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text[:2000]}
        payload = data if isinstance(data, dict) else {"result": data}

        # Verified-output fields for F6-style completion tracking.
        if action == "twilio.calls.create":
            sid = payload.get("sid") or payload.get("Sid")
            if not sid:
                raise ToolValidationError("Twilio call create returned no Call SID")
            payload["entity_id"] = sid
            payload["call_sid"] = sid
            payload["call_status"] = payload.get("status") or payload.get("Status")
            payload["outcome_effect"] = "created"
        if action == "twilio.messages.create":
            sid = payload.get("sid") or payload.get("MessageSid")
            if not sid:
                raise ToolValidationError("Twilio message create returned no Message SID")
            payload["entity_id"] = sid
            payload["message_sid"] = sid
            payload["outcome_effect"] = "created"
        if action in {"twilio.calls.get", "twilio.messages.get"}:
            payload["entity_id"] = payload.get("sid")
            payload["verified_status"] = payload.get("status")

        return NormalizedResult(success=True, action=action, connector_id=cid, data=payload)

    return _exec
