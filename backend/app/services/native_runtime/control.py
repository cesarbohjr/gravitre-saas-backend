"""Current tenant/IAM checks and signed backend-to-worker intake envelopes."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
import re
import time
from uuid import UUID
import jwt
from app.services.native_agent_adapters import AdapterScope
from app.services.agent_memory_service import ensure_agent_in_org
from app.services.agent_tool_permissions import list_agent_tool_permissions
from app.services.tool_types import ToolContext,ToolPermissionDeniedError
from app.services.write_authority import current_write_authority

SCOPES={'execute':'platform:native:execute','read':'platform:native:read','telemetry':'platform:telemetry:export'}
ACTIONS={'openhands':'assistant.run_openhands','browser_use':'assistant.run_browser_use'}


def require_member_and_agent(ctx: ToolContext) -> None:
    if not ctx.client or not ctx.actor_id or ctx.actor_id=='system' or not ctx.agent_id:
        raise ToolPermissionDeniedError('Authenticated actor and persisted agent required')
    for value in (ctx.org_id,ctx.agent_id):
        try:UUID(str(value))
        except (ValueError,TypeError):raise ToolPermissionDeniedError('Persisted tenant/agent scope required') from None
    rows=(ctx.client.table('organization_members').select('role').eq('org_id',ctx.org_id).eq('user_id',ctx.actor_id).limit(1).execute().data or [])
    if not rows or rows[0].get('role') not in {'owner','admin','member'}:raise ToolPermissionDeniedError('Current organization membership required')
    ensure_agent_in_org(ctx.client,ctx.org_id,str(ctx.agent_id))


def require_access(ctx: ToolContext, permission: str) -> None:
    require_member_and_agent(ctx)
    expected=SCOPES[permission]
    now=datetime.now(timezone.utc)
    for row in list_agent_tool_permissions(ctx.client,ctx.org_id,str(ctx.agent_id)):
        # No legacy wildcard or default platform grant activates native workers.
        if row.get('org_id')!=ctx.org_id or row.get('agent_id')!=ctx.agent_id or row.get('connector_type')!='platform' or expected not in (row.get('scopes') or []):continue
        expiry=row.get('expires_at')
        if expiry:
            try:
                date=datetime.fromisoformat(str(expiry).replace('Z','+00:00'))
                if date.tzinfo is None or date<=now:continue
            except ValueError:continue
        return
    raise ToolPermissionDeniedError('An explicit current native execution or telemetry grant is required')


def require_approval(*, human_only: bool=False):
    authority=current_write_authority()
    if not authority or authority.kind not in ({'human'} if human_only else {'human','run'}) or not authority.ref:
        raise ToolPermissionDeniedError('This native action requires explicit approval')
    return authority


def scope_for(ctx: ToolContext, run_id: str | None=None) -> AdapterScope:
    run=run_id or ctx.run_id or ctx.turn_id
    if not run:raise ToolPermissionDeniedError('Durable run/turn scope is required')
    return AdapterScope(ctx.org_id,str(ctx.agent_id),str(run))


def validate_task(engine: str, params: dict, *, max_seconds: int=300, max_steps: int=20) -> dict:
    if engine not in ACTIONS:raise ValueError('Unknown native runtime')
    if set(params)-{'task','files','allowed_hosts'}:raise ValueError('Unknown native task field')
    task=params.get('task')
    if not isinstance(task,str) or not 1<=len(task.strip())<=8000:raise ValueError('A bounded software/browser task is required')
    files=params.get('files') or {}
    if not isinstance(files,dict) or len(files)>20:raise ValueError('At most twenty supplied software files are supported')
    for path,value in files.items():
        if not isinstance(path,str) or len(path)>160 or not re.fullmatch(r'[a-zA-Z0-9_-][a-zA-Z0-9_.-]*(?:/[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)*',path) or any(p in {'..','.git','.env','node_modules'} or p.startswith('.') for p in path.split('/')):
            raise ValueError('Only bounded relative source-file paths are accepted')
        if not isinstance(value,str) or len(value)>16000:raise ValueError('Oversized source file')
        if re.search(r'-----BEGIN .*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}|\bAKIA[A-Z0-9]{16}\b',value):raise ValueError('Remove credentials from supplied code')
    hosts=params.get('allowed_hosts') or []
    if not isinstance(hosts,list) or len(hosts)>10:raise ValueError('At most ten explicit destinations are supported')
    if engine=='openhands' and hosts:raise ValueError('Software sandboxes have no external browsing access')
    if engine=='browser_use' and (not hosts or files):raise ValueError('Browser tasks require explicit hosts and do not accept source files')
    for host in hosts:
        if not isinstance(host,str) or len(host)>253 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+',host):raise ValueError('Only exact DNS hosts are accepted')
        from app.services.native_runtime.network import public_addresses
        public_addresses(host)
    if not 1<=max_seconds<=600 or not 1<=max_steps<=100:raise ValueError('Invalid configured execution limits')
    result={'task':task,'files':files,'allowed_hosts':list(dict.fromkeys(hosts)),'max_seconds':max_seconds,'max_steps':max_steps}
    if len(json.dumps(result).encode())>240000:raise ValueError('Native input exceeds the bounded task envelope')
    return result


class IntakeSigner:
    def __init__(self, key: str):
        if len(key)<32:raise ValueError('Dedicated backend/worker signing key required')
        self.key=key

    def sign(self, ctx: ToolContext, operation: str, payload: dict, *, run_id: str | None=None, authority=None) -> str:
        scope=scope_for(ctx,run_id)
        return jwt.encode({'iss':'gravitre.backend','aud':'gravitre.native-worker','iat':int(time.time()),'exp':int(time.time())+60,
            'scope':asdict(scope),'actor':ctx.actor_id,'operation':operation,'payload_hash':hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'authority':asdict(authority) if authority else None,'conversation_id':ctx.conversation_id,'turn_id':ctx.turn_id},self.key,algorithm='HS256')

    def verify(self, token: str, operation: str, payload: dict) -> dict:
        claims=jwt.decode(token,self.key,algorithms=['HS256'],audience='gravitre.native-worker',issuer='gravitre.backend',options={'require':['exp','iat','scope','actor','operation','payload_hash']})
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if claims['operation']!=operation or claims['payload_hash']!=digest:raise PermissionError('Native intake scope/parameters changed')
        AdapterScope(**claims['scope'])
        return claims
