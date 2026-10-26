"""Approved Smartlead enrollment through the tenant-scoped Nango proxy.

Never callable from an untrusted tool action. The workflow service must supply
an authenticated tenant actor, persisted Play run, and a server-side approval
record matching the exact enrollment payload.
"""
from __future__ import annotations
from typing import Any
import httpx
from app.connectors.repository import get_connector
from app.connectors.nango_client import scoped_connection,proxy_request
from app.plays.prospecting_approvals import resolve_stage_approval

def enroll_approved_smartlead_lead(*,client:Any,settings:Any,org_id:str,
    run_id:str,actor_id:str,connector_id:str,campaign_id:str,
    prospect_contact_id:str,recipient_email:str,first_name:str="",
    last_name:str="")->dict[str,Any]:
    if not all((org_id,run_id,actor_id,connector_id,campaign_id,prospect_contact_id)):
        raise ValueError("Missing enrollment identity")
    if not campaign_id.isascii() or not campaign_id.isdecimal() or int(campaign_id)<1:
        raise ValueError("Invalid Smartlead campaign")
    email=recipient_email.strip().lower()
    if "@" not in email or len(email)>254:
        raise ValueError("Invalid email")
    contact=(client.table("prospect_contacts").select("id,email,consent_reviewed_by,consent_reviewed_at,email_status")
      .eq("org_id",org_id).eq("id",prospect_contact_id).limit(1).execute().data or [])
    if not contact or str(contact[0].get("email") or "").strip().lower()!=email:
        raise PermissionError("Prospect not owned by tenant or email mismatch")
    if (not contact[0].get("consent_reviewed_by") or not contact[0].get("consent_reviewed_at")
       or contact[0].get("email_status") not in {"valid","verified"}):
        raise PermissionError("Verified email and persisted consent review required")
    suppression=(client.table("prospect_suppressions").select("id").eq("org_id",org_id)
                 .eq("normalized_email",email).limit(1).execute().data or [])
    if suppression:
        raise PermissionError("Recipient suppressed")
    approved_payload={"connector_id":connector_id,"campaign_id":campaign_id,
       "prospect_contact_id":prospect_contact_id,"recipient_email":email,
       "first_name":first_name,"last_name":last_name}
    if not resolve_stage_approval(client,org_id=org_id,run_id=run_id,
        actor_id=actor_id,stage="outreach_enroll",approved_payload=approved_payload):
        raise PermissionError("Exact enrollment not approved")
    run=(client.table("prospect_play_runs").select("id,current_stage,state")
         .eq("org_id",org_id).eq("id",run_id).eq("requested_by",actor_id).limit(1).execute().data or [])
    if not run or run[0]["current_stage"]!="outreach_enroll" or run[0]["state"] not in {"running","awaiting_approval"}:
        raise PermissionError("Play is not at approved enrollment stage")
    row=get_connector(client,org_id,connector_id,"production")
    if not row or row.get("type")!="smartlead" or row.get("status") not in {"active","healthy","connected","syncing"}:
        raise PermissionError("Tenant Smartlead connector not connected")
    cfg=row.get("config") or {}
    connection_id=str(cfg.get("managed_connection_id") or "")
    if (not cfg.get("outreach_enabled") or cfg.get("auth_provider")!="managed"
      or cfg.get("managed_integration_id")!="smartlead" or not connection_id):
        raise PermissionError("Smartlead Nango connection is not enabled")
    scoped_connection(settings,connection_id=connection_id,integration_id="smartlead",
       org_id=org_id,connector_id=connector_id)
    # This call can begin campaign sends. The calling runtime MUST first acquire
    # the atomic prospect_claim_step lease. Unknown outcomes are not retried.
    response=proxy_request(settings,method="POST",
       endpoint=f"/campaigns/{campaign_id}/leads",
       connection_id=connection_id,integration_id="smartlead",
       json_body={"lead_list":[{"email":email,"first_name":first_name,"last_name":last_name}]})
    if response.status_code in {401,403,429}:
        raise PermissionError("Smartlead authorization, rate limit or plan restriction")
    response.raise_for_status()
    body=response.json()
    return {"success":True,"provider":"smartlead","campaign_id":campaign_id,
       "recipient_email":email,"provider_response":body,"enrolled":True,
       "email_sent":False}
