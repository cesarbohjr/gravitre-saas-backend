"""Service-only external prospect writes. No tool caller can pass an approval boolean.

Nango integration MUST inject Smartlead's query-string api_key upstream. API
keys never enter this method. Enrollment is intentionally callable only by a
worker holding a trusted service client and an exact persisted approval.
"""
from __future__ import annotations
from typing import Any
import httpx
from app.connectors.nango_client import proxy_request,scoped_connection
from app.connectors.repository import get_connector
from app.plays.prospecting_approval import resolve_prospecting_approval
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext
from app.services.write_authority import write_authority

def approved_hubspot_create(ctx:ToolContext,*,run_id:str,connector_id:str,
        payload:dict[str,Any])->dict[str,Any]:
    approval=resolve_prospecting_approval(ctx.client,org_id=ctx.org_id,
      actor_id=ctx.actor_id,run_id=run_id,stage="crm_export",
      action="hubspot.contacts.create",payload=payload)
    if not approval: raise PermissionError("Exact approved HubSpot action required")
    with write_authority("human",approval):
        result=invoke_tool(ctx,"hubspot.contacts.create",{"connector_id":connector_id,**payload})
    if not result.success: raise result.to_exception()
    if not str(result.data.get("contact_id") or "").strip():
        raise RuntimeError("HubSpot did not confirm a contact ID; reconcile before retry")
    return {"success":True,"provider":"hubspot","data":result.data,"approval_id":approval}

def approved_smartlead_enroll(ctx:ToolContext,*,run_id:str,connector_id:str,
        campaign_id:str,contact_id:str,email:str,first_name:str="",
        last_name:str="")->dict[str,Any]:
    if not campaign_id.isascii() or not campaign_id.isdecimal() or int(campaign_id)<1:
        raise ValueError("Smartlead campaign must be a positive numeric ID")
    recipient=email.strip().lower()
    if not recipient or "@" not in recipient: raise ValueError("Invalid recipient")
    payload={"connector_id":connector_id,"campaign_id":campaign_id,
        "contact_id":contact_id,"email":recipient,"first_name":first_name,
        "last_name":last_name}
    approval=resolve_prospecting_approval(ctx.client,org_id=ctx.org_id,
       actor_id=ctx.actor_id,run_id=run_id,stage="outreach_enroll",
       action="smartlead.leads.enroll",payload=payload)
    if not approval: raise PermissionError("Exact approved enrollment required")
    contacts=(ctx.client.table("prospect_contacts").select("id,email,consent_reviewed_at,consent_basis")
       .eq("org_id",ctx.org_id).eq("id",contact_id).limit(1).execute().data or [])
    if not contacts or str(contacts[0].get("email") or "").strip().lower()!=recipient:
        raise PermissionError("Recipient does not match tenant contact")
    if not contacts[0].get("consent_reviewed_at") or not contacts[0].get("consent_basis"):
        raise PermissionError("Persisted consent review required")
    blocked=(ctx.client.table("prospect_suppressions").select("id")
        .eq("org_id",ctx.org_id).eq("normalized_email",recipient).limit(1).execute().data or [])
    if blocked: raise PermissionError("Recipient suppressed")
    row=get_connector(ctx.client,ctx.org_id,connector_id,ctx.environment_name)
    if not row or row.get("type")!="smartlead" or row.get("status") not in {"active","healthy","connected","syncing"}:
        raise PermissionError("Tenant Smartlead connector unavailable")
    config=row.get("config") or {}
    if (not config.get("outreach_enabled") or config.get("auth_provider")!="managed"
        or config.get("managed_integration_id")!="smartlead-ai" or not config.get("managed_connection_id")):
        raise PermissionError("Nango-managed Smartlead connection unavailable")
    connection_id=str(config["managed_connection_id"])
    scoped_connection(ctx.settings,connection_id=connection_id,integration_id="smartlead-ai",
       org_id=ctx.org_id,connector_id=connector_id)
    # Never retry a failed/uncertain POST automatically: the durable claim must be reconciled.
    response=proxy_request(ctx.settings,method="POST",
       endpoint=f"/campaigns/{campaign_id}/leads",
       connection_id=connection_id,integration_id="smartlead",
       json_body={"lead_list":[{"email":recipient,"first_name":first_name,
                                  "last_name":last_name}]})
    response.raise_for_status()
    result=response.json()
    if not isinstance(result,dict) or result.get("success") is False or result.get("error") or result.get("status") in ("error","failed"):
        raise RuntimeError("Smartlead enrollment not confirmed; reconcile before retry")
    return {"success":True,"provider":"smartlead","campaign_id":campaign_id,
            "provider_response":result,"approval_id":approval}
