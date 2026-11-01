"""Durable native job lifecycle and fresh authorization for each worker boundary."""
from __future__ import annotations
from dataclasses import dataclass,asdict
import hashlib
import json
import time
from typing import Any,Callable
from app.services.native_agent_adapters import AdapterScope,openhands_review_plan,browser_use_review_plan
from app.services.native_runtime.control import ACTIONS,require_access,require_member_and_agent,validate_task
from app.services.native_runtime.store import Journal,LeaseLost
from app.services.tool_types import ToolContext
from app.services.voice_barge_in_write import raise_if_barge_in_blocks_invoke
from app.services.model_policy_service import assert_model_allowed,load_org_model_policy


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    base_url: str
    api_key: str
    budget_usd: float
    input_usd_per_million: float
    output_usd_per_million: float
    max_output_tokens: int=4096

    def validate(self) -> None:
        from urllib.parse import urlsplit
        import math
        p=urlsplit(self.base_url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or not self.api_key or not self.provider or not self.model:
            raise ValueError('Reviewed tenant model route required')
        for value in (self.budget_usd,self.input_usd_per_million,self.output_usd_per_million):
            if type(value) not in (int,float) or not math.isfinite(value) or value<=0:raise ValueError('Reviewed finite model pricing/budget required')
        if not 1<=self.max_output_tokens<=8192:raise ValueError('Invalid model output bound')


class NativeRuntime:
    def __init__(self,journal: Journal,settings: Any,client: Any,runner: Any,route_for: Callable[[AdapterScope],ModelRoute]):
        self.journal=journal;self.settings=settings;self.client=client;self.runner=runner;self.route_for=route_for

    def context(self,claims: dict) -> ToolContext:
        s=AdapterScope(**claims['scope'])
        return ToolContext(settings=self.settings,client=self.client,org_id=s.org_id,actor_id=claims['actor'],agent_id=s.agent_id,run_id=s.run_id,
            conversation_id=claims.get('conversation_id'),turn_id=claims.get('turn_id'))

    def authorize(self,claims: dict,permission: str='execute') -> ModelRoute | None:
        ctx=self.context(claims);require_access(ctx,permission)
        if permission!='execute':return None
        route=self.route_for(AdapterScope(**claims['scope']));route.validate()
        assert_model_allowed(load_org_model_policy(self.client,ctx.org_id),provider=route.provider,model=route.model)
        raise_if_barge_in_blocks_invoke(ctx,ACTIONS[claims['engine']])
        return route

    def enqueue(self,claims: dict,engine: str,params: dict) -> str:
        if engine not in ACTIONS:raise ValueError('Unsupported native engine')
        authority=claims.get('authority')
        if not isinstance(authority,dict) or authority.get('kind') not in ('human','run') or not authority.get('ref'):
            raise PermissionError('Approved native request required')
        claims={**{key:claims.get(key) for key in ('scope','actor','authority','conversation_id','turn_id')},'engine':engine}
        self.authorize(claims)
        payload=validate_task(engine,params)
        scope=AdapterScope(**claims['scope'])
        identity=hashlib.sha256(json.dumps([scope.run_id,engine,claims['actor'],authority['ref']],separators=(',',':')).encode()).hexdigest()
        self.journal.consume_authority(scope.org_id,claims['actor'],authority['ref'],'submit:'+identity)
        return self.journal.enqueue(scope,engine,identity,{'claims':claims,'task':payload},ttl=payload['max_seconds']+60,max_attempts=1,actor=claims['actor'])

    def status(self,claims: dict,job_id: str) -> dict:
        scope=AdapterScope(**claims['scope']);row=self.journal.get(scope,job_id,material=True)
        if not row or row['kind'] not in ACTIONS:raise PermissionError('Native job not found')
        if row['actor']!=claims['actor']:raise PermissionError('Native job belongs to another actor')
        require_access(self.context(claims),'read')
        result={k:v for k,v in row.items() if k not in ('payload','result','actor')}
        result['actions']=[a for a in self.journal.actions(scope,job_id) if a['state']=='pending'] if row['state']=='running' else []
        # Results remain advisory; no external success claim becomes verified.
        if row['state']=='completed':result['review']=row['result']
        return result

    def cancel(self,claims: dict,job_id: str) -> bool:
        # Membership/agent scope remains required; cancellation is not a new
        # execution grant and must remain possible after execute is revoked.
        require_member_and_agent(self.context(claims))
        row=self.journal.get(AdapterScope(**claims['scope']),job_id)
        if not row or row['actor']!=claims['actor']:raise PermissionError('Native job not found')
        return self.journal.cancel(AdapterScope(**claims['scope']),job_id)

    def approve(self,claims: dict,job_id: str,request_id: str,digest: str,approved: bool) -> None:
        authority=claims.get('authority')
        if not isinstance(authority,dict) or authority.get('kind')!='human' or not authority.get('ref'):raise PermissionError('Fresh human approval required')
        self.status(claims,job_id)
        row=self.journal.get(AdapterScope(**claims['scope']),job_id,material=True)
        self.authorize(row['payload']['claims'])
        self.journal.consume_authority(claims['scope']['org_id'],claims['actor'],authority['ref'],'action:'+request_id+':'+digest+':'+str(approved))
        self.journal.approve(AdapterScope(**claims['scope']),job_id,request_id,digest,approved)

    def tick(self,engine: str) -> str | None:
        job=self.journal.claim(engine,lease_seconds=60)
        if not job:return None
        claims=job['payload']['claims'];last_renew=[time.monotonic()];bound_route=[None]
        def guard() -> ModelRoute:
            if not self.journal.active(job):raise LeaseLost('Native job no longer active')
            route=self.authorize(claims)
            if bound_route[0] is None:bound_route[0]=route
            elif route!=bound_route[0]:raise PermissionError('Native model route changed; new approval required')
            if time.monotonic()-last_renew[0]>=15:
                self.journal.update(job,'running');last_renew[0]=time.monotonic()
            return route
        def action(sequence: int,details: dict) -> dict:
            guard()
            return self.journal.request_action(job,sequence,details)
        try:
            guard()
            result=self.runner.execute(job,guard=guard,action_gate=action)
            guard()
            if not isinstance(result,dict) or len(json.dumps(result).encode())>240000:raise ValueError('Invalid native result')
            # Scope is attached by trusted host code, not accepted from SDK output.
            envelope={**result,'schema_version':1,'org_id':job['scope'].org_id,'agent_id':job['scope'].agent_id,'run_id':job['scope'].run_id}
            plan=(openhands_review_plan(envelope,scope=job['scope']) if engine=='openhands' else browser_use_review_plan(envelope,scope=job['scope'],allowed_hosts=frozenset(job['payload']['task']['allowed_hosts'])))
            review={'plan':plan.model_dump(mode='json') if hasattr(plan,'model_dump') else asdict(plan),
                    'patch':result.get('patch','')[:120000] if engine=='openhands' and isinstance(result.get('patch'),str) else '',
                    'verified_execution':False,'requires_review':True}
            self.journal.update(job,'completed',result=review)
            return 'completed'
        except LeaseLost:
            return 'cancelled_or_lease_lost'
        except Exception:
            try:self.journal.update(job,'failed',error='native_execution_failed')
            except LeaseLost:pass
            return 'failed'
        finally:
            self.runner.cleanup(job['id'])
