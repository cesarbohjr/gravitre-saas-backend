"""Per-job trusted model/egress gateway, run in a separate disposable container.

Never mounts the Docker socket or engine workspace. The engine receives only a
random per-job token, not a provider credential. Exact CONNECT destinations are
resolved and pinned to public IPs; the engine has only an internal Docker network.
"""
from __future__ import annotations
import base64
import hmac
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
import select
import socket
import threading
import sys
from urllib.parse import urlsplit
import urllib.request
try:
    from .network import public_addresses
    from .http_server import BoundedHTTPServer
except ImportError:
    from network import public_addresses
    from http_server import BoundedHTTPServer

CONFIG={}
LOCK=threading.Lock();SPENT=0.0;CALLS=0


def control(operation: str,payload: dict) -> dict:
    body=json.dumps({'operation':operation,'payload':payload}).encode()
    req=urllib.request.Request(CONFIG['control_url'],data=body,headers={'Authorization':'Bearer '+CONFIG['control_token'],'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as r:
        return json.loads(r.read(65536))


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,value):
        body=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        global SPENT,CALLS
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+CONFIG['engine_token']):return self.reply(403,{'error':'native_authorization_required'})
        stage='decode';body={}
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=262144:raise ValueError('bounds')
            body=json.loads(self.rfile.read(length))
            if self.path=='/action':
                stage='action_authority'
                return self.reply(200,control('action',body))
            if self.path!='/v1/chat/completions':return self.reply(404,{'error':'unsupported_native_route'})
            if body.get('stream') is True:raise ValueError('Only bounded non-streamed model calls are supported')
            stage='authority';control('authorize',{})
            stage='content'
            body.pop('stream',None)
            # OpenHands supplies conversation cache affinity automatically.
            # It is not execution input and must not reach the model provider.
            body.pop('prompt_cache_key',None);body.pop('prompt_cache_retention',None)
            # Byte count is a conservative upper bound on text token count;
            # images/audio and provider-specific URL fetches are not accepted.
            for message in body.get('messages',[]):
                content=message.get('content')
                if isinstance(content,list):
                    if any(not isinstance(c,dict) or c.get('type')!='text' or not isinstance(c.get('text'),str) for c in content):raise ValueError('Multimodal calls require a separate approved path')
                elif content is not None and not isinstance(content,str):raise ValueError('Invalid model content')
            body['model']=CONFIG['model']
            token_field='max_completion_tokens' if 'max_completion_tokens' in body else 'max_tokens'
            output_limit=min(int(body.get(token_field) or CONFIG['max_output_tokens']),CONFIG['max_output_tokens'])
            body.pop('max_tokens',None);body.pop('max_completion_tokens',None);body[token_field]=output_limit
            if not 1<=output_limit<=8192:raise ValueError('bounds')
            # Never forward model-supplied routing/telemetry destinations.
            allowed={'model','messages','tools','tool_choice','temperature','max_tokens','stop','response_format','parallel_tool_calls','max_completion_tokens','frequency_penalty','presence_penalty','top_p','seed','reasoning_effort'}
            stage='parameters'
            if set(body)-allowed:raise ValueError('Unsupported model parameter')
            raw=json.dumps(body,separators=(',',':')).encode()
            reserve=(len(raw)*CONFIG['input_usd_per_million']+output_limit*CONFIG['output_usd_per_million'])/1000000
            with LOCK:
                if CALLS>=CONFIG['max_calls'] or SPENT+reserve>CONFIG['budget_usd']:return self.reply(429,{'error':'native_budget_exhausted'})
                SPENT+=reserve;CALLS+=1
            # HTTPSConnection does not follow redirects and pins the configured
            # origin. Request bodies and provider failures are never logged.
            stage='upstream'
            u=urlsplit(CONFIG['base_url']);connection=http.client.HTTPSConnection(u.hostname,u.port or 443,timeout=30)
            try:
                connection.request('POST',u.path.rstrip('/')+'/chat/completions',body=raw,headers={'Authorization':'Bearer '+CONFIG['api_key'],'Content-Type':'application/json'})
                r=connection.getresponse();data=r.read(1048577)
                if r.status!=200 or len(data)>1048576:return self.reply(502,{'error':'native_model_failed'})
                stage='final_authority';control('authorize',{})
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            finally:connection.close()
        except Exception as error:
            # Only fixed stages/classes/known parameter names enter the private
            # diagnostic pipe. Never include request values or exception text.
            print(json.dumps({'gateway_failure_stage':stage,'gateway_failure_class':type(error).__name__,'known_parameter_flags':[key for key in ('n','store','stream_options','service_tier','metadata','user','top_k','prompt_cache_key','prompt_cache_retention') if isinstance(body,dict) and key in body]}),file=sys.stderr,flush=True)
            self.reply(403,{'error':'native_request_blocked'})
    def do_CONNECT(self):
        remote=None;stage='connect_destination'
        try:
            u=urlsplit('//'+self.path)
            if u.hostname not in CONFIG['allowed_hosts'] or u.port!=443 or u.username or u.password:raise ValueError('scope')
            stage='connect_authority';control('authorize',{})
            stage='connect_dns'
            addresses=public_addresses(u.hostname)
            # Connect to the validated numeric address, never re-resolve a host.
            stage='connect_socket';remote=socket.create_connection((addresses[0],443),timeout=10)
            self.send_response(200,'Connection established');self.end_headers()
            peers=[self.connection,remote]
            stage='connect_relay'
            while True:
                control('authorize',{})
                readable,_,_=select.select(peers,[],[],2)
                for source in readable:
                    data=source.recv(65536)
                    if not data:return
                    (remote if source is self.connection else self.connection).sendall(data)
        except Exception as error:
            kind=type(error).__name__
            if kind not in {'ValueError','PermissionError','TimeoutError','ConnectionError','ConnectionRefusedError','ConnectionResetError','BrokenPipeError','OSError','gaierror','HTTPError','URLError'}:kind='InternalError'
            print(json.dumps({'gateway_failure_stage':stage,'gateway_failure_class':kind,'known_parameter_flags':[]}),file=sys.stderr,flush=True)
            try:self.send_error(403,'Native destination blocked')
            except Exception:pass
        finally:
            if remote:remote.close()


if __name__=='__main__':
    CONFIG=json.loads(sys.stdin.buffer.read(65537))
    BoundedHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
