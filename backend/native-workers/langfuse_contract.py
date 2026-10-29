"""Real isolated Langfuse server/OTLP/observation/deletion certification.

Inputs are synthetic counts only. The application journal and transport are real;
the tenant receipt database is an explicitly filter-honoring local fixture.
"""
from __future__ import annotations
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4
import httpx
from cryptography.fernet import Fernet

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.native_agent_adapters import AdapterScope,TelemetryPermit
from app.services.native_runtime.langfuse import LangfuseOutbox,LangfuseTransport,METRIC_KEYS
from app.services.native_runtime.store import Journal
from tests.support.fake_supabase import FakeSupabase


def run():
    statuses=[]
    class Proxy(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def relay(self):
            # The actual Langfuse server is localhost-only on this CI host.
            connection=http.client.HTTPConnection('127.0.0.1',3000,timeout=30)
            try:
                length=int(self.headers.get('Content-Length','0'));assert 0<=length<=262144
                connection.request(self.command,self.path,body=self.rfile.read(length) if length else None,headers={k:v for k,v in self.headers.items() if k.lower() in {'authorization','content-type','x-langfuse-ingestion-version'}})
                response=connection.getresponse();body=response.read(2097153);assert len(body)<=2097152
                statuses.append({'method':self.command,'status':response.status})
                self.send_response(response.status);self.send_header('Content-Type',response.getheader('Content-Type','application/json'));self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            finally:connection.close()
        do_POST=relay;do_GET=relay;do_DELETE=relay
    with tempfile.TemporaryDirectory(prefix='langfuse-cert-') as temporary:
        root=Path(temporary)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost','-keyout',str(root/'key.pem'),'-out',str(root/'cert.pem')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        server=ThreadingHTTPServer(('127.0.0.1',0),Proxy);tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(root/'cert.pem',root/'key.pem');server.socket=tls.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with httpx.Client(verify=str(root/'cert.pem'),timeout=15,follow_redirects=False,trust_env=False) as client:
                transport=LangfuseTransport(f'https://localhost:{server.server_port}',os.environ['LANGFUSE_INIT_PROJECT_PUBLIC_KEY'],os.environ['LANGFUSE_INIT_PROJECT_SECRET_KEY'],client=client)
                scope=AdapterScope(str(uuid4()),str(uuid4()),str(uuid4()));receipt=str(uuid4())
                database=FakeSupabase();database.tables['intelligence_outcome_events']=[{'id':receipt,'org_id':scope.org_id,'agent_id':scope.agent_id,'entity_id':scope.run_id,'outcome_event':'dialogue_evaluated','created_at':datetime.now(timezone.utc).isoformat(),'metadata':{'evaluator_version':'dialogue-metrics-v1','channel':'text','stage_count':3,'failed_stage_count':0,'duration_ms':1}}]
                key=Fernet.generate_key();path=str(root/'journal.sqlite');journal=Journal(path,key)
                outbox=LangfuseOutbox(journal,b'isolated-fixture-correlation-key-32',lambda _:transport,export_allowed=lambda _:True)
                assert outbox.enqueue(database,receipt,scope=scope,permit=TelemetryPermit(scope,False)) is None
                assert not statuses,'Consent denial made a request'
                job=outbox.enqueue(database,receipt,scope=scope,permit=TelemetryPermit(scope,True))
                assert outbox.enqueue(database,receipt,scope=scope,permit=TelemetryPermit(scope,True))==job
                # Reconstruct the durable client/journal before processing.
                journal=Journal(path,key);outbox=LangfuseOutbox(journal,b'isolated-fixture-correlation-key-32',lambda _:transport,export_allowed=lambda _:True)
                def settle(kind,target):
                    deadline=time.monotonic()+600
                    while time.monotonic()<deadline:
                        outbox.tick(kind)
                        row=journal.get(scope,job,material=True)
                        if row['state']==target:return row
                        if row['state']=='failed':raise AssertionError('Durable Langfuse job failed: '+str(row['error_code']))
                        time.sleep(2)
                    raise AssertionError('Durable Langfuse acknowledgement deadline exceeded')
                delivered=settle('langfuse','delivered');payload=delivered['payload']
                assert set(payload['metrics'])==METRIC_KEYS and transport.acknowledged(payload)
                assert len(transport.observations(payload))==1,'Stable identity duplicated an observation'
                outbox.withdraw(scope);assert not journal.consent(scope)
                erased=settle('langfuse_delete','deleted')
                assert erased['payload'] is None and not transport.observations(payload)
                evidence={'schema_version':1,'git_sha':os.environ.get('GITHUB_SHA','local'),'server_release':'v4.71.0','consent_denial_no_request':'PASS','durable_restart_and_idempotency':'PASS','real_otlp_exact_observation_readback':'PASS','real_trace_deletion_readback':'PASS','local_encrypted_payload_erased':'PASS','external_provider_requests':False,'live_tenant_data':False,'http_status_counts':{str(code):sum(s['status']==code for s in statuses) for code in sorted({s['status'] for s in statuses})}}
                Path(os.environ.get('LANGFUSE_CERT_EVIDENCE','langfuse-runtime-evidence.json')).write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,sort_keys=True))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':run()
