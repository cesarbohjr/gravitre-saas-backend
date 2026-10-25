"""Executable read-only prospecting provider adapters.

No browser scraping or arbitrary outbound URLs. Requires tenant-scoped connector
credentials and a pre-authorized credit budget; never performs CRM writes.
"""
from __future__ import annotations

from typing import Any
from datetime import date
import httpx

from app.connectors.repository import get_connector, get_decrypted_secret
from app.services.tool_types import NormalizedResult, ToolContext

ENDPOINTS = {
    "hunter.email.verify": ("GET", "https://api.hunter.io/v2/email-verifier"),
    "emailable.email.verify": ("GET", "https://api.emailable.com/v1/verify"),
    "apollo.people.search": ("POST", "https://api.apollo.io/api/v1/mixed_people/api_search"),
    "apollo.people.match": ("POST", "https://api.apollo.io/api/v1/people/match"),
    "millionverifier.email.verify": ("GET", "https://api.millionverifier.com/api/v3/"),
}
CREDIT_ACTIONS = set(ENDPOINTS)  # Treat all provider calls as metered until plan terms are verified.
ALLOWED_TYPES = {"hunter", "emailable", "apollo", "snov", "millionverifier"}


def execute_prospecting_action(ctx: ToolContext, action: str, params: dict[str, Any]) -> NormalizedResult:
    connector_id = str(params.get("connector_id") or ctx.connector_id or "")
    vendor = action.split(".", 1)[0]
    def fail(code: str, message: str) -> NormalizedResult:
        return NormalizedResult(success=False, action=action, connector_id=connector_id,
                                error_code=code, error_message=message)
    if action not in ENDPOINTS or vendor not in ALLOWED_TYPES:
        return fail("action_not_found", "Provider action has no vetted executable adapter")
    if not connector_id or not ctx.org_id:
        return fail("connector_not_connected", "Tenant-scoped connector is required")
    connector = get_connector(ctx.client, ctx.org_id, connector_id, ctx.environment_name)
    if not connector or str(connector.get("type")) != vendor:
        return fail("connector_not_connected", "Connected provider does not match requested action")
    if str(connector.get("status")) not in {"active", "healthy", "connected", "syncing"}:
        return fail("connector_not_connected", "Provider connector is not active")
    config = connector.get("config") or {}
    if not isinstance(config, dict) or not config.get("prospecting_enabled", False):
        return fail("permission_denied", "Prospecting connector not enabled")
    if action in CREDIT_ACTIONS and not (config.get("credits_confirmed") and config.get("credit_budget_approved") and config.get("remaining_free_credits", 0) > 0):
        return fail("permission_denied", "Credit-consuming action requires confirmed unused allowance and approval")
    allowed_params = {
        "hunter.email.verify": ("email",),
        "emailable.email.verify": ("email",),
        "millionverifier.email.verify": ("email",),
        "apollo.people.search": ("q_keywords", "person_titles", "person_locations", "organization_locations", "per_page", "page"),
        "apollo.people.match": ("first_name", "last_name", "organization_name", "domain", "email"),
    }[action]
    payload = {k:params[k] for k in allowed_params if k in params and params[k] is not None}
    if action.endswith("email.verify"):
        email = str(payload.get("email") or "").strip()
        if len(email)>254 or "@" not in email:
            return fail("validation_error", "Business email required")
    if action == "apollo.people.search":
        try:
            payload["per_page"] = max(1, min(25, int(payload.get("per_page") or 10)))
        except (TypeError, ValueError):
            return fail("validation_error", "Invalid requested page size")
    key = get_decrypted_secret(ctx.client, connector_id, "api_key", ctx.settings, org_id=ctx.org_id)
    if not key:
        return fail("connector_not_connected", "Provider API key not configured")

    reservation_id = str(params.get("request_id") or "").strip()
    if action in CREDIT_ACTIONS and not reservation_id:
        return fail("validation_error", "Stable request_id is required for metered calls")
    if action in CREDIT_ACTIONS:
        try:
            result = ctx.client.rpc("prospect_reserve_credits", {
                "p_org":ctx.org_id,"p_provider":vendor,
                "p_period":str(config.get("credit_period") or date.today().replace(day=1).isoformat()),
                "p_request":reservation_id,"p_cost":1
            }).execute()
            if result.data is not True:
                return fail("permission_denied","Credit budget exhausted or unavailable")
        except Exception:
            return fail("permission_denied","Credit reservation unavailable")
    def settle(consumed: int, state: str) -> None:
        if action in CREDIT_ACTIONS:
            ctx.client.rpc("prospect_settle_credits", {
                "p_org":ctx.org_id,"p_provider":vendor,"p_request":reservation_id,
                "p_consumed":consumed,"p_status":state
            }).execute()
    method,url = ENDPOINTS[action]
    headers={"Accept":"application/json"}
    if vendor == "hunter":
        headers["Authorization"] = "Bearer "+key
    elif vendor == "emailable":
        headers["Authorization"] = "Bearer "+key
    elif vendor == "apollo":
        headers["X-Api-Key"] = key
    else:
        payload["key"] = key
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            response = client.request(method,url,headers=headers,
                                      params=payload if method=="GET" else None,
                                      json=payload if method=="POST" else None)
        if response.status_code in (401,403):
            settle(0,"released")
            return fail("auth_expired", "Provider rejected credentials or entitlement")
        if response.status_code == 429:
            settle(0,"released")
            return fail("rate_limited", "Provider rate limit reached")
        response.raise_for_status()
        data=response.json()
        if response.status_code == 202:
            return fail("outcome_uncertain", "Provider verification pending; credit reservation held")
        settle(1,"charged")
        # Never report raw provider payload including PII or credentials through logs.
        return NormalizedResult(success=True,action=action,connector_id=connector_id,
                                data={"provider":vendor,"result":data})
    except (httpx.HTTPError,ValueError) as exc:
        # Ambiguous transport failures retain reservation pending reconciliation.
        return fail("tool_error", "Provider request failed: "+type(exc).__name__)


def register_prospecting_handlers() -> None:
    """Explicit opt-in at application startup, no implicit registration in imports."""
    from pathlib import Path
    from app.connectors.sdk import get_partner_executor, load_manifest_file, register_from_manifest
    base=Path(__file__).resolve().parents[1] / "plays" / "provider_manifests"
    for vendor in ALLOWED_TYPES:
        if get_partner_executor(vendor+".email.verify") or get_partner_executor(vendor+".people.search"):
            continue
        manifest=load_manifest_file(base / (vendor+".json"))
        handlers={}
        for action in manifest.actions:
            tool_action=f"{vendor}.{action.id}"
            def handler(ctx:ToolContext, params:dict[str,Any], *, _action:str=tool_action)->NormalizedResult:
                return execute_prospecting_action(ctx,_action,params)
            handlers[action.id]=handler
        register_from_manifest(manifest,handlers)
