"""Bridge durable prospecting checkpoints to Gravitre's canonical invoke_tool spine.

Production must supply a service-role DB client and a server-side approval
resolver. Never accept approvals from caller tool parameters.
"""
from __future__ import annotations
from typing import Any,Callable
from app.plays.prospecting_execution import run_stage
from app.marketplace.workflows.qualified_prospecting_workflow import STAGE_ACTIONS
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext
from app.core.safe_dict import safe_normalize_stored_dict

def invoke_prospecting_stage(ctx:ToolContext, *,stage:str,
    params:dict[str,Any], approval_resolver:Callable[[str,str,str,str],bool]|None=None
)->dict[str,Any]:
    if not ctx.run_id or not ctx.org_id or not ctx.actor_id:
        raise ValueError("Canonical workflow run, tenant and actor are mandatory")
    action=STAGE_ACTIONS.get(stage)
    if not action:
        raise ValueError("Unsupported stage; external writes require separate approved executor")
    allowed_params={k:v for k,v in params.items() if k not in {
        "approved","approval_verified","source_verified","write_authority"}}
    def execute()->dict[str,Any]:
        result=invoke_tool(ctx,action,allowed_params)
        if not result.success:
            raise result.to_exception()
        return {"success":True,"action":action,"data":result.data}
    return run_stage(ctx.client,org_id=ctx.org_id,run_id=ctx.run_id,
      stage=stage,actor_id=ctx.actor_id,execute=execute,
      approval_resolver=approval_resolver)

def invoke_approved_external_stage(ctx:ToolContext,*,stage:str,
    params:dict[str,Any])->dict[str,Any]:
    """Run a CRM or campaign write inside the atomic checkpoint claim.

    The private executors resolve an exact action/payload approval from DB.
    Tool-supplied authority flags are never forwarded. Unknown outcomes are
    durable and require reconciliation, not blind re-enrollment.
    """
    from app.plays.prospecting_authorized_writes import (
        approved_hubspot_create,approved_smartlead_enroll)
    from app.plays.prospecting_approval import resolve_prospecting_approval
    if not ctx.run_id or stage not in {"crm_export","outreach_enroll"}:
        raise ValueError("Authenticated durable run and supported external stage required")
    action="hubspot.contacts.create" if stage=="crm_export" else "smartlead.leads.enroll"
    exact_payload=(safe_normalize_stored_dict(params, key="payload") if stage=="crm_export" else {
        **{k:params[k] for k in ("connector_id","campaign_id","contact_id","email")},
        "first_name":str(params.get("first_name") or ""),
        "last_name":str(params.get("last_name") or "")})
    approved_id=resolve_prospecting_approval(ctx.client,org_id=ctx.org_id,
        actor_id=ctx.actor_id,run_id=ctx.run_id,stage=stage,
        action=action,payload=exact_payload)
    def approved(org:str,actor:str,run:str,requested_stage:str)->bool:
        return (org==ctx.org_id and actor==ctx.actor_id and run==ctx.run_id
                and requested_stage==stage and bool(approved_id))
    def execute()->dict[str,Any]:
        if stage=="crm_export":
            return approved_hubspot_create(ctx,run_id=ctx.run_id,
                connector_id=str(params["connector_id"]),payload=exact_payload)
        return approved_smartlead_enroll(ctx,run_id=ctx.run_id,
            **exact_payload)
    return run_stage(ctx.client,org_id=ctx.org_id,run_id=ctx.run_id,
        stage=stage,actor_id=ctx.actor_id,execute=execute,
        approval_resolver=approved)
