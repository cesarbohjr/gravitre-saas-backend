"""Synthetic tenant-local adoption; no production consent or privacy approval."""
import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.ml.federated_adoption import (LEDGER, save_source_anchor, candidate_ranker,
    independent_holdout, evaluate, promotion_decision, adopt_candidate, artifact_permission)
from app.ml.federated_runtime.privacy import feature_schema_digest

ROUND, AUDIT = "a"*64, "b"*64
REF = {"model_id":"model", "version":1}


class Store:
    def __init__(self):
        self.settings = {}
        self.rows, self.versions, self.calls = [], [], []

    def table(self,name):
        return Query(self,name)


class Query:
    def __init__(self,store,table):
        self.store,self.name = store,table
        self.payload = None
        self.filters = []

    def select(self,*a,**kw): return self
    def limit(self,*a,**kw): return self
    def order(self,*a,**kw): return self
    @property
    def not_(self): return self
    def is_(self,*a,**kw): return self
    def gt(self,*a,**kw): self.filters.append(('gt',a)); return self
    def eq(self,*a,**kw): self.filters.append(('eq',a)); return self
    def update(self,payload): self.payload = payload; return self
    def execute(self):
        self.store.calls.append((self.name,self.filters,self.payload))
        if self.name == 'organizations':
            if self.payload:
                expected = next((args[1] for kind,args in self.filters if kind=='eq' and args[0]=='settings'),None)
                if expected != json.dumps(self.store.settings,sort_keys=True,separators=(',',':')):
                    return SimpleNamespace(data=[])
                self.store.settings = copy.deepcopy(self.payload['settings'])
            return SimpleNamespace(data=[{'settings':copy.deepcopy(self.store.settings)}])
        return SimpleNamespace(data=copy.deepcopy(self.store.rows if self.name=='rag_chunk_outcomes' else self.store.versions))


def observed_rows():
    now = datetime.now(timezone.utc)-timedelta(seconds=10)
    return [{'id':f'outcome-{i}','message_id':f'message-{i}', 'ranker_features':{
        'rerank_score':2. if i%2 else -2.,'source_reliability_score':.6,
        'rank_position':1,'source_document_age_days':10},
        'ranker_features_observed_at':now.isoformat(),'recorded_at':(now+timedelta(seconds=1)).isoformat(),
        'outcome_helpful':bool(i%2)} for i in range(100)]


