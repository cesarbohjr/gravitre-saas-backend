"""Independent corpus, signed audit, DP composition and real consumer contracts."""
import base64
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.ml.domain_llm import collect_domain_corpus, DomainSpecificLLMRouter
from app.ml.federated_learning import verified_privacy_profile


class Query:
    def __init__(self, rows, selections): self.rows, self.selections = list(rows), selections
    def select(self, columns): self.selections.append(columns); return self
    def eq(self, key, value): self.rows = [row for row in self.rows if row.get(key) == value]; return self
    def in_(self, key, values): self.rows = [row for row in self.rows if row.get(key) in values]; return self
    def order(self, *a, **k): return self
    def limit(self, count): self.rows = self.rows[:count]; return self
    def execute(self): return SimpleNamespace(data=self.rows)


def corpus_db():
    contract = {'model_name': 'domain_specific_llm', 'schema_version': 1, 'task_type': 'classification',
                'department': 'support', 'target_definition': 'routing', 'labels': ['a', 'b'], 'provider_base_model': 'gpt-base'}
    tables = {'trained_models': [{'id': 'target', 'org_id': 'org', 'base_model': 'domain_specific_llm'}],
        'training_dataset_bindings': [{'org_id': 'org', 'target_id': 'target', 'target_type': 'model', 'dataset_id': kind,
                                      'purpose': kind, 'metadata': contract} for kind in ('training', 'benchmark')],
        'training_records': [{'id': str(i), 'org_id': 'org', 'dataset_id': 'training' if i < 1000 else 'benchmark',
                             'input': f'unique case {i}', 'expected_output': ['a', 'b'][i % 2],
                             'metadata': {'synthetic': False, 'label_source': 'human_reviewed', 'source_ref': f'audit:{i}'}} for i in range(1100)]}
    selections = []
    return tables, selections, SimpleNamespace(table=lambda name: Query(tables[name], selections))


def test_domain_binding_is_org_scoped_and_benchmark_is_independent():
    tables, selections, db = corpus_db()
    with patch('app.workflows.repository.get_supabase_client', return_value=db):
        assert len(collect_domain_corpus('org', MagicMock())['benchmark']) == 100
        with pytest.raises(ValueError, match='target'): collect_domain_corpus('other-org', MagicMock())
        tables['training_records'][-1]['input'] = tables['training_records'][0]['input']
        with pytest.raises(ValueError, match='Duplicate'): collect_domain_corpus('org', MagicMock())
        collect_domain_corpus('org', MagicMock(), include_inputs=False)
        assert 'input' not in selections[-1].split(',')


def test_domain_datasets_cannot_share_training_and_benchmark_records():
    tables, _, db = corpus_db()
    tables['training_dataset_bindings'][-1]['dataset_id'] = 'training'
    with patch('app.workflows.repository.get_supabase_client', return_value=db):
        with pytest.raises(ValueError, match='Independent'): collect_domain_corpus('org', MagicMock())


def audit_settings(**updates):
    key = Ed25519PrivateKey.generate()
    payload = {'expires_at': (datetime.now(UTC)+timedelta(days=1)).isoformat(), 'protocol': 'flower_secaggplus',
        'privacy_unit': 'organization', 'adjacency': 'replace_one', 'accountant': 'rdp', 'transport': 'mutual_tls',
        'min_participants': 100, 'raw_data_egress': False, 'deployment_sha256': 'a'*64, 'audit_ref': 'test-only-audit',
        'legal_review_ref': 'test-only-legal', 'approved_by': 'independent-test-reviewer', 'program_id': 'test-program',
        'feature_schema_sha256': 'b'*64, 'node_registry_sha256':'c'*64, 'max_epsilon': 10.0, 'delta': 1e-5, 'noise_multiplier': 10.0,
        'clipping_norm': 1.0, 'max_rounds': 2, **updates}
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    envelope = {'payload': payload, 'signature': base64.b64encode(key.sign(encoded)).decode()}
    settings = SimpleNamespace(federated_audit_public_key=base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode(),
                               federated_audit_manifest=json.dumps(envelope))
    return settings, envelope


def test_audit_signature_and_real_rdp_composition_are_enforced():
    settings, envelope = audit_settings()
    profile, digest = verified_privacy_profile(settings)
    assert len(digest) == 64 and profile['min_participants'] == 100
    envelope['payload']['raw_data_egress'] = True
    settings.federated_audit_manifest = json.dumps(envelope)
    with pytest.raises(InvalidSignature): verified_privacy_profile(settings)
    settings, _ = audit_settings(max_epsilon=.0001)
    with pytest.raises(ValueError, match='composed privacy budget'): verified_privacy_profile(settings)


