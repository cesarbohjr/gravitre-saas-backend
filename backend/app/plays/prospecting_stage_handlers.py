"""Native prospecting stage executors for canonical invoke_tool runtime.

Stages are deliberately fail-closed. They operate on tenant-owned persisted
records and never bypass human review or create external CRM/email side effects.
"""
from __future__ import annotations
from typing import Any
from app.services.tool_types import NormalizedResult, ToolContext

ACTIONS=("companies.discover","companies.research","contacts.verify","contacts.review","contacts.stage")

def _result(action:str,success:bool,*,data:dict[str,Any]|None=None,code:str|None=None,message:str|None=None)->NormalizedResult:
    return NormalizedResult(success=success,action="prospecting."+action,data=data or {},error_code=code,error_message=message)

def _handle(ctx:ToolContext,action:str,params:dict[str,Any])->NormalizedResult:
    if not ctx.org_id or not ctx.actor_id:
        return _result(action,False,code="permission_denied",message="Tenant and actor required")
    if action=="companies.discover":
        rows=(ctx.client.table("prospect_companies").select("id,name,domain,source_url,source_authorized")
              .eq("org_id",ctx.org_id).eq("source_authorized",True).limit(100).execute().data or [])
        return _result(action,True,data={"companies":rows,"source":"tenant_persisted_authorized","new_companies":0})
    if action=="companies.research":
        company_id=str(params.get("company_id") or "")
        if not company_id:
            return _result(action,False,code="validation_error",message="Company ID required")
        rows=(ctx.client.table("prospect_companies").select("id,name,domain,fit_score,source_url,source_authorized")
              .eq("org_id",ctx.org_id).eq("id",company_id).limit(1).execute().data or [])
        if not rows or not rows[0].get("source_authorized"):
            return _result(action,False,code="permission_denied",message="Authorized source evidence required")
        return _result(action,True,data={"company":rows[0],"research_source":"persisted","fetched_external_site":False})
    if action=="contacts.verify":
        contact_id=str(params.get("contact_id") or "")
        if not contact_id: return _result(action,False,code="validation_error",message="Contact ID required")
        rows=(ctx.client.table("prospect_contacts").select("id,email,email_status,verification_provider,verified_at")
              .eq("org_id",ctx.org_id).eq("id",contact_id).limit(1).execute().data or [])
        if not rows: return _result(action,False,code="validation_error",message="Contact not found")
        return _result(action,True,data={"contact":rows[0],"verification_cached":True,"vendor_called":False})
    if action=="contacts.review":
        # Consent cannot be granted or invented by the workflow agent.
        return _result(action,False,code="permission_denied",message="Human consent review required in authenticated review UI")
    if action=="contacts.stage":
        if not params.get("approved_pending_action_id"):
            return _result(action,False,code="permission_denied",message="Canonical PendingAction authorization required")
        # A supplied approval ID is not itself proof of approval.
        return _result(action,False,code="permission_denied",message="PendingAction verification integration not enabled")
    return _result(action,False,code="action_not_found",message="Unrecognized prospecting stage")

def register_prospecting_stage_handlers()->None:
    from app.connectors.sdk import get_partner_executor,register_from_manifest
    if get_partner_executor("prospecting.companies.discover"):
        return
    actions=[{"id":name,"name":name,"description":"Tenant-scoped prospecting stage",
        "scopes":["prospecting:"+name],"inputSchema":{"type":"object"},
        "idempotent":True,"destructive":False} for name in ACTIONS]
    manifest={"manifestVersion":"1.0","id":"native-prospecting-stages","name":"Prospecting stages",
        "version":"0.1.0","vendor":"prospecting","auth":{"type":"apiKey","headerName":"X-Internal-Not-Used"},
        "capabilities":["actions"],"actions":actions}
    handlers={}
    for name in ACTIONS:
        def run(ctx:ToolContext,params:dict[str,Any],*,_name:str=name)->NormalizedResult:
            return _handle(ctx,_name,params)
        handlers[name]=run
    register_from_manifest(manifest,handlers)
