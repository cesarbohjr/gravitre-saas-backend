"""Real source capture, delivery boundaries and existing-job wakeup contracts."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.ml.registry import ModelRegistry
from app.ml.federated_adoption import wake_after_feedback, pending_adoption
from tests.ml.test_federated_adoption import prepared, ROUND, AUDIT


@pytest.mark.asyncio
async def test_registry_refuses_foreign_urls_and_model_paths_before_attaching_credentials():
    registry = ModelRegistry()
    registry._settings = SimpleNamespace(blob_read_write_token='vercel_blob_rw_example_testonly',blob_store_id='store_example')
    urls = ['https://attacker.example/models/model/v1.pkl',
            'http://example.private.blob.vercel-storage.com/models/model/v1.pkl',
            'https://other.private.blob.vercel-storage.com/models/model/v1.pkl',
            'https://example.private.blob.vercel-storage.com/models/foreign/v1.pkl',
            'https://example.private.blob.vercel-storage.com/models/model/v2.pkl',
            'https://example.private.blob.vercel-storage.com/models/model/v1.pkl?redirect=evil',
            'https://example.public.blob.vercel-storage.com/models/model/v1.pkl']
    with patch('app.ml.registry.httpx.AsyncClient') as client:
        for url in urls:
            with pytest.raises(ValueError):
                await registry._download_artifact(url,model_id='model',version=1)
        client.assert_not_called()


@pytest.mark.asyncio
async def test_registry_streams_only_the_own_private_version_with_no_redirects():
    registry = ModelRegistry()
    registry._settings = SimpleNamespace(blob_read_write_token='vercel_blob_rw_example_testonly')
    captured = {}
    class Response:
        status_code = 200
        headers = {'content-length':'3'}
        def raise_for_status(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def aiter_bytes(self): yield b'abc'
    class Client:
        def __init__(self,**kwargs): captured.update(kwargs)
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        def stream(self,method,url,headers): captured['headers']=headers; return Response()
    with patch('app.ml.registry.httpx.AsyncClient',Client):
        assert await registry._download_artifact('https://example.private.blob.vercel-storage.com/models/model/v1.pkl',model_id='model',version=1)==b'abc'
    assert captured['follow_redirects'] is False
    assert captured['headers']['Authorization']=='Bearer vercel_blob_rw_example_testonly'


@pytest.mark.asyncio
async def test_pre_feedback_capture_uses_actual_features_and_only_one_proxy_label_per_message():
    from app.services.rag_outcome_tracking import record_retrieval_outcomes
    client = MagicMock()
    docs, outcomes = MagicMock(),MagicMock()
    for query in (docs,outcomes):
        for name in ('select','eq','in_','insert'): getattr(query,name).return_value=query
    docs.execute.return_value = SimpleNamespace(data=[{'id':'doc','updated_at':(datetime.now(timezone.utc)-timedelta(days=5)).isoformat()}])
    client.table.side_effect=lambda name:docs if name=='rag_documents' else outcomes
    source = [{'id':'chunk','document_id':'doc','rerank_score':.7,'score':.9}]*2
    with patch('app.ml.training_consent.training_is_approved',AsyncMock(return_value=True)), patch(
        'app.ml.federated_learning.verified_privacy_profile',return_value=({},AUDIT)), patch(
        'app.ml.federated_adoption.artifact_permission',AsyncMock(return_value=True)):
        await record_retrieval_outcomes(MagicMock(),org_id='org',message_id='message',rows=source,reliability_scores={'doc':.6},client=client)
    payload = outcomes.insert.call_args.args[0]
    assert len(payload)==2 and sum('ranker_features' in row for row in payload)==1
    first = payload[0]
    assert first['ranker_features']['rerank_score']==.7
    assert first['ranker_features']['source_reliability_score']==.6
    assert first['ranker_features']['source_document_age_days']>=5
    assert first['ranker_features_observed_at']==first['recorded_at']
    assert first['outcome_helpful'] is None
    assert docs.eq.call_args.args==('org_id','org')
    outcomes.insert.reset_mock(); docs.select.reset_mock()
    with patch('app.ml.training_consent.training_is_approved',AsyncMock(return_value=False)):
        await record_retrieval_outcomes(MagicMock(),org_id='org',message_id='message',rows=source,reliability_scores={'doc':.6},client=client)
    assert all('ranker_features' not in row for row in outcomes.insert.call_args.args[0])
    docs.select.assert_not_called()


@pytest.mark.asyncio
async def test_feedback_wakes_existing_temporal_job_and_pending_validation_expires():
    store,_,_ = prepared()
    redis = MagicMock(); redis.set.return_value=True
    with patch('app.ml.training_consent.training_is_approved',AsyncMock(return_value=True)),patch(
        'app.ml.federated_learning.verified_privacy_profile',return_value=({},AUDIT)),patch(
        'app.core.redis_client.get_sync_redis',return_value=redis),patch(
        'app.temporal.starters.temporal_enabled',return_value=True),patch(
        'app.temporal.starters.start_company_intelligence_workflow',AsyncMock()) as start:
        await wake_after_feedback('org',MagicMock(),store)
        start.assert_awaited_once_with('org')
        store.settings['federated_adoption'][ROUND]['captured_at']=(datetime.now(timezone.utc)-timedelta(days=15)).isoformat()
        assert not await pending_adoption('org',MagicMock(),store)


@pytest.mark.asyncio
async def test_private_candidate_delivery_requires_membership_permission_and_finite_bounded_json(tmp_path,monkeypatch):
    pytest.importorskip('flwr')
    from app.ml.federated_runtime import control
    from app.ml.federated_runtime.privacy import feature_schema_digest
    monkeypatch.setenv('FEDERATED_RUNTIME_DATA_DIR',str(tmp_path))
    cohort = [str(uuid4()) for _ in range(100)]
    profile={'program_id':'test-only','feature_schema_sha256':feature_schema_digest()}
    (tmp_path/f'round-{ROUND}.json').write_text(json.dumps({'participants':cohort,'program_id':'test-only','audit_digest':AUDIT}))
    artifact={'schema':1,'parameters':[1,.2,0,0,0],'round_id':ROUND,'audit_digest':AUDIT,'feature_schema_sha256':feature_schema_digest()}
    destination=tmp_path/f'candidate-{ROUND}.json'; destination.write_text(json.dumps(artifact))
    from uuid import UUID
    with patch.object(control,'runtime_profile',return_value=(profile,AUDIT)),patch.object(
        control,'get_round',AsyncMock(return_value={'state':'completed'})),patch.object(control,'current_permission') as permission:
        assert (await control.read_candidate(ROUND,UUID(cohort[0])))==artifact
        permission.assert_called_once()
        with pytest.raises(HTTPException) as denied:
            await control.read_candidate(ROUND,uuid4())
        assert denied.value.status_code==403
        artifact['parameters'][0]=float('nan'); destination.write_text(json.dumps(artifact))
        with pytest.raises(HTTPException) as invalid:
            await control.read_candidate(ROUND,UUID(cohort[0]))
        assert invalid.value.status_code==409
