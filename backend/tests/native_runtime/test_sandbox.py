from dataclasses import asdict
import io
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from app.services.native_runtime.docker_runner import DockerRunner,SandboxImages
from app.services.native_runtime.runtime import ModelRoute
from app.services.native_runtime import gateway,network

IMAGES=SandboxImages('registry/oh@sha256:'+'1'*64,'registry/browser@sha256:'+'2'*64,'registry/gateway@sha256:'+'3'*64)

class Input:
    def __init__(self):self.data=b''
    def write(self,data):self.data+=data
    def close(self):pass
class Process:
    def __init__(self,done):self.stdin=Input();self.returncode=0 if done else None
    def poll(self):return self.returncode
    def kill(self):self.returncode=-9
    def wait(self,**_):return self.returncode

@pytest.mark.parametrize('result_body,invalid',[
    (b'{"observations":[{"summary":"draft"}],"patch":"example"}',False),
    (b'',True),(b'[]',True),(b'not-json',True),(b'x'*240001,True),
])
def test_exact_sandbox_policy_secret_isolation_and_cleanup(monkeypatch,result_body,invalid):
    monkeypatch.setattr('socket.getfqdn',lambda *_:'localhost')
    monkeypatch.setattr('socket.getaddrinfo',lambda *_args,**_kwargs:[(None,None,None,None,('8.8.8.8',443))])
    commands=[];processes=[];containers=[];networks=[];inspections=[]
    jobid=str(uuid4())
    def docker(args,**kwargs):
        commands.append(args)
        op=args[1]
        if op=='info':return SimpleNamespace(stdout=b'{"runsc":{}}')
        if op=='inspect':
            inspections.append(True)
            return SimpleNamespace(stdout=b'' if len(inspections)==1 else b'172.28.0.2')
        if op=='ps':return SimpleNamespace(stdout='\n'.join(containers).encode())
        if op=='rm':containers.clear()
        if op in ('run','create'):containers.append(args[args.index('--name')+1])
        if op=='network':
            if args[2]=='inspect':return SimpleNamespace(stdout=b'172.17.0.1')
            if args[2]=='ls':return SimpleNamespace(stdout='\n'.join(networks).encode())
            if args[2]=='create':networks.append(args[-1])
            if args[2]=='rm':networks.clear()
        if op=='exec' and '/out/result.json' in args[-1]:return SimpleNamespace(stdout=result_body)
        return SimpleNamespace(stdout=b'')
    def process(args,**kwargs):
        result=Process(args[-1]=='/runner/engine.py');processes.append((args,result));return result
    runner=DockerRunner(IMAGES,command=docker,process_factory=process)
    model=ModelRoute('openai','configured','https://model.example/v1','PROVIDER-SECRET',1,1,1)
    job={'id':jobid,'kind':'openhands','payload':{'task':{'task':'bounded','files':{},'allowed_hosts':[],'max_seconds':5,'max_steps':2}}}
    if invalid:
        with pytest.raises(ValueError):runner.execute(job,guard=lambda:model,action_gate=Mock())
    else:
        result=runner.execute(job,guard=lambda:model,action_gate=Mock())
        assert result['patch']=='example'
    assert not containers and not networks
    assert len(inspections)==2
    connect=next(i for i,c in enumerate(commands) if c[1:3]==['network','connect'])
    start=next(i for i,c in enumerate(commands) if c[1]=='start')
    assert connect<start
    flat=repr(commands)
    assert 'PROVIDER-SECRET' not in flat and 'PROVIDER-SECRET' not in repr(processes[1][1].stdin.data)
    assert b'PROVIDER-SECRET' in processes[0][1].stdin.data
    assert not any(command[1]=='cp' for command in commands)
    assert 'f.read(240001)' in flat
    assert '--privileged' not in flat and 'docker.sock' not in flat
    assert 'com.docker.network.bridge.gateway_mode_ipv4=isolated' in flat
    assert '--read-only' in flat and '--cap-drop=ALL' in flat and 'no-new-privileges' in flat
    assert '--dns' in flat and '127.0.0.1' in flat
    assert 'gateway:172.28.0.2' in flat
    assert 'host.docker.internal:172.17.0.1' in flat and 'host-gateway' not in flat
    assert '--signal=KILL' in flat and '--pids-limit' in flat and '--memory' in flat
    engine=next(c for c in commands if c[1]=='run' and c[c.index('--name')+1]=='native-engine-'+jobid)
    assert engine[engine.index('--network')+1]=='native-'+jobid
    assert engine[engine.index('--runtime')+1]=='runsc'

