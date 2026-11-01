"""Canonical invoke_tool adapters. No worker action inherits a legacy wildcard grant."""
from __future__ import annotations
from urllib.parse import urlsplit
import httpx
from app.services.native_runtime.control import IntakeSigner,require_access,require_member_and_agent,require_approval,ACTIONS
from app.services.tool_types import ToolContext,NormalizedResult,ToolValidationError

OPERATIONS=('run_openhands','run_browser_use','native_job_status','cancel_native_job','approve_native_action','export_evaluation_metrics','withdraw_evaluation_metrics')


def invoke_native(ctx: ToolContext,operation: str,params: dict) -> NormalizedResult:
    action='assistant.'+operation
    if operation not in OPERATIONS:raise ToolValidationError('Unknown native operation')
    url=str(getattr(ctx.settings,'native_worker_url','') or '').rstrip('/')
    u=urlsplit(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        return NormalizedResult(False,action,error_code='native_worker_unavailable',error_message='This native worker is not configured. Advisory review remains available.')
    request=dict(params)
    # Internal canonical ledger metadata is not an SDK task or authority.
    request.pop("_gravitre_idempotency_key",None)
    run_id=request.pop('run_id',None)
    authority=None
    if operation in ('run_openhands','run_browser_use'):
        require_access(ctx,'execute');authority=require_approval()
        from app.services.voice_barge_in_write import raise_if_barge_in_blocks_invoke,raise_if_speculative_blocks_invoke
        raise_if_speculative_blocks_invoke(action);raise_if_barge_in_blocks_invoke(ctx,action)
    elif operation=='approve_native_action':require_access(ctx,'execute');authority=require_approval(human_only=True)
    elif operation=='export_evaluation_metrics':require_access(ctx,'telemetry');authority=require_approval()
    elif operation in ('cancel_native_job','withdraw_evaluation_metrics'):require_member_and_agent(ctx)
    else:require_access(ctx,'read')
    signer=IntakeSigner(str(getattr(ctx.settings,'native_worker_signing_key','') or ''))
    token=signer.sign(ctx,operation,request,run_id=run_id,authority=authority)
    try:
        with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
            r=client.post(url+'/v1/invoke',json={'operation':operation,'payload':request},headers={'Authorization':'Bearer '+token})
            if r.status_code!=200:raise ValueError('Native request failed')
            result=r.json()
            if not isinstance(result,dict):raise ValueError('Malformed native result')
            return NormalizedResult(True,action,data=result)
    except Exception:
        # Enqueue may have committed before a transport failure. A retry uses
        # the same approved operation identity; it never blindly executes again.
        return NormalizedResult(False,action,error_code='native_outcome_uncertain',error_message='The native request could not be confirmed. Check its durable status before retrying.')


def _handler(operation):
    def execute(ctx,params):return invoke_native(ctx,operation,params)
    return execute

NATIVE_EXECUTORS={'assistant.'+op:_handler(op) for op in OPERATIONS}