@pytest.mark.parametrize('change', [{'min_participants': 99}, {'privacy_unit': 'record'}, {'protocol': 'plain_average'},
                                   {'expires_at': (datetime.now(UTC)-timedelta(days=1)).isoformat()}])
def test_even_signed_unsupported_or_expired_profiles_stay_dormant(change):
    settings, _ = audit_settings(**change)
    with pytest.raises(ValueError): verified_privacy_profile(settings)


@pytest.mark.asyncio
async def test_domain_inference_uses_matching_deployed_model_and_contract():
    model = DomainSpecificLLMRouter()
    model.load(json.dumps({'schema': 1, 'fine_tuned_model_id': 'ft:org:trained', 'department': 'support',
                          'target_definition': 'routing', 'base_model': 'gpt-base', 'labels': ['a', 'b']}).encode())
    router = MagicMock()
    router.complete = AsyncMock(return_value=SimpleNamespace(content='a', model='ft:org:trained', model_call_id='trace'))
    with patch('app.ml.provider_execution.require_permission', AsyncMock()), patch('app.services.model_router.ModelRouter', return_value=router):
        result, _ = await model.predict([{'prompt': 'case', 'department': 'support', 'target_definition': 'routing'}], org_id='org')
        assert result == ['a'] and router.complete.call_args.kwargs['model_override'] == 'ft:org:trained'
        with pytest.raises(ValueError, match='semantics'):
            await model.predict([{'prompt': 'case', 'department': 'sales', 'target_definition': 'routing'}], org_id='org')
        router.complete.return_value.model = 'base-fallback'
        with pytest.raises(ValueError, match='validated label'):
            await model.predict([{'prompt': 'case', 'department': 'support', 'target_definition': 'routing'}], org_id='org')


@pytest.mark.asyncio
async def test_workflow_candidates_and_vetted_rules_reach_shared_model_boundary():
    from app.services.decision_service import DecisionService, DecisionPath
    service = DecisionService(MagicMock())
    with patch('app.ml.model_catalog.load_org_trained_catalog_model', AsyncMock(return_value=SimpleNamespace(_features=[]))), patch(
        'app.ml.model_catalog.infer_catalog_capability', AsyncMock(return_value={'status': 'ok', 'advisory_only': True})) as infer:
        result = await service._catalog_advice('org', {'deal_amount_before': 100}, [DecisionPath(id='follow_up', label='Follow up')],
                                              [{'field': 'deal_amount_before', 'operator': 'greater_than', 'value': 50, 'path_id': 'follow_up'}])
    calls = {call.args[1]: call for call in infer.call_args_list}
    assert calls['agentic_planning'].args[2]['inputs'] == [{'action': 'follow_up', 'deal_amount_before': 100}]
    assert calls['neuro_symbolic'].args[2]['rules'][0]['operator'] == 'gt'
    assert calls['agentic_planning'].kwargs['source'] == 'decision_service'
    assert result['agentic_planning']['advisory_only']


@pytest.mark.asyncio
async def test_federation_needs_100_distinct_current_tenant_approvals_before_network():
    from app.ml.federated_learning import FederatedLearningCoordinator
    from app.ml.training_consent import training_disclosure
    settings, _ = audit_settings()
    _, digest = verified_privacy_profile(settings)
    disclosure = training_disclosure('federated_learning')
    record = {'state':'approved', 'scope_digest':disclosure['scope_digest'],
              'sharing_scope':'cross_tenant_private_updates', 'audit_digest':digest}
    rows = [{'id':str(i % 99), 'settings':{'model_training_consents':{'federated_learning':record}}} for i in range(200)]
    client = MagicMock(); query = client.table.return_value
    query.select.return_value = query; query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    with patch('app.workflows.repository.get_supabase_client', return_value=client), patch('httpx.AsyncClient') as runtime:
        result = await FederatedLearningCoordinator().reconcile(org_id='0', settings=settings)
    assert result['participants'] == 99 and result['status'] == 'dormant'
    runtime.assert_not_called()
    assert query.select.call_args.args == ('id,settings',)


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign_dataset', [True, False])
async def test_existing_worker_never_trains_on_another_tenants_dataset_or_records(foreign_dataset):
    from app.workers.training_worker import TrainingWorker
    tables = {'training_jobs':[{'id':'job','org_id':'org','dataset_id':'dataset','model_base':'random_forest','created_by':'actor'}],
              'training_datasets':[{'id':'dataset','name':'private','org_id':'foreign' if foreign_dataset else 'org'}],
              'training_records':[{'dataset_id':'dataset','org_id':'foreign','input':'secret','expected_output':'a'}]}
    class WorkerQuery(Query):
        def update(self, *args, **kwargs): return self
    db = SimpleNamespace(table=lambda name: WorkerQuery(tables[name], []))
    worker = TrainingWorker()
    worker._get_client = lambda: db
    worker._train_classifier = AsyncMock()
    registry = MagicMock()
    registry.add_version = AsyncMock()
    with patch('app.workers.training_worker.get_model_registry', return_value=registry):
        await worker.process_job('job')
    worker._train_classifier.assert_not_awaited()
    registry.add_version.assert_not_awaited()


