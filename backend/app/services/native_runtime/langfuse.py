"""Metrics-only, idempotent OTLP delivery with source-of-record acknowledgement.

Uses stable trace/span IDs for retries. A 2xx ingestion response is not delivery:
GET /api/public/v2/observations must return the exact observation and metrics.
Transport, credentials and the client are bound to an administrator's tenant
configuration, never to a model-provided endpoint or global default SDK client.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
from typing import Any, Callable
from urllib.parse import urlsplit
import httpx
from app.services.native_agent_adapters import AdapterScope, TelemetryPermit, load_langfuse_feedback_metrics
from app.services.native_runtime.store import Journal, LeaseLost

NAME='gravitre.dialogue_evaluation'
METRIC_KEYS=frozenset({'schema_version','run_ref','channel','evaluator_version','stage_count','failed_stage_count','duration_ms'})
# Langfuse derives these static fields from our OTLP envelope, not tenant data.
READBACK_PROVENANCE={'attributes.langfuse.observation.type':'span','resourceAttributes.service.name':'gravitre.metrics','scope.name':'gravitre.metrics.v1'}


def validate_metrics(m: dict) -> None:
    if set(m)!=METRIC_KEYS or m.get('schema_version')!=1 or type(m.get('schema_version')) is not int:
        raise ValueError('Invalid telemetry allowlist')
    if not isinstance(m.get('run_ref'),str) or not re.fullmatch('[0-9a-f]{64}',m['run_ref']):raise ValueError('Invalid run reference')
    if m.get('channel') not in ('text','voice') or m.get('evaluator_version')!='dialogue-metrics-v1':raise ValueError('Invalid telemetry enums')
    for key,limit in [('stage_count',20),('failed_stage_count',20),('duration_ms',604800000)]:
        if type(m.get(key)) is not int or not 0<=m[key]<=limit:raise ValueError('Invalid metric bounds')
    if m['failed_stage_count']>m['stage_count']:raise ValueError('Invalid stage counts')


class LangfuseTransport:
    def __init__(self, base_url: str, public_key: str, secret_key: str, *, client: httpx.Client | None=None):
        u=urlsplit(base_url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
            raise ValueError('A configured HTTPS Langfuse origin is required')
        if not public_key or not secret_key:raise ValueError('Tenant Langfuse credentials required')
        self.origin=base_url.rstrip('/')
        self.destination_ref=hashlib.sha256((self.origin+'\n'+public_key).encode()).hexdigest()
        self.auth=httpx.BasicAuth(public_key,secret_key)
        self.owns_client=client is None
        self.http=client or httpx.Client(timeout=10,follow_redirects=False,trust_env=False)

    def close(self) -> None:
        if self.owns_client:self.http.close()

    def _request(self, method: str, path: str, **kwargs):
        response=self.http.request(method,self.origin+path,auth=self.auth,timeout=10,follow_redirects=False,**kwargs)
        if 300<=response.status_code<400:raise ValueError('Telemetry redirects are forbidden')
        response.raise_for_status()
        return response

    def submit(self, payload: dict) -> None:
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
        validate_metrics(payload['metrics'])
        request=ExportTraceServiceRequest()
        resource=request.resource_spans.add()
        attr=resource.resource.attributes.add();attr.key='service.name';attr.value.string_value='gravitre.metrics'
        scope=resource.scope_spans.add();scope.scope.name='gravitre.metrics.v1'
        span=scope.spans.add();span.trace_id=bytes.fromhex(payload['trace_id']);span.span_id=bytes.fromhex(payload['span_id'])
        span.name=NAME;span.kind=1
        span.start_time_unix_nano=payload['start_ns'];span.end_time_unix_nano=payload['start_ns']+max(1,payload['metrics']['duration_ms']*1000000)
        # A JSON object preserves the seven allowlisted metric types without
        # claiming a Langfuse SDK/version to enable SDK-specific value decoding.
        attr=span.attributes.add();attr.key='langfuse.observation.metadata'
        attr.value.string_value=json.dumps(payload['metrics'],sort_keys=True,separators=(',',':'))
        attr=span.attributes.add();attr.key='langfuse.observation.type';attr.value.string_value='span'
        result=self._request('POST','/api/public/otel/v1/traces',content=request.SerializeToString(),headers={'Content-Type':'application/x-protobuf','x-langfuse-ingestion-version':'4'})
        # OTLP may report partial rejection under HTTP 200.
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse
        if result.content:
            ack=ExportTraceServiceResponse();ack.ParseFromString(result.content)
            if ack.partial_success.rejected_spans:raise ValueError('Telemetry ingestion rejected a span')

    def observations(self, payload: dict) -> list[dict]:
        # Every value is <=64 characters. Compact metadata avoids an expanded
        # events_full join while retaining exact, non-truncated metric values.
        r=self._request('GET','/api/public/v2/observations',params={'traceId':payload['trace_id'],'fields':'core,basic,metadata','limit':10})
        data=r.json().get('data')
        if not isinstance(data,list):raise ValueError('Malformed observation acknowledgement')
        return data

    def acknowledged(self, payload: dict) -> bool:
        for row in self.observations(payload):
            if not isinstance(row,dict) or row.get('id')!=payload['span_id'] or row.get('traceId')!=payload['trace_id'] or row.get('name')!=NAME:
                continue
            metadata=row.get('metadata')
            if not isinstance(metadata,dict):continue
            if set(metadata)!=METRIC_KEYS|READBACK_PROVENANCE.keys():continue
            try:validate_metrics({key:metadata[key] for key in METRIC_KEYS})
            except ValueError:continue
            if metadata=={**payload['metrics'],**READBACK_PROVENANCE}:return True
        return False

    def delete(self, payload: dict) -> bool:
        try:self._request('DELETE','/api/public/traces/'+payload['trace_id'])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code!=404:raise
        return not self.observations(payload)


class LangfuseOutbox:
    def __init__(self, journal: Journal, correlation_key: bytes, transport_for: Callable[[AdapterScope], LangfuseTransport], *, export_allowed: Callable[[AdapterScope], bool]):
        if len(correlation_key)<32:raise ValueError('Dedicated correlation key required')
        self.journal=journal;self.key=correlation_key;self.transport_for=transport_for;self.export_allowed=export_allowed

    def enqueue(self, client: Any, receipt_id: str, *, scope: AdapterScope, permit: TelemetryPermit, ttl: int=86400, actor: str='') -> str | None:
        if permit.scope!=scope or permit.enabled is not True:return None
        metrics=load_langfuse_feedback_metrics(client,receipt_id,scope=scope,correlation_key=self.key)
        if metrics is None:return None
        validate_metrics(metrics)
        identity=json.dumps([scope.org_id,scope.agent_id,scope.run_id,receipt_id],separators=(',',':')).encode()
        digest=hmac.new(self.key,b'langfuse-receipt-v1:'+identity,hashlib.sha256).hexdigest()
        # Stable event time is derived from the validated local receipt, not a
        # new wall-clock value on retries. It stays internal and carries no IO.
        rows=(client.table('intelligence_outcome_events').select('created_at').eq('org_id',scope.org_id).eq('agent_id',scope.agent_id).eq('id',receipt_id).limit(1).execute().data or [])
        from datetime import datetime
        stamp=(rows[0].get('created_at') if rows else None)
        if not isinstance(stamp,str):raise ValueError('A dated durable evaluation receipt is required')
        parsed=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if parsed.tzinfo is None or parsed.timestamp()<=0:raise ValueError('Receipt date must be timezone-aware')
        start_ns=int(parsed.timestamp()*1000000000)
        configured=self.transport_for(scope)
        try:
            destination=configured.destination_ref
            if not isinstance(destination,str) or not re.fullmatch('[0-9a-f]{64}',destination):raise ValueError('Bound telemetry destination required')
        finally:
            if isinstance(configured,LangfuseTransport):configured.close()
        payload={'trace_id':digest[:32],'span_id':digest[32:48],'start_ns':start_ns,'metrics':metrics,'destination_ref':destination}
        self.journal.set_consent(scope,True,ttl=ttl)
        return self.journal.enqueue(scope,'langfuse',digest,payload,ttl=ttl,actor=actor)

    def withdraw(self, scope: AdapterScope) -> None:
        self.journal.set_consent(scope,False)

    def tick(self, kind: str='langfuse') -> str | None:
        if kind not in ('langfuse','langfuse_delete'):raise ValueError('Invalid delivery queue')
        job=self.journal.claim(kind)
        if not job:return None
        scope=job['scope'];payload=job['payload'];transport=None
        try:
            if kind=='langfuse' and not self.export_allowed(scope):
                self.journal.set_consent(scope,False)
                return 'consent_revoked'
            transport=self.transport_for(scope)
            if transport.destination_ref!=payload.get('destination_ref'):
                self.journal.update(job,'queued',error='delivery_destination_changed',retry_delay=min(300,2**job['attempts']))
                return 'destination_changed'
            if kind=='langfuse_delete':
                # An empty query cannot prove deletion after an unacknowledged
                # in-flight POST. Wait for source evidence, or leave an explicit
                # unresolved deletion failure; never certify false erasure.
                if job['phase']=='delete_unknown' and not transport.acknowledged(payload):
                    self.journal.update(job,'queued',error='deletion_outcome_uncertain',retry_delay=min(300,2**job['attempts']))
                    return 'deletion_pending'
                if transport.delete(payload):
                    self.journal.update(job,'deleted');self.journal.erase(scope,job['id'])
                    return 'deleted'
                self.journal.update(job,'queued',error='deletion_unconfirmed',retry_delay=min(300,2**job['attempts']))
                return 'deletion_pending'
            if not self.journal.consent(scope) or not self.export_allowed(scope):
                self.journal.request_deletion(job);return 'consent_revoked'
            if not self.journal.active(job):raise LeaseLost('Lease revoked')
            if job['phase']=='submit':
                # Durable phase before I/O. Retrying uses the same trace/span IDs.
                self.journal.update(job,'running',phase='ack')
                if not self.journal.consent(scope) or not self.export_allowed(scope) or not self.journal.active(job):raise LeaseLost('Consent revoked')
                transport.submit(payload)
            else:
                if not transport.acknowledged(payload):
                    if not self.journal.consent(scope) or not self.export_allowed(scope) or not self.journal.active(job):raise LeaseLost('Consent revoked')
                    transport.submit(payload)
            if not self.journal.consent(scope) or not self.export_allowed(scope):
                self.journal.request_deletion(job);return 'consent_revoked'
            ack=transport.acknowledged(payload)
            self.journal.update(job,'delivered' if ack else 'queued',phase='ack',error=None if ack else 'ack_pending',retry_delay=min(300,2**job['attempts']))
            return 'delivered' if ack else 'ack_pending'
        except LeaseLost:
            return 'lease_lost'
        except Exception:
            # No exception body, URL, credential or source record is persisted.
            try:self.journal.update(job,'queued',error='delivery_failed',retry_delay=min(300,2**job['attempts']))
            except LeaseLost:pass
            return 'delivery_failed'
        finally:
            if isinstance(transport,LangfuseTransport):transport.close()
