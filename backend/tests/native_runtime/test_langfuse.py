from unittest.mock import Mock
import json
import pytest
import httpx
from app.services.native_agent_adapters import AdapterScope,TelemetryPermit
from app.services.native_runtime.langfuse import LangfuseOutbox,LangfuseTransport,validate_metrics
from tests.native_runtime.test_journal import journal,S
from tests.support.fake_supabase import FakeSupabase

@pytest.fixture
def db():
    db=FakeSupabase();db.tables['intelligence_outcome_events']=[{'id':'receipt','org_id':S.org_id,'agent_id':S.agent_id,'entity_id':S.run_id,'outcome_event':'dialogue_evaluated','created_at':'2026-10-28T12:00:00Z','metadata':{'evaluator_version':'dialogue-metrics-v1','channel':'voice','stage_count':6,'failed_stage_count':1,'duration_ms':15,'prompt':'DO NOT EXPORT','api_key':'SECRET'}}]
    return db

@pytest.fixture
def setup(journal):
    transport=Mock();transport.acknowledged.return_value=False
    return LangfuseOutbox(journal,b'x'*32,lambda scope:transport,export_allowed=lambda scope:True),transport

def ready(journal,id):
    with journal.connect() as db:db.execute('UPDATE jobs SET next_at=0 WHERE id=?',(id,))

def test_requires_exact_per_run_consent_and_receipt_scope(setup,db):
    out,transport=setup
    assert out.enqueue(db,'receipt',scope=S,permit=TelemetryPermit(S,False)) is None
    other=AdapterScope('other',S.agent_id,S.run_id)
    assert out.enqueue(db,'receipt',scope=other,permit=TelemetryPermit(other,True)) is None
    assert out.enqueue(db,'receipt',scope=S,permit=TelemetryPermit(other,True)) is None
    transport.submit.assert_not_called()

def test_durable_retry_has_stable_ids_and_requires_remote_ack(setup,db,journal):
    out,transport=setup
    id=out.enqueue(db,'receipt',scope=S,permit=TelemetryPermit(S,True))
    assert out.enqueue(db,'receipt',scope=S,permit=TelemetryPermit(S,True))==id
    assert out.tick()=='ack_pending'
    assert journal.get(S,id)['state']=='queued'
    payload=transport.submit.call_args.args[0]
    assert set(payload['metrics'])=={'schema_version','run_ref','channel','evaluator_version','stage_count','failed_stage_count','duration_ms'}
    assert 'SECRET' not in repr(payload) and S.org_id not in repr(payload) and 'DO NOT EXPORT' not in repr(payload)
    ready(journal,id);transport.acknowledged.return_value=True
    assert out.tick()=='delivered'
    assert journal.get(S,id)['state']=='delivered'
    assert transport.submit.call_count==1

def test_revocation_deletes_remote_before_local_erasure(setup,db,journal):
    out,transport=setup;transport.acknowledged.return_value=True;transport.delete.return_value=True
    id=out.enqueue(db,'receipt',scope=S,permit=TelemetryPermit(S,True));out.tick()
    out.withdraw(S)
    assert not journal.consent(S)
    ready(journal,id)
    assert out.tick('langfuse_delete')=='deleted'
    assert journal.get(S,id,material=True)['payload'] is None

def test_unacknowledged_inflight_export_never_claims_complete_deletion(setup,db,journal):
    out,transport=setup
    id=out.enqueue(db,'receipt',scope=S,permit=TelemetryPermit(S,True));out.tick()
    out.withdraw(S);ready(journal,id)
    assert out.tick('langfuse_delete')=='deletion_pending'
    assert journal.get(S,id)['state']!='deleted'
    transport.delete.assert_not_called()

def test_failures_are_sanitized_and_retry_is_bounded(setup,db,journal):
    out,transport=setup;transport.submit.side_effect=RuntimeError('SECRET provider failure')
    id=out.enqueue(db,'receipt',scope=S,permit=TelemetryPermit(S,True))
    for _ in range(8):ready(journal,id);out.tick()
    assert journal.get(S,id)['state']=='failed'
    assert journal.get(S,id)['error_code']=='delivery_failed'
    assert 'SECRET' not in repr(journal.get(S,id,material=True))

def test_transport_uses_stable_otlp_ids_safe_fields_and_strict_ack():
    requests=[];payload={'trace_id':'1'*32,'span_id':'2'*16,'start_ns':1000,'metrics':{'schema_version':1,'run_ref':'a'*64,'channel':'text','evaluator_version':'dialogue-metrics-v1','stage_count':2,'failed_stage_count':0,'duration_ms':1}}
    def handle(request):
        requests.append(request)
        if request.method=='POST':return httpx.Response(200,content=b'')
        return httpx.Response(200,json={'data':[{'id':payload['span_id'],'traceId':payload['trace_id'],'name':'gravitre.dialogue_evaluation','metadata':payload['metrics']}]})
    t=LangfuseTransport('https://metrics.example','public','private',client=httpx.Client(transport=httpx.MockTransport(handle)))
    t.submit(payload);t.submit(payload)
    assert requests[0].content==requests[1].content
    assert t.acknowledged(payload)
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    decoded=ExportTraceServiceRequest();decoded.ParseFromString(requests[0].content)
    span=decoded.resource_spans[0].scope_spans[0].spans[0]
    assert span.trace_id.hex()==payload['trace_id'] and span.span_id.hex()==payload['span_id']
    assert len(span.attributes)==8
    assert 'fields=core%2Cbasic%2Cmetadata' in str(requests[-1].url)
    assert 'io' not in requests[-1].url.params['fields']
    payload['metrics']['prompt']='forbidden'
    with pytest.raises(ValueError):t.submit(payload)

def test_redirect_does_not_leak_credentials():
    t=LangfuseTransport('https://metrics.example','p','s',client=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(302,headers={'Location':'https://evil.example'}))))
    with pytest.raises(ValueError):t.observations({'trace_id':'1'*32})
