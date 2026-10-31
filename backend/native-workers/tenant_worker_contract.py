"""Acceptance-only: actual worker entrypoint, persisted IAM and real gVisor runners.

Refuses non-acceptance Supabase. No provider/customer operation or production
activation is performed. Output is fixed scenario labels, booleans and counts.
"""
from __future__ import annotations
from dataclasses import asdict, replace
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from broker_process_contract import IndependentFixture
from app.services.native_runtime.docker_runner import DockerRunner, SandboxImages
from app.services.native_runtime.store import Journal
from app.services.native_agent_adapters import AdapterScope

ACCEPTANCE='https://aadnwmjzrmbvadszroqt.supabase.co'
PAGE=b'''<!doctype html><title>Native acceptance fixture</title><h1>Ready</h1>
<button id="commit" type="button">Commit synthetic change</button>
<p id="result">No change</p><p id="revision">Original</p>
<script>const cap=location.hash.slice(1);history.replaceState(null,'',location.pathname);
document.querySelector('#commit').onclick=()=>fetch('/write',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cap})}).then(r=>{if(!r.ok)throw Error('denied');document.querySelector('#result').textContent='Written'});
setInterval(()=>fetch('/state').then(r=>r.json()).then(s=>{const t=s.mutated?'Changed':'Original';const n=document.querySelector('#revision');if(n.textContent!==t)n.textContent=t}),100)</script>'''



class AcceptanceCredentialError(ValueError):
    def __init__(self,name):
        self.credential_name=name
        super().__init__('Acceptance API credential is not a valid HTTP header token')


def normalize_acceptance_headers(environment):
    normalized=[]
    for name in ('E2E_SUPABASE_ANON_KEY','E2E_SUPABASE_SERVICE_ROLE_KEY'):
        raw=environment.get(name,'');clean=raw.strip()
        if not clean or any(ord(character)<33 or ord(character)>126 for character in clean):
            raise AcceptanceCredentialError(name)
        if raw!=clean:normalized.append(name)
        environment[name]=clean
    return normalized


def wait_for(predicate, seconds, category):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        time.sleep(.25)
    raise TimeoutError(category)


def terminal_wait_budget(case):
    """Allow slower CI browser execution without changing worker lease or write gates.

    Lost acknowledgements add a retry-and-readback path. The original 60-second
    terminal wait was a harness deadline, not an execution authorization limit.
    """
    return 150 if case in ('lost_submit_ack','lost_approval_ack') else 100 if case.startswith('broker_crash') else 60


def docker(*args):
    return subprocess.check_output(['docker',*args],stderr=subprocess.DEVNULL,timeout=120).decode().strip()


def publish(tag):
    name='127.0.0.1:5050/'+tag;docker('tag',tag,name);docker('push',name)
    return json.loads(docker('image','inspect',name,'--format','{{json .RepoDigests}}'))[0]


def worker_main(adapter):
    import uvicorn
    from app.services.native_runtime.worker import build_app
    def factory(images):
        if adapter=='playwright':
            return DockerRunner(replace(images,playwright_comparison=os.environ['CERT_PLAYWRIGHT_IMAGE']),
                                comparison_url=os.environ['CERT_FIXTURE_URL'])
        return DockerRunner(images)
    uvicorn.run(build_app(runner_factory=factory),host='127.0.0.1',port=int(os.environ['CERT_WORKER_PORT']),
                access_log=False,log_level='warning')


