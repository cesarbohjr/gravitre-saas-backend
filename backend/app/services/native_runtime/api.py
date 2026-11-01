"""Private worker API. Only short-lived, exact-body backend envelopes are accepted."""
from __future__ import annotations
from fastapi import FastAPI,Request,HTTPException
from app.services.native_agent_adapters import AdapterScope,TelemetryPermit
from app.services.native_runtime.control import IntakeSigner,require_access,require_member_and_agent


def create_app(runtime,outbox,signer: IntakeSigner) -> FastAPI:
    app=FastAPI(title='Gravitre private native worker',docs_url=None,redoc_url=None,openapi_url=None)
    @app.post('/v1/invoke')
    async def invoke(request: Request):
        try:
            if int(request.headers.get('content-length','0'))>262144:raise ValueError('bounds')
            body=bytearray()
            async for chunk in request.stream():
                if len(body)+len(chunk)>262144:raise ValueError('bounds')
                body.extend(chunk)
            import json
            envelope=json.loads(body);operation=envelope['operation'];payload=envelope['payload']
            if not isinstance(payload,dict):raise ValueError('shape')
            token=request.headers.get('authorization','')
            if not token.startswith('Bearer '):raise PermissionError('authentication')
            claims=signer.verify(token[7:],operation,payload)
            scope=AdapterScope(**claims['scope']);ctx=runtime.context(claims)
            if operation in ('run_openhands','run_browser_use'):
                id=runtime.enqueue(claims,'openhands' if operation=='run_openhands' else 'browser_use',payload)
                row=runtime.journal.get(scope,id)
                return {'job_id':id,'run_id':scope.run_id,'state':row['state'],'verified_execution':False}
            if operation=='native_job_status':
                row=runtime.journal.get(scope,payload['job_id'])
                if row and row['kind'] in ('langfuse','langfuse_delete'):
                    require_access(ctx,'telemetry')
                    if row['actor']!=claims['actor']:raise PermissionError('scope')
                    return {k:v for k,v in row.items() if k!='actor'}
                return runtime.status(claims,payload['job_id'])
            if operation=='cancel_native_job':return {'cancelled':runtime.cancel(claims,payload['job_id'])}
            if operation=='approve_native_action':
                runtime.approve(claims,payload['job_id'],payload['request_id'],payload['digest'],payload['approved'])
                return {'state':'approved' if payload['approved'] else 'denied'}
            if operation=='export_evaluation_metrics':
                require_access(ctx,'telemetry')
                authority=claims.get('authority') or {}
                if authority.get('kind') not in ('human','run') or not authority.get('ref'):raise PermissionError('consent')
                # Verify a configured, tenant-specific delivery route before
                # creating consent or a queue item. Missing config fails closed.
                configured_transport=outbox.transport_for(scope)
                from app.services.native_runtime.langfuse import LangfuseTransport
                if isinstance(configured_transport,LangfuseTransport):configured_transport.close()
                runtime.journal.consume_authority(scope.org_id,claims['actor'],authority['ref'],'telemetry:'+payload['receipt_id'])
                id=outbox.enqueue(runtime.client,payload['receipt_id'],scope=scope,permit=TelemetryPermit(scope,True),actor=claims['actor'])
                if not id:raise ValueError('receipt missing')
                row=runtime.journal.get(scope,id)
                return {'job_id':id,'run_id':scope.run_id,'state':row['state'],'kind':row['kind'],'delivered':row['state']=='delivered'}
            if operation=='withdraw_evaluation_metrics':
                require_member_and_agent(ctx)
                owners=runtime.journal.owners(scope)
                if owners and owners!={claims['actor']}:raise PermissionError('scope')
                outbox.withdraw(scope)
                return {'consent':False,'remote_deletion':'pending_verification'}
            raise ValueError('unknown operation')
        except Exception:
            # Provider errors, secrets, request bodies and tenant identities are
            # deliberately absent from the public response and logs.
            raise HTTPException(403,'Native request unavailable, unauthorized or stale') from None
    return app