def test_no_unpinned_image_or_insecure_runtime():
    with pytest.raises(ValueError):SandboxImages('latest','latest','latest').validate()
    with pytest.raises(ValueError):SandboxImages(IMAGES.openhands,IMAGES.browser_use,IMAGES.gateway,'runc').validate()

@pytest.mark.parametrize('address',['127.0.0.1','10.1.2.3','169.254.169.254','::1','fc00::1','192.0.2.1'])
def test_dns_escape_rebinding_and_private_routes_are_denied(monkeypatch,address):
    monkeypatch.setattr(network.socket,'getaddrinfo',lambda *_args,**_kwargs:[(None,None,None,None,(address,443))])
    with pytest.raises(ValueError):network.public_addresses('allowed.example')

def test_mixed_public_private_dns_and_url_creds_are_denied(monkeypatch):
    monkeypatch.setattr(network.socket,'getaddrinfo',lambda *_args,**_kwargs:[(None,None,None,None,('8.8.8.8',443)),(None,None,None,None,('10.0.0.1',443))])
    with pytest.raises(ValueError):network.public_addresses('allowed.example')
    for url in ['https://user:secret@allowed.example','https://allowed.example:8443','http://allowed.example','https://other.example','https://allowed.example\\evil']:
        with pytest.raises(ValueError):network.approved_url(url,['allowed.example'])

@pytest.mark.parametrize('token_field',['max_tokens','max_completion_tokens'])
def test_gateway_fixed_route_budget_no_redirect_and_no_exception_leak(monkeypatch,token_field):
    config={'engine_token':'job-token','model':'approved','max_output_tokens':20,'max_calls':1,'budget_usd':1,'input_usd_per_million':1,'output_usd_per_million':1,'base_url':'https://fixed.example/v1','api_key':'PRIVATE-KEY'}
    monkeypatch.setattr(gateway,'CONFIG',config);monkeypatch.setattr(gateway,'CALLS',0);monkeypatch.setattr(gateway,'SPENT',0)
    monkeypatch.setattr(gateway,'control',lambda *_:{'authorized':True})
    upstream=Mock();upstream.getresponse.return_value=SimpleNamespace(status=200,read=lambda _:b'{"choices":[]}')
    connection=Mock(return_value=upstream);monkeypatch.setattr(gateway.http.client,'HTTPSConnection',connection)
    def send(body):
        handler=object.__new__(gateway.Handler);raw=json.dumps(body).encode()
        handler.headers={'Authorization':'Bearer job-token','Content-Length':str(len(raw))};handler.rfile=io.BytesIO(raw);handler.wfile=io.BytesIO();handler.path='/v1/chat/completions'
        handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock()
        handler.do_POST();return handler
    first=send({'model':'model-chosen-by-attacker','messages':[{'role':'user','content':'hello'}],token_field:100,'reasoning_effort':'low','prompt_cache_key':'PRIVATE-CACHE-CONTEXT','prompt_cache_retention':'24h'})
    assert first.send_response.call_args.args[0]==200
    forwarded=json.loads(upstream.request.call_args.kwargs['body'])
    assert forwarded['model']=='approved'
    assert 'prompt_cache_key' not in forwarded and 'prompt_cache_retention' not in forwarded
    assert b'PRIVATE-CACHE-CONTEXT' not in upstream.request.call_args.kwargs['body']
    assert forwarded[token_field]==20 and forwarded['reasoning_effort']=='low'
    assert ('max_tokens' if token_field=='max_completion_tokens' else 'max_completion_tokens') not in forwarded
    assert connection.call_args.args==('fixed.example',443)
    second=send({'messages':[{'role':'user','content':'hello'}]})
    assert second.send_response.call_args.args[0]==429
    assert connection.call_count==1
    invalid=send({'messages':[],'base_url':'https://evil.example'})
    assert invalid.send_response.call_args.args[0]==403
    assert b'PRIVATE-KEY' not in invalid.wfile.getvalue()