class Model:
    def __init__(self,root,url):
        self.url=url;self.token=secrets.token_urlsafe(32)
        self.click_proposed_for=None
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                assert self.path=='/v1/chat/completions'
                assert self.headers.get('Authorization')=='Bearer '+owner.token
                n=int(self.headers['Content-Length']);assert 0<n<=262144
                body=json.loads(self.rfile.read(n));state=''
                for message in reversed(body.get('messages',[])):
                    text=message.get('content','')
                    if not isinstance(text,str):continue
                    sections=re.findall(r'<browser_state>\n(.*?)\n</browser_state>',text,re.S)
                    if message.get('role')=='user' and sections:state=sections[-1];break
                active=re.search(r'^Current tab: ([A-Za-z0-9_-]+)\s*$',state,re.M)
                tab=re.search(r'^Tab '+re.escape(active.group(1))+r': (\S+) - ',state,re.M) if active else None
                seen=urlsplit(tab.group(1)) if tab else None;expected=urlsplit(owner.url)
                same=bool(seen) and seen.scheme=='https' and seen.netloc==expected.netloc and seen.path=='/page'
                dom=state.partition('Interactive elements')[2]
                target=re.search(r'\[(\d+)\]<button\b[^\n]*\bid=commit\b',dom)
                # The result paragraph is noninteractive and may appear before
                # the Interactive elements section. The prior test model missed
                # that readback, proposed a second click and left it pending.
                # Never propose the same externally mutating click twice.
                observed_written=same and bool(re.search(r'\\bWritten\\b',state))
                if observed_written:
                    action=[{'done':{'text':'Owned fixture readback complete','success':True}}]
                elif same and owner.click_proposed_for==owner.url:
                    action=[{'wait':{'seconds':1}}]
                elif same and target:
                    owner.click_proposed_for=owner.url
                    action=[{'click':{'index':int(target.group(1))}}]
                elif same:
                    action=[{'wait':{'seconds':1}}]
                else:
                    action=[{'navigate':{'url':owner.url}}]
                content=json.dumps({'evaluation_previous_goal':'Observe owned fixture','memory':'Only the approved fixture is in scope',
                    'next_goal':'Read back the reviewed fixture effect','action':action})
                data=json.dumps({'id':'fixture','object':'chat.completion','created':1,'model':'fixture-native',
                    'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}],
                    'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}).encode()
                try:
                    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                except OSError:pass
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=host.docker.internal',
            '-addext','subjectAltName=DNS:host.docker.internal','-addext','basicConstraints=critical,CA:TRUE',
            '-keyout',str(root/'key.pem'),'-out',str(root/'fixture.crt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        bridge=DockerRunner.private_ipv4(docker('network','inspect','bridge','--format','{{(index .IPAM.Config 0).Gateway}}'))
        self.server=ThreadingHTTPServer((bridge,0),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(root/'fixture.crt',root/'key.pem')
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        (root/'Dockerfile').write_text('FROM native-gateway\nUSER root\nCOPY fixture.crt /usr/local/share/ca-certificates/native-fixture.crt\nRUN update-ca-certificates\nUSER 10001:10001\n')
        subprocess.run(['docker','build','-q','-t','native-tenant-gateway',str(root)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.route={'provider':'openai','model':'fixture-native','base_url':f'https://host.docker.internal:{self.server.server_port}/v1',
                    'api_key':self.token,'budget_usd':2.0,'input_usd_per_million':1.0,'output_usd_per_million':1.0}
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)


class Worker:
    def __init__(self,root,adapter,base_env,scope,actor,client):
        from app.config import get_settings
        from app.services.native_runtime.control import IntakeSigner
        from app.services.tool_types import ToolContext
        self.adapter=adapter;self.environment=dict(base_env);self.scope=scope;self.actor=actor;self.client=client
        self.path=str(root/'journal.sqlite3')
        from cryptography.fernet import Fernet
        self.key=Fernet.generate_key()
        self.environment.update(NATIVE_JOURNAL_PATH=self.path,NATIVE_JOURNAL_KEY=self.key.decode(),
                                NATIVE_CORRELATION_KEY=secrets.token_hex(32))
        with socket.socket() as s:s.bind(('127.0.0.1',0));self.port=s.getsockname()[1]
        self.environment['CERT_WORKER_PORT']=str(self.port)
        self.signer=IntakeSigner(base_env['NATIVE_WORKER_SIGNING_KEY'])
        self.settings=get_settings();self.capture=root/'worker-private.log';self.process=None
        try:self.start()
        except BaseException:
            self.close();raise
    def start(self):
        self.stream=open(self.capture,'ab')
        self.process=subprocess.Popen([sys.executable,__file__,'--worker',self.adapter],env=self.environment,
            stdin=subprocess.DEVNULL,stdout=self.stream,stderr=self.stream,start_new_session=True)
        def ready():
            if self.process.poll() is not None:raise RuntimeError('worker_startup_failed')
            try:urlopen(f'http://127.0.0.1:{self.port}/v1/invoke',timeout=1)
            except HTTPError as e:return e.code==405
            except OSError:return False
        wait_for(ready,60,'worker_readiness_timeout')
        self.journal=Journal(self.path,self.key)
    def kill(self):
        old=self.process.pid;os.kill(old,signal.SIGKILL);self.process.wait(timeout=10)
        assert self.process.returncode==-signal.SIGKILL;self.stream.close();return old
    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        self.stream.close()
    def envelope(self,operation,payload,ref,scope=None):
        from app.services.tool_types import ToolContext
        from app.services.write_authority import WriteAuthority
        s=scope or self.scope
        context=ToolContext(self.settings,self.client,s.org_id,self.actor,agent_id=s.agent_id,run_id=s.run_id)
        return self.signer.sign(context,operation,payload,authority=WriteAuthority('human',ref))
    def call(self,operation,payload,ref=None,*,scope=None,drop_ack=False,bad_token=False,expired=False,tamper=False):
        token=self.envelope(operation,payload,ref or str(uuid4()),scope)
        if bad_token:
            prefix,signature=token.rsplit('.',1)
            token=prefix+'.'+('A' if signature[0]!='A' else 'B')+signature[1:]
        if expired:
            import jwt
            claims=jwt.decode(token,options={'verify_signature':False});claims['exp']=int(time.time())-10
            token=jwt.encode(claims,self.signer.key,algorithm='HS256')
        sent={**payload,'task':payload['task']+' changed'} if tamper else payload
        raw=json.dumps({'operation':operation,'payload':sent}).encode()
        if drop_ack:
            with socket.create_connection(('127.0.0.1',self.port),timeout=10) as connection:
                connection.sendall((f'POST /v1/invoke HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {token}\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\nConnection: close\r\n\r\n').encode()+raw)
            return None
        request=Request(f'http://127.0.0.1:{self.port}/v1/invoke',data=raw,
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=30) as response:return response.status,json.loads(response.read(262144))
        except HTTPError as error:return error.code,{}
    def actions(self,id):return self.journal.actions(self.scope,id)
    def approve(self,id,action,approved=True,drop_ack=False):
        return self.call('approve_native_action',{'job_id':id,'request_id':action['id'],'digest':action['digest'],'approved':approved},drop_ack=drop_ack)


def run():
    stage='acceptance_preflight';rows=[];case_counts=[];private_captures=[];user=None;orgs=[];admin=None;logged=None;fixture=None;tunnel=None;model=None;worker=None
    temporary=None;stream=None
    target=Path(os.environ.get('NATIVE_TENANT_EVIDENCE','native-tenant-worker-evidence.json'))
    report={'schema_version':1,'git_sha':os.environ.get('CERT_HEAD_SHA',os.environ.get('GITHUB_SHA','local')),'status':'BLOCKED','scenarios':rows,
            'live_customer_data':False,'external_provider_inference':False,'production_adapter_switch':False}
    try:
        required=('E2E_SUPABASE_URL','E2E_SUPABASE_ALLOWED_URL','E2E_SUPABASE_SERVICE_ROLE_KEY','E2E_SUPABASE_ANON_KEY','E2E_SUPABASE_JWT_SECRET')
        if any(not os.environ.get(k) for k in required):raise RuntimeError('missing_acceptance_secret')
        if os.environ['E2E_SUPABASE_URL'].rstrip('/')!=ACCEPTANCE or os.environ['E2E_SUPABASE_ALLOWED_URL'].rstrip('/')!=ACCEPTANCE:
            raise RuntimeError('non_acceptance_target_blocked')
        stage='acceptance_credential_headers'
        report['normalized_outer_whitespace_fields']=normalize_acceptance_headers(os.environ)
        stage='acceptance_database_preflight'
        os.environ.update(APP_ENV='dev',SUPABASE_URL=ACCEPTANCE,SUPABASE_SERVICE_ROLE_KEY=os.environ['E2E_SUPABASE_SERVICE_ROLE_KEY'],
            SUPABASE_ANON_KEY=os.environ['E2E_SUPABASE_ANON_KEY'],SUPABASE_JWT_SECRET=os.environ['E2E_SUPABASE_JWT_SECRET'])
        from supabase import create_client
        from app.core.db import shared_http_options
        stage='acceptance_service_client_construction'
        admin=create_client(ACCEPTANCE,os.environ['E2E_SUPABASE_SERVICE_ROLE_KEY'],options=shared_http_options())
        for table in ('organizations','organization_members','agents','agent_tool_permissions'):
            stage='acceptance_schema_'+table
            admin.table(table).select('id').limit(0).execute()
        stage='disposable_tenant_authentication'
        password=secrets.token_urlsafe(32);email='native-'+uuid4().hex+'@example.invalid'
        user=admin.auth.admin.create_user({'email':email,'password':password,'email_confirm':True}).user.id
        logged=create_client(ACCEPTANCE,os.environ['E2E_SUPABASE_ANON_KEY'],options=shared_http_options())
        session=logged.auth.sign_in_with_password({'email':email,'password':password})
        assert logged.auth.get_user(session.session.access_token).user.id==user
        for _ in range(2):
            id=str(uuid4());admin.table('organizations').insert({'id':id,'name':'Disposable native certification','slug':'native-'+uuid4().hex}).execute();orgs.append(id)
        member=admin.table('organization_members').insert({'org_id':orgs[0],'user_id':user,'role':'owner'}).execute().data[0]
        agents=[]
        for org in orgs:
            id=str(uuid4());admin.table('agents').insert({'id':id,'org_id':org,'name':'Disposable native certification','created_by':user}).execute();agents.append(id)
        grant=admin.table('agent_tool_permissions').insert({'org_id':orgs[0],'agent_id':agents[0],'connector_type':'platform',
            'scopes':['platform:native:execute','platform:native:read'],'granted_by':user,
            'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}).execute().data[0]
        assert logged.table('agents').select('id').eq('id',agents[0]).execute().data==[{'id':agents[0]}]
        assert logged.table('agents').select('id').eq('id',agents[1]).execute().data==[]
        rows.append({'scenario':'authenticated_actor_and_cross_tenant_rls','passed':True})
        temporary=tempfile.TemporaryDirectory(prefix='native-tenant-')
        root=Path(temporary.name);cap=secrets.token_hex(32)
        fixture=IndependentFixture(root/'effects.sqlite3',PAGE,capability=cap)
        tunnel_log=root/'tunnel-private.log';stream=open(tunnel_log,'wb')
        tunnel=subprocess.Popen([os.environ['CLOUDFLARED_BIN'],'tunnel','--no-autoupdate','--protocol','http2','--url',fixture.origin],
            stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,start_new_session=True,
            env={key:os.environ[key] for key in ('PATH','HOME','TMPDIR','LANG','SSL_CERT_FILE','SSL_CERT_DIR') if key in os.environ})
        def origin_ready():
            stream.flush();text=tunnel_log.read_text(errors='replace')
            matches=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',text)
            found=next((u for u in matches if urlsplit(u).hostname not in {'api.trycloudflare.com','www.trycloudflare.com'}),None)
            if not found:return False
            try:
                with urlopen(found+'/page',timeout=5) as response:
                    return found if response.status==200 else False
            except OSError:return False
        stage='owned_https_fixture_readiness';origin=wait_for(origin_ready,90,'https_fixture_unavailable')
        fixture_url=origin+'/page#'+cap;host=urlsplit(origin).hostname
        model_root=root/'model';model_root.mkdir(mode=0o700);model=Model(model_root,fixture_url)
        images=SandboxImages(publish('native-openhands'),publish('native-browser'),publish('native-tenant-gateway'),
                             playwright_comparison=publish('native-playwright-comparison'))
        base_env={**os.environ,'APP_ENV':'dev','PYTHONPATH':str(Path(__file__).resolve().parents[1]),
            'NATIVE_OPENHANDS_IMAGE':images.openhands,'NATIVE_BROWSER_IMAGE':images.browser_use,'NATIVE_GATEWAY_IMAGE':images.gateway,
            'NATIVE_SANDBOX_RUNTIME':'runsc','NATIVE_WORKER_SIGNING_KEY':secrets.token_hex(32),
            'CERT_PLAYWRIGHT_IMAGE':images.playwright_comparison,'CERT_FIXTURE_URL':fixture_url,
            'NATIVE_TENANTS_JSON':json.dumps({orgs[0]:{'processing_permission':{'owner':user,'reference':'authorized-disposable-native-certification',
                'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},'model':model.route}})}
        report['images']=asdict(images)
        report['source_sha256']={name:hashlib.sha256((Path(__file__).resolve().parents[1]/'app/services/native_runtime'/name).read_bytes()).hexdigest() for name in ('worker.py','runtime.py','control.py','docker_runner.py','store.py')}
        cleaner=DockerRunner(images)
        cases=('approved','denied','cancelled','grant_revoked','membership_revoked','stale_fingerprint',
               'engine_crash','gateway_crash','broker_crash_before_dispatch','broker_crash_after_effect','lost_submit_ack','lost_approval_ack')
        report['required_scenarios']=list(cases)
        for adapter in ('browser_use','playwright'):
            adapter_root=root/adapter;adapter_root.mkdir(mode=0o700)
            worker=None;owned_jobs=[]
            try:
                for case in cases:
                    if worker is not None:worker.close();worker=None
                    case_cap=secrets.token_hex(32);fixture.register_capability(case_cap)
                    case_url=origin+'/page#'+case_cap;model.url=case_url
                    case_root=adapter_root/case;case_root.mkdir(mode=0o700)
                    private_captures.append(case_root/'worker-private.log')
                    stage=adapter+':'+case+':worker_startup'
                    worker=Worker(case_root,adapter,{**base_env,'CERT_FIXTURE_URL':case_url},AdapterScope(orgs[0],agents[0],str(uuid4())),user,admin)
                    stage=adapter+':'+case
                    worker.scope=AdapterScope(orgs[0],agents[0],str(uuid4()))
                    fixture.mutated=False;fixture.hold=case=='broker_crash_after_effect'
                    before=fixture.count(case_cap);assert before==0
                    payload={'task':f'Use only {case_url}; click Commit once and read back Written.','allowed_hosts':[host]}
                    authority=str(uuid4())
                    if case=='approved':
                        assert worker.call('run_browser_use',payload,scope=AdapterScope(orgs[1],agents[1],str(uuid4())))[0]==403
                        assert worker.call('run_browser_use',payload,bad_token=True)[0]==403
                        assert worker.call('run_browser_use',payload,expired=True)[0]==403
                        assert worker.call('run_browser_use',payload,tamper=True)[0]==403
                        assert worker.call('run_browser_use',{**payload,'allowed_hosts':['host.docker.internal']})[0]==403
                        admin.table('agent_tool_permissions').update({'expires_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}).eq('id',grant['id']).execute()
                        assert worker.call('run_browser_use',payload)[0]==403
                        admin.table('agent_tool_permissions').update({'expires_at':grant['expires_at']}).eq('id',grant['id']).execute()
                        admin.table('agent_tool_permissions').update({'scopes':['platform:native:read']}).eq('id',grant['id']).execute()
                        assert worker.call('run_browser_use',payload)[0]==403
                        admin.table('agent_tool_permissions').update({'scopes':['platform:native:read','platform:native:execute']}).eq('id',grant['id']).execute()
                    with worker.journal.connect() as db:
                        assert db.execute('SELECT COUNT(*) FROM jobs WHERE run=?',(worker.scope.run_id,)).fetchone()[0]==0
                    if case=='lost_submit_ack':
                        worker.call('run_browser_use',payload,authority,drop_ack=True)
                        def persisted():
                            with worker.journal.connect() as db:
                                row=db.execute('SELECT id FROM jobs WHERE run=?',(worker.scope.run_id,)).fetchone()
                                return row['id'] if row else False
                        persisted_id=wait_for(persisted,15,'lost_ack_submission_not_persisted')
                    status,submitted=worker.call('run_browser_use',payload,authority);assert status==200
                    id=submitted['job_id'];owned_jobs.append(id)
                    if case=='lost_submit_ack':assert id==persisted_id
                    def pending(sequence):
                        values=worker.actions(id)
                        return values[sequence] if len(values)>sequence and values[sequence]['state']=='pending' else False
                    nav=wait_for(lambda:pending(0),90,'navigation_approval_not_reached')
                    assert set(nav['action']['actions'])=={'navigate'}
                    assert worker.approve(id,nav)[0]==200
                    click=wait_for(lambda:pending(1),90,'click_approval_not_reached')
                    assert set(click['action']['actions'])=={'click'}
                    if case=='approved':
                        # Exercise actual job gateway from inside the actual engine.
                        probe="import socket; s=socket.create_connection(('gateway',8080),timeout=5); s.sendall(b'CONNECT denied.invalid:443 HTTP/1.1\\r\\nHost: denied.invalid\\r\\n\\r\\n'); print(s.recv(1024).split(b'\\r\\n')[0].decode()); s.close()"
                        assert '403' in docker('exec',cleaner.names(id)[1],'python','-c',probe)
                        token_probe="import socket; s=socket.create_connection(('gateway',8080),timeout=5); s.sendall(b'POST /authorize HTTP/1.1\\r\\nHost: gateway\\r\\nAuthorization: Bearer invalid-job-token\\r\\nContent-Length: 2\\r\\n\\r\\n{}'); print(s.recv(1024).split(b'\\r\\n')[0].decode()); s.close()"
                        assert '403' in docker('exec',cleaner.names(id)[1],'python','-c',token_probe)
                        wrong={**click,'digest':'0'*64}
                        assert worker.approve(id,wrong)[0]==403
                        assert worker.actions(id)[1]['state']=='pending' and fixture.count(case_cap)==before
                    if case=='denied':assert worker.approve(id,click,False)[0]==200
                    elif case=='cancelled':assert worker.call('cancel_native_job',{'job_id':id})[0]==200
                    elif case=='grant_revoked':
                        admin.table('agent_tool_permissions').update({'scopes':['platform:native:read']}).eq('id',grant['id']).execute()
                        assert worker.approve(id,click)[0]==403
                    elif case=='membership_revoked':
                        admin.table('organization_members').delete().eq('id',member['id']).execute()
                        assert worker.approve(id,click)[0]==403
                    elif case in ('engine_crash','gateway_crash'):
                        docker('kill',cleaner.names(id)[1 if case=='engine_crash' else 2])
                    elif case=='broker_crash_before_dispatch':
                        old=worker.kill();worker.start();assert worker.process.pid!=old
                    else:
                        if case=='stale_fingerprint':
                            fixture.mutated=True;time.sleep(2)
                        approval=worker.approve(id,click,drop_ack=case=='lost_approval_ack')
                        if case!='lost_approval_ack':assert approval[0]==200
                        if case=='broker_crash_after_effect':
                            wait_for(lambda:fixture.count(case_cap)==before+1,15,'committed_effect_not_observed')
                            assert worker.journal.get(worker.scope,id)['state']=='running'
                            old=worker.kill();worker.start();assert worker.process.pid!=old
                            fixture.hold=False
                    crash=case.startswith('broker_crash')
                    def finished():
                        row=worker.journal.get(worker.scope,id)
                        if row['state'] in ('completed','failed','cancelled','uncertain'):
                            return row if not crash or row['phase']=='reconciled' else False
                        return False
                    # A dropped submit ACK can leave the client unaware of the
                    # accepted job. Keep the recovery boundary fail-closed, but
                    # preserve sanitized journal/worker diagnostics on timeout.
                    try:
                        result=wait_for(finished,terminal_wait_budget(case),'worker_terminal_or_reconciliation_timeout')
                    except TimeoutError:
                        row=worker.journal.get(worker.scope,id)
                        actions=worker.actions(id)
                        report['terminal_timeout_details']={
                            'adapter':adapter,'scenario':case,
                            'journal_state':row['state'] if row else 'missing',
                            'journal_phase':row['phase'] if row else 'missing',
                            'action_states':[action['state'] for action in actions],
                            'action_count':len(actions),
                            'worker_alive':worker.process.poll() is None,
                            'external_write_count':fixture.count(case_cap)-before,
                        }
                        raise
                    expected=1 if case in ('approved','broker_crash_after_effect','lost_submit_ack','lost_approval_ack') else 0
                    assert fixture.count(case_cap)-before==expected
                    if crash:assert result['state']=='uncertain'
                    elif expected:assert result['state']=='completed'
                    elif case in ('denied','cancelled'):assert result['state']=='cancelled'
                    else:assert result['state']=='failed'
                    if case=='membership_revoked':
                        admin.table('organization_members').insert(member).execute()
                    if case=='grant_revoked':
                        admin.table('agent_tool_permissions').update({'scopes':['platform:native:read','platform:native:execute']}).eq('id',grant['id']).execute()
                    if case=='lost_approval_ack':assert worker.approve(id,click)[0]==403
                    assert worker.call('run_browser_use',payload,authority)[1]['job_id']==id
                    assert worker.journal.get(worker.scope,id)['state']==result['state']
                    # Terminal journal state precedes the runner's finally cleanup.
                    # Observe its cleanup before exercising idempotency; concurrent
                    # removal would race the worker and obscure actual recovery.
                    def resources_removed():
                        return not docker('ps','-aq','--filter','label=gravitre.native.job='+id) and not docker('network','ls','-q','--filter','label=gravitre.native.job='+id)
                    wait_for(resources_removed,30,'worker_resource_cleanup_timeout')
                    cleaner.cleanup(id)
                    assert not docker('ps','-aq','--filter','label=gravitre.native.job='+id)
                    assert not docker('network','ls','-q','--filter','label=gravitre.native.job='+id)
                    time.sleep(.5);assert fixture.count(case_cap)-before==expected
                    case_counts.append((case_cap,expected))
                    rows.append({'adapter':adapter,'scenario':case,'passed':True,'state':result['state'],
                        'authorized_writes':expected,'observed_writes':fixture.count(case_cap)-before,'unauthorized_writes':0,
                        'replayed_jobs':0,'resources_cleaned':True,'actual_worker_entrypoint':True,
                        'persisted_tenant_authorization':True,'signed_api':True,'natural_lease_expiry':crash,
                        'http_acknowledgement_dropped':case in ('lost_submit_ack','lost_approval_ack','broker_crash_after_effect')})
            finally:
                if worker is not None:worker.close()
                for id in owned_jobs:cleaner.cleanup(id)
                worker=None
        assert len(case_counts)==2*len(cases)
        assert all(fixture.count(capability)==expected for capability,expected in case_counts)
        assert fixture.writes==sum(expected for _,expected in case_counts)
        report['independent_total_writes']=fixture.writes
        report['status']='PASS'
    except Exception as error:
        report.update(status='BLOCKED',failure_stage=stage,failure_class=type(error).__name__)
        report['failure_frames']=[{'file':Path(frame.filename).name,'line':frame.lineno,'function':frame.name} for frame in traceback.extract_tb(error.__traceback__)[-12:]]
        if isinstance(error,subprocess.CalledProcessError):
            report['subprocess_returncode']=error.returncode
            if isinstance(error.cmd,list) and len(error.cmd)>1 and error.cmd[0]=='docker' and error.cmd[1] in {'ps','network','rm','exec','kill','image','push','tag','build'}:
                report['docker_operation']=error.cmd[1]
        if isinstance(error,AcceptanceCredentialError):report['invalid_credential_name']=error.credential_name
        if type(error).__name__=='LocalProtocolError':report['header_value_rejected']='Illegal header value' in str(error)
        code=str(getattr(error,'code',''))
        if re.fullmatch(r'[A-Za-z0-9_-]{1,48}',code):report['failure_code']=code
        capture=worker.capture if worker is not None else (private_captures[-1] if private_captures else None)
        if capture is not None and capture.exists():
            content=capture.read_text(errors='replace')[-32768:]
            report['worker_failure_classes']=list(dict.fromkeys(re.findall(r'^(?:[A-Za-z_][A-Za-z0-9_]*\.)*([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):',content,re.M)))
            report['worker_failure_frames']=[{'file':Path(m[0]).name,'line':int(m[1]),'function':m[2]}
                for m in re.findall(r'File "([^"]+)", line (\d+), in ([A-Za-z0-9_<>]+)',content)[-12:]]
    finally:
        def cleanup(label,operation):
            try:operation()
            except Exception:
                report['status']='BLOCKED'
                report.setdefault('cleanup_failures',[]).append(label)
        if worker is not None:cleanup('worker',worker.close)
        if model is not None:cleanup('scripted_model',model.close)
        if tunnel is not None:
            def stop_tunnel():
                tunnel.terminate()
                try:tunnel.wait(timeout=10)
                except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait(timeout=5)
            cleanup('https_fixture_tunnel',stop_tunnel)
        if fixture is not None:
            def stop_receiver():
                fixture.hold=False;fixture.close()
                import sqlite3
                with sqlite3.connect('file:'+str(root/'effects.sqlite3')+'?mode=ro',uri=True) as db:
                    total=db.execute('SELECT COUNT(*) FROM writes').fetchone()[0]
                    if report['status']=='PASS' and total!=report['independent_total_writes']:
                        report.update(status='BLOCKED',failure_stage='late_receiver_effect_after_cleanup')
            cleanup('independent_receiver',stop_receiver)
        if stream is not None:cleanup('tunnel_capture',stream.close)
        if temporary is not None:cleanup('private_files',temporary.cleanup)
        if logged is not None:cleanup('actor_session',logged.auth.sign_out)
        if admin is not None:
            for org in orgs:
                cleanup('disposable_tenant',lambda org=org:admin.table('organizations').delete().eq('id',org).execute())
            if user:cleanup('disposable_actor',lambda:admin.auth.admin.delete_user(user))
        target.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,sort_keys=True))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker_main(sys.argv[2])
    else:
        def interrupted(*_):raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM,interrupted)
        raise SystemExit(run())
