"""Real gVisor + DockerRunner certification with a local scripted HTTPS model.

No provider credential, tenant record or external write is used. The browser
may read example.com after the fixture explicitly approves that exact action.
Only assertion names and sanitized outcomes are written as evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import concurrent.futures
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.native_runtime.docker_runner import DockerRunner,SandboxImages


def docker(*args):
    return subprocess.check_output(['docker',*args],stderr=subprocess.DEVNULL,timeout=120).decode().strip()


@dataclass(frozen=True)
class FixtureRoute:
    provider: str='openai'
    model: str='fixture-native'
    base_url: str=''
    api_key: str='fixture-only-not-a-provider-key'
    budget_usd: float=2.0
    input_usd_per_million: float=1.0
    output_usd_per_million: float=1.0
    max_output_tokens: int=4096
    def validate(self):
        assert self.base_url.startswith('https://host.docker.internal:')


PROBE="""python - <<'PYCODE'
import json,socket,os
from pathlib import Path
proof={}
for label,address in [('direct_egress','1.1.1.1'),('metadata','169.254.169.254'),('host_bridge','172.17.0.1')]:
 try:
  s=socket.create_connection((address,443),timeout=1);s.close();proof[label]=False
 except OSError:proof[label]=True
try:
 Path('/etc/native-fixture-escape').write_text('blocked');proof['readonly_root']=False