def test_domain_promotion_compares_the_same_holdout_and_rejects_changed_champion():
    from app.ml.intelligence_training import champion_challenger_decision
    contract = {'algorithm':'domain_classification_sft','department':'support','target_definition':'routing','domain_labels':'["a", "b"]'}
    old = {'accuracy':.60, 'custom_metrics':{**contract, 'fine_tuned_model':'ft:old'}}
    new = {'accuracy':.85, 'custom_metrics':{**contract,'fine_tuned_model':'ft:new',
        'compared_champion_model':'ft:old','compared_champion_accuracy':.90}}
    assert champion_challenger_decision(new, old, has_champion=True)[1] == 'challenger_worse_than_champion'
    new['custom_metrics']['compared_champion_accuracy'] = .80
    assert champion_challenger_decision(new, old, has_champion=True)[0]
    old['custom_metrics']['fine_tuned_model'] = 'ft:concurrent-replacement'
    assert champion_challenger_decision(new, old, has_champion=True)[1] == 'not_deployed_domain_champion_not_evaluated_on_current_holdout'


@pytest.mark.asyncio
async def test_domain_worker_uses_bound_data_and_independent_provider_evaluation_before_registration():
    from app.ml.domain_llm import execute_domain_training
    tables, selections, _ = corpus_db()
    job = {'id':'job','org_id':'org','dataset_id':'training','model_base':'domain_specific_llm','status':'training'}
    tables['training_jobs'] = [job.copy()]
    class MutableQuery(Query):
        def update(self, value): self.pending = value; return self
        def execute(self):
            for row in self.rows: row.update(getattr(self, 'pending', {}))
            return SimpleNamespace(data=self.rows)
    db = SimpleNamespace(table=lambda name: MutableQuery(tables[name], selections))
    trainer = SimpleNamespace(client=None, openai_job_id='provider-job', fine_tuned_model_id='ft:org:new',
        _training_file_id=None, _validation_file_id=None, train=AsyncMock(),
        get_job_status=AsyncMock(return_value={'status':'succeeded'}), get_training_metrics=AsyncMock(), cancel_job=AsyncMock())
    provider = MagicMock(); provider.models.retrieve = AsyncMock(); provider.close = AsyncMock()
    async def complete(**kwargs):
        label = ['a','b'][int(kwargs['prompt'].split()[-1]) % 2] if kwargs['model_override'] == 'ft:org:new' else 'a'
        return SimpleNamespace(content=label, model=kwargs['model_override'])
    router = MagicMock(); router.complete = AsyncMock(side_effect=complete)
    redis = MagicMock(); redis.set.return_value = True
    with patch('app.ml.provider_execution.require_permission', AsyncMock()), patch('app.ml.provider_execution.processing_policy', return_value={'model':'gpt-base'}), patch(
        'app.ml.provider_execution.reserve_provider_budget'), patch('app.core.redis_client.get_sync_redis', return_value=redis), patch(
        'app.workflows.repository.get_supabase_client', return_value=db), patch('app.ml.model_catalog.load_org_trained_catalog_model', AsyncMock(return_value=DomainSpecificLLMRouter())), patch(
        'app.ml.fine_tuning.FineTunedLLM', return_value=trainer), patch('openai.AsyncOpenAI', return_value=provider), patch(
        'app.services.model_router.ModelRouter', return_value=router), patch('app.ml.intelligence_training.register_trained_artifact_detailed', AsyncMock(return_value={'model_id':'registered','deployed':True})) as register:
        result = await execute_domain_training(job, MagicMock())
    assert result['model_id'] == 'registered'
    trainer.train.assert_awaited_once()
    assert len(trainer.train.call_args.kwargs['examples']) == 1000
    assert router.complete.await_count == 200
    metrics = register.call_args.kwargs['metrics']
    assert metrics.validation_samples == 100 and metrics.accuracy == 1 and metrics.custom_metrics['base_accuracy'] == .5
    artifact = DomainSpecificLLMRouter(); artifact.load(register.call_args.kwargs['artifact'])
    assert artifact.department == 'support' and artifact.fine_tuned_model_id == 'ft:org:new'
    assert tables['training_jobs'][0]['status'] == 'completed'
