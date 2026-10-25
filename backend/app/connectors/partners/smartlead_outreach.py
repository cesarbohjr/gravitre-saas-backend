"""Smartlead cold-outreach connector for Gravitre Prospecting Play.

Read-only campaign and sender account queries are executable. Enrollment is
separately blocked: adding a lead to an active campaign can immediately send,
so a canonical PendingAction + immutable consent review is required first.
"""
from __future__ import annotations
from typing import Any
import httpx
from app.connectors.repository import get_connector
from app.connectors.nango_client import scoped_connection, proxy_request
from app.services.tool_types import NormalizedResult, ToolContext

BASE = "https://server.smartlead.ai/api/v1"
READ_ACTIONS = {
    "campaigns.list": "/campaigns/",
    "email_accounts.list": "/email-accounts/",
    "analytics.overview": "/analytics/overview",
}

def execute_smartlead(ctx: ToolContext, action_id: str, params: dict[str,Any]) -> NormalizedResult:
    action="smartlead."+action_id
    cid=str(params.get("connector_id") or ctx.connector_id or "")
    def deny(code: str, message: str) -> NormalizedResult:
        return NormalizedResult(success=False,action=action,connector_id=cid,
                                error_code=code,error_message=message)
    if action_id not in READ_ACTIONS and action_id != "leads.enroll":
        return deny("action_not_found","Unknown Smartlead capability")
    if not ctx.org_id or not cid:
        return deny("connector_not_connected","Tenant-scoped connector is required")
    row=get_connector(ctx.client,ctx.org_id,cid,ctx.environment_name)
    if not row or row.get("type")!="smartlead" or row.get("status") not in {"active","healthy","connected","syncing"}:
        return deny("connector_not_connected","Smartlead connector unavailable")
    config=row.get("config") or {}
    if not isinstance(config,dict) or not config.get("outreach_enabled"):
        return deny("permission_denied","Outreach integration not enabled for tenant")
    if action_id=="leads.enroll":
        # Adding a lead to an active campaign may itself transmit mail.
        # Do not accept a boolean or approval-id string from an untrusted tool call.
        return deny("permission_denied","Requires canonical approved PendingAction, verified consent and pre-enrollment suppression sync")
    # Headless Nango connection; no provider API keys are read or stored in Gravitre.
    connection_id = str(config.get("managed_connection_id") or "")
    integration_id = str(config.get("managed_integration_id") or "")
    if config.get("auth_provider") != "managed" or not connection_id or integration_id != "smartlead":
        return deny("connector_not_connected", "Smartlead requires a Nango managed connection")
    try:
        scoped_connection(ctx.settings, connection_id=connection_id,
                          integration_id=integration_id, org_id=ctx.org_id,
                          connector_id=cid)
        response=proxy_request(
            ctx.settings,method="GET",endpoint=READ_ACTIONS[action_id],
            connection_id=connection_id,integration_id=integration_id,
            extra_headers={"Accept":"application/json"},
        )
        if response.status_code in (401,403):
            return deny("auth_expired","Smartlead authorization rejected")
        if response.status_code==429:
            return deny("rate_limited","Smartlead rate limit")
        response.raise_for_status()
        return NormalizedResult(success=True,action=action,connector_id=cid,
                data={"provider":"smartlead","result":response.json()})
    except (httpx.HTTPError,ValueError) as exc:
        return deny("tool_error","Smartlead Nango proxy request failed: "+type(exc).__name__)

def ensure_smartlead_registered() -> None:
    from app.connectors.sdk import get_partner_executor,register_from_manifest
    if get_partner_executor("smartlead.campaigns.list"):
        return
    actions=("campaigns.list","email_accounts.list","analytics.overview","leads.enroll")
    manifest={"manifestVersion":"1.0","id":"smartlead-outreach","name":"Smartlead Cold Outreach",
      "version":"0.1.0","vendor":"smartlead","description":"Read campaigns and prepare gated outreach",
      "auth":{"type":"apiKey","headerName":"X-Gravitre-Vault"},
      "capabilities":["actions"],"actions":[{
         "id":name,"name":name,"description":"Read provider or request guarded lead enrollment",
         "scopes":["smartlead:"+name],
         "inputSchema":{"type":"object","properties":{"connector_id":{"type":"string"}}},
         "idempotent":name!="leads.enroll","destructive":False
       } for name in actions]}
    handlers={}
    for name in actions:
        def call(ctx:ToolContext,params:dict[str,Any],*,_name:str=name)->NormalizedResult:
            return execute_smartlead(ctx,_name,params)
        handlers[name]=call
    register_from_manifest(manifest,handlers)