def prepared():
    store = Store()
    save_source_anchor(store,'org',ROUND,AUDIT,REF,(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat())
    store.rows = observed_rows()
    champion = candidate_ranker([-1,.1,0,0,0],ROUND,AUDIT)
    champion.registry_ref = REF
    candidate = {'schema':1,'round_id':ROUND,'audit_digest':AUDIT,
        'feature_schema_sha256':feature_schema_digest(),'parameters':[3,.1,0,0,0]}
    return store,champion,candidate


def test_source_anchor_is_immutable_and_does_not_replace_security_settings():
    store,_,_ = prepared()
    first = copy.deepcopy(store.settings[LEDGER][ROUND])
    store.settings['security'] = {'keep':'unchanged'}
    assert save_source_anchor(store,'org',ROUND,AUDIT,REF,datetime.now(timezone.utc).isoformat()) == first
    assert store.settings['security'] == {'keep':'unchanged'}
    with pytest.raises(ValueError,match='overwrite'):
        save_source_anchor(store,'org',ROUND,AUDIT,{**REF,'version':2},first['captured_at'])


def test_holdout_requires_actual_future_snapshots_and_distinct_message_feedback():
    store,_,_ = prepared()
    anchor = store.settings[LEDGER][ROUND]
    assert len(independent_holdout(store,'org',anchor)[0]) == 100
    query = store.calls[-1]
    assert ('eq',('org_id','org')) in query[1]
    store.rows[-1]['message_id'] = store.rows[0]['message_id']
    assert independent_holdout(store,'org',anchor) is None
    store.rows = observed_rows()
    store.rows[0]['ranker_features_observed_at'] = anchor['captured_at']
    assert independent_holdout(store,'org',anchor) is None
    store.rows = observed_rows()
    store.rows[0]['ranker_features'].pop('source_reliability_score')
    assert independent_holdout(store,'org',anchor) is None


def test_real_logistic_evaluation_compares_same_holdout_and_roundtrips_existing_artifact():
    from app.ml.learning_to_rank import RetrievalRanker
    store,champion,document = prepared()
    holdout,digest = independent_holdout(store,'org',store.settings[LEDGER][ROUND])
    candidate = candidate_ranker(document['parameters'],ROUND,AUDIT)
    metrics = evaluate(candidate,champion,holdout,digest,ROUND,REF)
    assert promotion_decision(metrics.model_dump())[0]
    assert metrics.training_samples == 0 and metrics.validation_samples == 100
    loaded = RetrievalRanker(); loaded.load(candidate.save())
    assert loaded.federation == candidate.federation
    assert loaded.get_learned_weight() == pytest.approx(.1)
    rejected = evaluate(champion,candidate,holdout,digest,ROUND,REF)
    assert not promotion_decision(rejected.model_dump())[0]
    malformed = metrics.model_dump(); malformed['custom_metrics']['compared_champion_version']=0
    assert not promotion_decision(malformed)[0]


@pytest.mark.asyncio
async def test_adoption_uses_shared_registry_once_and_rejects_stale_champion():
    store,champion,document = prepared()
    registration = AsyncMock(return_value={'deployed':True,'model_id':'model','version':2,'reason':'passed'})
    with patch('app.ml.federated_learning.verified_privacy_profile',return_value=({},AUDIT)), patch(
        'app.ml.training_consent.training_is_approved',AsyncMock(return_value=True)), patch(
        'app.ml.federated_adoption.artifact_permission',AsyncMock(return_value=True)), patch(
        'app.ml.model_catalog.load_org_trained_catalog_model',AsyncMock(return_value=champion)), patch(
        'app.ml.intelligence_training.register_trained_artifact_detailed',registration):
        assert (await adopt_candidate('org',ROUND,document,MagicMock(),store))['state']=='adopted'
        assert (await adopt_candidate('org',ROUND,document,MagicMock(),store))['state']=='adopted'
    assert registration.await_count == 1
    assert registration.call_args.kwargs['name']=='company-retrieval-ranker'
    store,champion,document = prepared(); champion.registry_ref = {**REF,'version':3}
    with patch('app.ml.federated_learning.verified_privacy_profile',return_value=({},AUDIT)), patch(
        'app.ml.training_consent.training_is_approved',AsyncMock(return_value=True)), patch(
        'app.ml.federated_adoption.artifact_permission',AsyncMock(return_value=True)), patch(
        'app.ml.model_catalog.load_org_trained_catalog_model',AsyncMock(return_value=champion)), patch(
        'app.ml.intelligence_training.register_trained_artifact_detailed',registration):
        assert (await adopt_candidate('org',ROUND,document,MagicMock(),store))['state']=='stale_champion'
    assert registration.await_count == 1


@pytest.mark.asyncio
async def test_uncertain_registration_requires_source_readback_instead_of_duplicate_version():
    store,champion,document = prepared()
    registration = AsyncMock(side_effect=TimeoutError('test-only lost source response'))
    with patch('app.ml.federated_learning.verified_privacy_profile',return_value=({},AUDIT)), patch(
        'app.ml.training_consent.training_is_approved',AsyncMock(return_value=True)), patch(
        'app.ml.federated_adoption.artifact_permission',AsyncMock(return_value=True)), patch(
        'app.ml.model_catalog.load_org_trained_catalog_model',AsyncMock(return_value=champion)), patch(
        'app.ml.intelligence_training.register_trained_artifact_detailed',registration):
        with pytest.raises(TimeoutError):
            await adopt_candidate('org',ROUND,document,MagicMock(),store)
        assert (await adopt_candidate('org',ROUND,document,MagicMock(),store))['state']=='registration_reconciliation_required'
    assert registration.await_count == 1


@pytest.mark.asyncio
async def test_revoked_federation_permission_blocks_composed_artifact_but_preserves_local_artifacts():
    candidate = candidate_ranker([1,.2,0,0,0],ROUND,AUDIT)
    assert await artifact_permission('org',SimpleNamespace(federation=None),MagicMock())
    with patch('app.ml.federated_learning.verified_privacy_profile',return_value=({},AUDIT)), patch(
        'app.ml.training_consent.load_training_consents',return_value={}),patch(
        'app.ml.training_consent.consent_is_approved',return_value=False):
        assert not await artifact_permission('org',candidate,MagicMock())
        assert not await artifact_permission('org',SimpleNamespace(_ranker=candidate),MagicMock())


@pytest.mark.parametrize("parameters", [[True,0,0,0,0], ["1",0,0,0,0], [float("nan"),0,0,0,0], [1,2]])
def test_candidate_refuses_coerced_or_nonfinite_parameters(parameters):
    with pytest.raises(ValueError,match="Five finite"):
        candidate_ranker(parameters,ROUND,AUDIT)