def test_gateway_must_be_ready_before_an_engine_can_start(monkeypatch):
    import subprocess
    monkeypatch.setattr('socket.getfqdn',lambda *_:'localhost')
    monkeypatch.setattr('socket.getaddrinfo',lambda *_args,**_kwargs:[(None,None,None,None,('8.8.8.8',443))])
    runner=DockerRunner(IMAGES,process_factory=lambda *_args,**_kwargs:Process(True))
    calls=[]
    def command(*args,**kwargs):
        calls.append(args)
        if args[0]=='info':return b'{"runsc":{}}'
        if args[:2]==('network','inspect'):return b'172.17.0.1'
        if args[0]=='inspect':return b'172.28.0.2'
        if args[0]=='exec':raise subprocess.CalledProcessError(1,['docker','exec'])
        return b''
    runner.docker=command
    route=ModelRoute('openai','configured','https://model.example/v1','PRIVATE',1,1,1)
    job={'id':str(uuid4()),'kind':'openhands','payload':{'task':{'task':'fixture','files':{},'allowed_hosts':[],'max_seconds':5,'max_steps':2}}}
    with pytest.raises(RuntimeError,match='gateway did not become ready'):
        runner.execute(job,guard=lambda:route,action_gate=Mock())
    # The trusted gateway must start first; the SDK engine still must not.
    starts=[args[args.index('--name')+1] for args in calls if args[0] in ('run','create')]
    assert starts==['native-gateway-'+job['id']]


@pytest.mark.parametrize('address',['127.0.0.1','0.0.0.0','169.254.169.254','8.8.8.8','224.0.0.1','::1','invalid IP'])
def test_sandbox_gateway_address_must_be_private_ipv4(address):
    with pytest.raises(ValueError):DockerRunner.private_ipv4(address)


def test_gateway_pins_public_browser_and_fixed_private_model_routes(monkeypatch):
    def resolve(host,*_args,**_kwargs):
        addresses=['2606:4700:4700::1111','1.1.1.1'] if host=='allowed.example' else ['10.20.0.5']
        return [(None,None,None,None,(address,443)) for address in addresses]
    monkeypatch.setattr('socket.getaddrinfo',resolve)
    entries=DockerRunner.gateway_host_entries(['allowed.example'],'https://model.example/v1','172.17.0.1')
    assert entries==['--add-host','host.docker.internal:172.17.0.1','--add-host','allowed.example:1.1.1.1','--add-host','model.example:10.20.0.5']


@pytest.mark.parametrize('address',['127.0.0.1','169.254.169.254','::1','0.0.0.0','224.0.0.1'])
def test_gateway_model_route_cannot_pin_loopback_or_metadata(monkeypatch,address):
    monkeypatch.setattr('socket.getaddrinfo',lambda *_args,**_kwargs:[(None,None,None,None,(address,443))])
    with pytest.raises(ValueError):DockerRunner.gateway_host_entries([],'https://model.example/v1','172.17.0.1')


def test_gateway_browser_pin_rejects_mixed_public_private_resolution(monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo',lambda *_args,**_kwargs:[(None,None,None,None,('8.8.8.8',443)),(None,None,None,None,('10.0.0.1',443))])
    with pytest.raises(ValueError):DockerRunner.gateway_host_entries(['allowed.example'],'https://host.docker.internal/v1','172.17.0.1')
