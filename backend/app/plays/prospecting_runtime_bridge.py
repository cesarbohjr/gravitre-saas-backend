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
