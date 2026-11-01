"""Configured private broker entrypoint, with durable queues and isolated SDK workers.

Run on a dedicated Docker + gVisor/Kata host with a private persistent volume.
Nothing in this module is launched by importing the application or by installing
an agent. Missing secrets or image digests fail startup closed. Missing tenant routes or
permits deny intake.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
import json
import os
import threading
import time
from datetime import datetime,timezone
from app.core.logging import get_logger
from app.config import get_settings
from app.core.db import get_supabase_client
from app.services.native_agent_adapters import AdapterScope
from app.services.native_runtime.api import create_app
from app.services.native_runtime.control import IntakeSigner,require_access
from app.services.native_runtime.docker_runner import DockerRunner,SandboxImages
from app.services.native_runtime.langfuse import LangfuseOutbox,LangfuseTransport
from app.services.native_runtime.runtime import NativeRuntime,ModelRoute
from app.services.native_runtime.store import Journal
from app.services.tool_types import ToolContext


logger=get_logger(__name__)

def build_app(*, runner_factory=None):
    settings=get_settings();client=get_supabase_client(settings)
    journal=Journal(os.environ['NATIVE_JOURNAL_PATH'],os.environ['NATIVE_JOURNAL_KEY'].encode())
    signer=IntakeSigner(settings.native_worker_signing_key)
    images=SandboxImages(os.environ['NATIVE_OPENHANDS_IMAGE'],os.environ['NATIVE_BROWSER_IMAGE'],os.environ['NATIVE_GATEWAY_IMAGE'],os.environ.get('NATIVE_SANDBOX_RUNTIME','runsc'),playwright_comparison=os.environ.get('NATIVE_PLAYWRIGHT_IMAGE'))
    # These routes are trusted administrator configuration, not tool/model args.
    tenants=json.loads(os.environ['NATIVE_TENANTS_JSON'])
    if not isinstance(tenants,dict):raise ValueError('Explicit tenant route configuration required')
    telemetry_projects=[r['langfuse']['public_key'] for r in tenants.values() if r.get('langfuse')]
    if len(telemetry_projects)!=len(set(telemetry_projects)):raise ValueError('Langfuse projects must be tenant-specific')
    def tenant(scope):
        value=tenants.get(scope.org_id)
        if not isinstance(value,dict):raise PermissionError('Tenant has no native processing configuration')
        return value
    def route_for(scope):
        value=tenant(scope)
        permit=value.get('processing_permission') or {}
        if not permit.get('owner') or not permit.get('reference'):raise PermissionError('Named provider-processing permission required')
        from uuid import UUID
        UUID(permit['owner'])
        owner=(client.table('organization_members').select('role').eq('org_id',scope.org_id).eq('user_id',permit['owner']).limit(1).execute().data or [])
        if not owner or owner[0].get('role') not in {'owner','admin'}:raise PermissionError('Processing permission owner no longer authorized')
        expiry=datetime.fromisoformat(permit['expires_at'].replace('Z','+00:00'))
        if expiry.tzinfo is None or expiry<=datetime.now(timezone.utc) or (expiry-datetime.now(timezone.utc)).total_seconds()>2678400:raise PermissionError('Provider-processing permission expired')
        route=ModelRoute(**value['model']);route.validate();return route
    def transport_for(scope):
        return LangfuseTransport(**tenant(scope)['langfuse'])
    def export_allowed(scope):
        owners=journal.owners(scope)
        if len(owners)!=1:return False
        actor=next(iter(owners))
        try:
            require_access(ToolContext(settings,client,scope.org_id,actor,agent_id=scope.agent_id,run_id=scope.run_id),'telemetry')
            return True
        except Exception:return False
    runtime=NativeRuntime(journal,settings,client,(runner_factory if runner_factory is not None else DockerRunner)(images),route_for)
    outbox=LangfuseOutbox(journal,bytes.fromhex(os.environ['NATIVE_CORRELATION_KEY']),transport_for,export_allowed=export_allowed)
    app=create_app(runtime,outbox,signer)
    stop=threading.Event();threads=[]
    # One execution thread per engine, one telemetry thread. SQLite claims fence
    # concurrency; a missing durable queue never becomes a local async fallback.
    def native_loop(engine):
        last_warning=0.0
        while not stop.is_set():
            try:
                for id in journal.uncertain_jobs():
                    runtime.runner.cleanup(id);journal.reconciled(id)
                runtime.tick(engine)
            except Exception:
                if time.monotonic()-last_warning>=60:
                    logger.warning('native_worker_loop_unavailable engine=%s',engine);last_warning=time.monotonic()
            stop.wait(0.5)
    def telemetry_loop():
        last_warning=0.0
        while not stop.is_set():
            try:outbox.tick();outbox.tick('langfuse_delete')
            except Exception:
                if time.monotonic()-last_warning>=60:
                    logger.warning('native_metrics_loop_unavailable');last_warning=time.monotonic()
            stop.wait(0.5)
    @asynccontextmanager
    async def lifespan(_):
        for engine in ('openhands','browser_use'):
            thread=threading.Thread(target=native_loop,args=(engine,),daemon=True);thread.start();threads.append(thread)
        thread=threading.Thread(target=telemetry_loop,daemon=True);thread.start();threads.append(thread)
        yield
        stop.set()
        for thread in threads:thread.join(timeout=5)
    app.router.lifespan_context=lifespan
    return app


if __name__=='__main__':
    import uvicorn
    uvicorn.run(build_app(),host=os.environ.get('NATIVE_BIND_HOST','127.0.0.1'),port=int(os.environ.get('NATIVE_PORT','8090')),access_log=False)
