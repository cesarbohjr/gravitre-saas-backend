"""One gVisor/Kata-isolated engine + trusted egress gateway per native job.

Only this trusted broker talks to Docker. Engines receive no host filesystem,
Docker socket, cloud credential or tenant provider key. No insecure runtime,
shared browser session, host networking or unbounded process fallback exists.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from http.server import BaseHTTPRequestHandler
import hmac
import ipaddress
import json
import re
import secrets
import subprocess
import threading
import time
from uuid import UUID
from app.services.native_runtime.http_server import BoundedHTTPServer


@dataclass(frozen=True)
class SandboxImages:
    openhands: str
    browser_use: str
    gateway: str
    runtime: str='runsc'

    def validate(self):
        if self.runtime not in ('runsc','kata-runtime'):raise ValueError('A reviewed isolating container runtime is required')
        for image in (self.openhands,self.browser_use,self.gateway):
            if not re.fullmatch(r'[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}',image):raise ValueError('All native images must be pinned by digest')


class DockerRunner:
    def __init__(self,images: SandboxImages,*,command=None,process_factory=None):
        images.validate();self.images=images;self.command=command or subprocess.run;self.process_factory=process_factory or subprocess.Popen

    def docker(self,*args,input: bytes | None=None):
        r=self.command(['docker',*args],input=input,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20,check=True)
        if len(r.stdout)>8388608:raise ValueError('Oversized sandbox response')
        return r.stdout.decode().strip() if not isinstance(r.stdout,bytes) else r.stdout

    def names(self,id: str):
        UUID(id)
        return 'native-'+id,'native-engine-'+id,'native-gateway-'+id

    def cleanup(self,id: str):
        network,engine,gateway=self.names(id)
        raw=self.docker('ps','-a','--filter','label=gravitre.native.job='+id,'--format','{{.Names}}')
        names=raw.decode().splitlines() if isinstance(raw,bytes) else raw.splitlines()
        if set(names)-{engine,gateway}:raise RuntimeError('Unexpected native resource owner')
        if names:self.docker('rm','-f',*names)
        raw=self.docker('network','ls','--filter','label=gravitre.native.job='+id,'--format','{{.Name}}')
        networks=raw.decode().splitlines() if isinstance(raw,bytes) else raw.splitlines()
        if set(networks)-{network}:raise RuntimeError('Unexpected native network owner')
        if network in networks:self.docker('network','rm',network)

    @staticmethod
    def private_ipv4(raw) -> str:
        value=raw.decode().strip() if isinstance(raw,bytes) else raw.strip()
        address=ipaddress.ip_address(value)
        if address.version!=4 or not address.is_private or address.is_loopback or address.is_unspecified or address.is_link_local or address.is_multicast:
            raise ValueError('Invalid private gateway interface')
        return str(address)

    def wait_for_gateway(self,gateway: str,network: str,process,guard) -> str:
        # Bind the internal gateway through /etc/hosts. A sandbox's isolated
        # loopback DNS must not depend on Docker's host-side DNS listener.
        ready_by=time.monotonic()+30
        while True:
            guard()
            gateway_address=self.docker('inspect','--format','{{(index .NetworkSettings.Networks "'+network+'").IPAddress}}',gateway).decode().strip()
            if gateway_address:break
            # Docker may report the newly connected interface before its
            # address is populated; never start the engine with no route.
            if process.poll() is not None or time.monotonic()>=ready_by:
                raise RuntimeError('Native gateway interface did not become ready')
            time.sleep(0.1)
        gateway_address=self.private_ipv4(gateway_address)
        while True:
            guard()
            try:
                self.docker('exec',gateway,'python','-c','import socket; s=socket.create_connection(("127.0.0.1",8080),timeout=1); s.close()')
                break
            except subprocess.CalledProcessError:
                if process.poll() is not None or time.monotonic()>=ready_by:raise RuntimeError('Native gateway did not become ready') from None
                time.sleep(0.25)
        return gateway_address

    def execute(self,job: dict,*,guard,action_gate) -> dict:
        id=job['id'];network,engine,gateway=self.names(id)
        route=guard();route.validate()
        runtimes=json.loads(self.docker('info','--format','{{json .Runtimes}}'))
        if self.images.runtime not in runtimes:raise RuntimeError('Isolating container runtime is not installed')
        # A previously orphaned sandbox cannot coexist with this operation.
        self.cleanup(id)
        control_token=secrets.token_urlsafe(32);engine_token=secrets.token_urlsafe(32)
        class Control(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                try:
                    if self.path!='/control' or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+control_token):raise PermissionError('scope')
                    count=int(self.headers.get('Content-Length','0'))
                    if not 0<count<=16384:raise ValueError('bounds')
                    body=json.loads(self.rfile.read(count));guard()
                    if body['operation']=='authorize':value={'authorized':True}
                    elif body['operation']=='action' and job['kind']=='browser_use':
                        payload=body['payload'];value=action_gate(payload['sequence'],payload['action'])
                    else:raise PermissionError('unknown native operation')
                    data=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                except Exception:
                    self.send_response(403);self.end_headers()
        server=BoundedHTTPServer(('0.0.0.0',0),Control)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        process=None;gateway_process=None
        try:
            self.docker('network','create','--internal','--opt','com.docker.network.bridge.gateway_mode_ipv4=isolated','--label','gravitre.native.job='+id,network)
            common=['--log-driver','none','--runtime',self.images.runtime,'--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                    '--pids-limit','256','--memory','2048m','--cpus','2','--user','10001:10001',
                    '--label','gravitre.native.job='+id,'--tmpfs','/tmp:rw,noexec,nosuid,size=128m,uid=10001,gid=10001']
            config={**asdict(route),'max_calls':job['payload']['task']['max_steps'],
                    'control_url':f'http://host.docker.internal:{server.server_port}/control','control_token':control_token,
                    'engine_token':engine_token,'allowed_hosts':job['payload']['task']['allowed_hosts']}
            # Attach both interfaces before starting runsc: its network stack
            # snapshots interfaces at sandbox startup. Credentials go only to
            # the subsequent exec stream, never container configuration.
            # Resolve Docker's bridge explicitly: runsc rejects the OCI extra-host
            # entry generated by Docker's host-gateway sentinel on some hosts.
            bridge=self.private_ipv4(self.docker('network','inspect','bridge','--format','{{(index .IPAM.Config 0).Gateway}}'))
            self.docker('create','-i','--name',gateway,'--network','bridge','--add-host','host.docker.internal:'+bridge,*common,
                self.images.gateway,'timeout','--signal=KILL',str(job['payload']['task']['max_seconds']+60),'sleep','infinity')
            self.docker('network','connect','--alias','gateway',network,gateway)
            self.docker('start',gateway)
            gateway_process=self.process_factory(['docker','exec','-i',gateway,'python','/runner/gateway.py'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            gateway_process.stdin.write(json.dumps(config).encode());gateway_process.stdin.close()
            gateway_address=self.wait_for_gateway(gateway,network,gateway_process,guard)
            image=self.images.openhands if job['kind']=='openhands' else self.images.browser_use
            self.docker('run','-d','-i','--name',engine,'--network',network,'--dns','127.0.0.1','--add-host','gateway:'+gateway_address,*common,
                '--tmpfs','/workspace:rw,nosuid,size=128m,uid=10001,gid=10001',
                '--tmpfs','/out:rw,noexec,nosuid,size=4m,uid=10001,gid=10001',
                '-e','HOME=/workspace','-e','HTTP_PROXY=http://gateway:8080','-e','HTTPS_PROXY=http://gateway:8080','-e','NO_PROXY=gateway,localhost,127.0.0.1',
                '-e','ANONYMIZED_TELEMETRY=false','-e','DO_NOT_TRACK=1','-e','OTEL_SDK_DISABLED=true',
                image,'timeout','--signal=KILL',str(job['payload']['task']['max_seconds']+30),'sleep','infinity')
            # Verify the actual guest-to-gateway path before invoking an SDK.
            self.docker('exec',engine,'python','-c','import socket; s=socket.create_connection(("gateway",8080),timeout=2); s.close()')
            payload={**job['payload']['task'],'engine':job['kind'],'model':route.model,'engine_token':engine_token}
            # No task/credential enters process arguments, logs or a host mount.
            process=self.process_factory(['docker','exec','-i',engine,'python','/runner/engine.py'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            process.stdin.write(json.dumps(payload).encode());process.stdin.close()
            deadline=time.monotonic()+job['payload']['task']['max_seconds']
            while process.poll() is None:
                guard()
                if time.monotonic()>=deadline:raise TimeoutError('Native sandbox timed out')
                time.sleep(0.5)
            if process.returncode:raise RuntimeError('Native engine failed')
            # gVisor's guest tmpfs is not Docker's host-side mounted rootfs.
            # Read inside the guest; no host mount or archive extraction needed.
            raw=self.docker('exec',engine,'python','-c','import sys; f=open("/out/result.json","rb"); sys.stdout.buffer.write(f.read(240001))')
            if not 0<len(raw)<=240000:raise ValueError('Invalid sandbox output')
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError('Invalid sandbox output')
            guard()
            return result
        finally:
            try:self.cleanup(id)
            finally:
                for child in (process,gateway_process):
                    if child and child.poll() is None:child.kill();child.wait(timeout=10)
                server.shutdown();server.server_close();thread.join(timeout=5)