except OSError:proof['readonly_root']=True
proof['no_docker_socket']=not Path('/var/run/docker.sock').exists()
proof['no_provider_key']='fixture-only-not-a-provider-key' not in Path('/proc/self/environ').read_bytes().decode(errors='replace')
Path('/workspace/review.py').write_text(json.dumps(proof,sort_keys=True))
PYCODE"""


def run():
    evidence={};state={'kind':'openhands','calls':0};lock=threading.Lock();entered=threading.Event();cancel=threading.Event()
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            assert self.path=='/v1/chat/completions'
            assert self.headers.get('Authorization')=='Bearer fixture-only-not-a-provider-key'
            length=int(self.headers['Content-Length']);assert 0<length<=262144
            body=json.loads(self.rfile.read(length))
            assert body['model']=='fixture-native'
            with lock:state['calls']+=1;number=state['calls'];kind=state['kind']
            entered.set()
            if kind=='cancel':
                cancel.wait(30)
                time.sleep(2)
            message={'role':'assistant','content':'Fixture task finished.'};finish='stop'
            if kind=='browser_use':
                if number>1:
                    latest_user=next((m for m in reversed(body.get('messages',[])) if m.get('role')=='user'),{})
                    observed=json.dumps(latest_user.get('content',''))
                    state['browser_page_observed']='Example Domain' in observed and 'example.com' in observed
                    if not state['browser_page_observed']:
                        self.send_response(422);self.send_header('Content-Length','0');self.end_headers();return
                output={'evaluation_previous_goal':'Fixture browser is running','memory':'Only the approved public fixture page may be read','next_goal':'Finish the fixture','action':([{'navigate':{'url':'https://example.com/'}}] if number==1 else [{'done':{'text':'Fixture browser session completed','success':True}}])}
                message['content']=json.dumps(output)
            elif kind=='openhands':
                tools=[x['function'] for x in body.get('tools',[]) if x.get('type')=='function']
                if number==1:
                    tool=next(x for x in tools if 'command' in x.get('parameters',{}).get('properties',{}) and ('terminal' in x['name'] or 'bash' in x['name']))
                    message={'role':'assistant','content':None,'tool_calls':[{'id':'fixture-command','type':'function','function':{'name':tool['name'],'arguments':json.dumps({'command':PROBE})}}]};finish='tool_calls'
                else:
                    tool=next((x for x in tools if x['name']=='finish'),None)
                    if tool:
                        message={'role':'assistant','content':None,'tool_calls':[{'id':'fixture-finish','type':'function','function':{'name':tool['name'],'arguments':json.dumps({'message':'Fixture task finished.'})}}]};finish='tool_calls'
            raw=json.dumps({'id':'fixture-response','object':'chat.completion','created':1,'model':'fixture-native','choices':[{'index':0,'message':message,'finish_reason':finish}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}).encode()
            try:
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            except (OSError,ssl.SSLError):pass
    with tempfile.TemporaryDirectory(prefix='native-cert-') as temporary:
        root=Path(temporary)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=host.docker.internal','-addext','subjectAltName=DNS:host.docker.internal','-addext','basicConstraints=critical,CA:TRUE','-keyout',str(root/'key.pem'),'-out',str(root/'fixture.crt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        # Only the trusted gateway receives the fixture CA, never its key.
        (root/'Dockerfile').write_text('FROM native-gateway\nUSER root\nCOPY fixture.crt /usr/local/share/ca-certificates/native-fixture.crt\nRUN update-ca-certificates\nUSER 10001:10001\n')
        subprocess.run(['docker','build','-q','-t','native-gateway-fixture',str(root)],check=True,stdout=subprocess.DEVNULL)
        server=ThreadingHTTPServer(('0.0.0.0',0),Provider)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(root/'fixture.crt',root/'key.pem');server.socket=context.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        route=FixtureRoute(base_url=f'https://host.docker.internal:{server.server_port}/v1')
        registry='127.0.0.1:5050'
        def publish(tag):
            name=registry+'/'+tag;docker('tag',tag,name);docker('push',name)
            digest=json.loads(docker('image','inspect',name,'--format','{{json .RepoDigests}}'))[0]
            assert '@sha256:' in digest
            return digest
        images=SandboxImages(publish('native-openhands'),publish('native-browser'),publish('native-gateway-fixture'))
        captures=[]
        def process_factory(args,**kwargs):
            stream=tempfile.TemporaryFile(mode='w+b')
            captures.append(stream)
            kwargs['stderr']=stream
            return subprocess.Popen(args,**kwargs)
        class ObservedRunner(DockerRunner):
            def cleanup(self,id):
                for container in self.names(id)[1:]:
                    try:
                        state=json.loads(docker('inspect','--format','{{json .State}}',container))
                        networks=json.loads(docker('inspect','--format','{{json .NetworkSettings.Networks}}',container))
                        print(json.dumps({'fixture_container':'gateway' if 'gateway' in container else 'engine','state':state.get('Status'),'exit_code':state.get('ExitCode'),'runtime_error':str(state.get('Error',''))[:1600],'network_addresses':[n.get('IPAddress') for n in networks.values()]}))
                    except subprocess.CalledProcessError:pass
                return super().cleanup(id)
        runner=ObservedRunner(images,process_factory=process_factory)
        def diagnostic():
            # Fixture-only diagnostics: no task, model response, exception body,
            # token or credential is printed. Keep only public stack locations
            # and exception class names, then close the private capture.
            for stream in captures:
                stream.flush();stream.seek(0)
                for line in stream.read(262144).decode(errors='replace').splitlines():
                    try:
                        entry=json.loads(line)
                        if isinstance(entry,dict) and set(entry) in ({'gateway_failure_stage','gateway_failure_class','known_parameter_flags'},{'browser_error_codes','browser_error_classes'},{'browser_failure_stage','browser_failure_class','frames'},{'browser_evidence_changed','url_changed','decoded_pixels_changed','screenshot_bytes_changed','dom_changed','title_changed','targets_changed'}):
                            print(json.dumps(entry))
                    except (ValueError,TypeError):pass
                    match=re.match(r'\s*File "([^"]+)", line (\d+), in ([A-Za-z0-9_<>]+)',line)
                    if match:print(json.dumps({'sdk_frame':Path(match[1]).name,'line':int(match[2]),'function':match[3]}))
                    match=re.match(r'^(?:[A-Za-z_][A-Za-z0-9_]*\.)*([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):',line)
                    if match:print(json.dumps({'sdk_exception':match[1]}))
                    for phrase,code in [('name or service not known','dns_unavailable'),('temporary failure in name resolution','dns_unavailable'),('connection refused','connection_refused'),('network is unreachable','network_unreachable'),('timed out','connection_timeout'),('no usable sandbox','chromium_sandbox_unavailable'),('failed to move to new namespace','chromium_namespace_denied'),('operation not permitted','operation_not_permitted'),('browser is not connected','browser_not_connected'),('executable doesn\'t exist','chromium_executable_missing')]:
                        if phrase in line.lower():print(json.dumps({'sdk_transport':code}))
                stream.close()
        def job(kind):
            return {'id':str(uuid4()),'kind':kind,'payload':{'task':{'task':'Execute only this fixed certification fixture. Make no external changes.','files':{'review.py':''} if kind=='openhands' else {},'allowed_hosts':['example.com'] if kind=='browser_use' else [],'max_seconds':180,'max_steps':5}}}
        def clean(id):
            assert not docker('ps','-aq','--filter','label=gravitre.native.job='+id)
            assert not docker('network','ls','-q','--filter','label=gravitre.native.job='+id)
        try:
            software=job('openhands');result=runner.execute(software,guard=lambda:route,action_gate=lambda *_:(_ for _ in ()).throw(AssertionError('Unexpected browser action')))
            patch=result.get('patch','')
            for key in ['direct_egress','metadata','host_bridge','readonly_root','no_docker_socket','no_provider_key']:assert f'"{key}": true' in patch,key
            clean(software['id']);evidence['openhands_real_sdk_patch_and_isolation']='PASS'
            print(json.dumps({'completed_runtime_checks':evidence},sort_keys=True))
            state.update(kind='browser_use',calls=0,browser_page_observed=False);approved=[]
            def action_gate(sequence,action):
                assert action['actions']=={'navigate':{'url':'https://example.com/'}}
                assert len(action['page_fingerprint'])==64
                approved.append(sequence);return {'state':'approved'}
            browser=job('browser_use')
            try:result=runner.execute(browser,guard=lambda:route,action_gate=action_gate)
            finally:print(json.dumps({'fixture_browser_model_requests':state['calls'],'fixture_browser_approvals':len(approved),'fixture_browser_page_observed':state['browser_page_observed']}))
            assert approved and state['browser_page_observed'] and result.get('observations')
            clean(browser['id']);evidence['browser_real_sdk_chromium_exact_approval']='PASS'
            print(json.dumps({'completed_runtime_checks':evidence},sort_keys=True))
            state.update(kind='cancel',calls=0);entered.clear();cancel.clear();cancelled=job('openhands')
            def guard():
                if cancel.is_set():raise PermissionError('fixture_cancelled')
                return route
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(runner.execute,cancelled,guard=guard,action_gate=lambda *_:None)
                assert entered.wait(90),'Engine never reached the fixture model'
                cancel.set()
                try:future.result(timeout=45)
                except PermissionError:pass
                else:raise AssertionError('Cancelled execution returned a result')
            clean(cancelled['id']);evidence['cancellation_fences_and_removes_sandbox']='PASS'
            # Cleanup is idempotent and cannot resurrect a lost worker.
            runner.cleanup(cancelled['id']);clean(cancelled['id']);evidence['recovery_cleanup_idempotent']='PASS'
        finally:
            cancel.set();server.shutdown();server.server_close();thread.join(timeout=5);diagnostic()
        evidence.update(schema_version=1,runtime='runsc',runsc_version=subprocess.check_output(['runsc','--version'],text=True).splitlines()[0],git_sha=os.environ.get('GITHUB_SHA','local'),external_provider_requests=False,live_tenant_data=False)
        target=Path(os.environ.get('NATIVE_CERT_EVIDENCE','native-runtime-evidence.json'));target.write_text(json.dumps(evidence,indent=2)+'\n')
        print(json.dumps(evidence,sort_keys=True))


if __name__=='__main__':run()
