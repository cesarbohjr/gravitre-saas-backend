"""Seven-capability coordination with real router/prompt code and scripted I/O."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.intelligence_router import CAPABILITY_NAMES, IntelligenceRouter, intelligence_context_block
from tests.services.test_phase2_intelligence_coordination import router


@pytest.mark.asyncio
async def test_deferred_turn_never_starts_any_optional_provider_even_with_classification_flags():
    service = router()
    service._run_catalog_capabilities = AsyncMock()
    with patch('app.services.intelligence_router.get_knowledge_graph_service') as graph:
        result = await service._run_enrichments('org-a','review',{
            'requires_prediction':True,'requires_causal':True,'requires_graph':True,'department':'operations',
        },{'defer_optional':True,'catalog_model_inputs':{'world_model':{'inputs':[{'real':1}]}}})
    for provider in (service._get_predictions,service._get_causal_analysis,
                     service._get_adaptive_context,service._run_catalog_capabilities):
        provider.assert_not_awaited()
    graph.assert_not_called()
    assert all(result['capabilities'][key]['status']=='deferred'
               for key in ('predictive','causal','relational','adaptive'))
    assert result['models']['world_model']['status']=='deferred'


@pytest.mark.asyncio
async def test_temporal_absence_and_disabled_sentiment_are_not_available_claims():
    result = await router()._run_enrichments('org-a','review',{}, {
        'sentiment':{'recommended_adaptation':'none'},'sentiment_detection_enabled':False})
    assert result['capabilities']['temporal']['status']=='not_requested'
    assert result['capabilities']['sentiment']['status']=='disabled'
    assert result['capabilities']['sentiment']['data']=={'status':'disabled'}


@pytest.mark.asyncio
async def test_relational_resolution_reuses_scoped_known_nodes_without_extra_model_call():
    service = router()
    graph = MagicMock()
    graph.explain_entity = AsyncMock(return_value={'relatedEntities':[{'id':'related'}]})
    client = MagicMock()
    with patch('app.workflows.repository.get_supabase_client',return_value=client), patch(
        'app.services.graph_query_intent.resolve_entity_from_knowledge_nodes',
        return_value={'entity_type':'company','entity_id':'known-node'}) as resolve, patch(
        'app.services.intelligence_router.get_knowledge_graph_service',return_value=graph):
        result = await service._run_enrichments('org-a','How is Acme related?',{'requires_graph':True},{})
    resolve.assert_called_once_with('org-a','How is Acme related?',client=client)
    graph.explain_entity.assert_awaited_once_with('org-a','company','known-node',settings=service.settings)
    graph.answer_business_question.assert_not_called()
    assert result['capabilities']['relational']['data']['relatedEntities']==[{'id':'related'}]


@pytest.mark.asyncio
async def test_unmatched_entity_stays_unknown_without_guessed_identifier():
    service = router()
    with patch('app.workflows.repository.get_supabase_client'), patch(
        'app.services.graph_query_intent.resolve_entity_from_knowledge_nodes',return_value=None), patch(
        'app.services.intelligence_router.get_knowledge_graph_service') as graph:
        result = await service._get_relational_context('org-a','unknown account')
    assert result['status']=='insufficient_entity_match'
    graph.assert_not_called()


@pytest.mark.asyncio
async def test_catalog_outputs_reach_semantic_consumers_and_keep_service_disclosures():
    service = router()
    models = {'graph_neural_network':{'status':'ok','used_fallback':False,'predictions':[.8]},
              'causal_impact_analyzer':{'status':'ok','used_fallback':False,'confidence_note':'not causal proof'},
              'meta_learning':{'status':'ok','used_fallback':False,'predictions':[.7]},
              'intent_classifier':{'status':'ok','used_fallback':False,'predictions':['analytics']}}
    service._run_catalog_capabilities = AsyncMock(return_value=models)
    result = await service._run_enrichments('org-a','review',{'requires_causal':True},{
        'catalog_model_inputs':{key:{} for key in models},'understanding':{'goal':'review'}})
    caps = result['capabilities']
    for model,key in (('graph_neural_network','relational'),('causal_impact_analyzer','causal'),
                      ('meta_learning','adaptive'),('intent_classifier','contextual')):
        assert caps[key]['status']=='available'
        assert caps[key]['data']['catalog_models'][model]==models[model]
    assert caps['causal']['data']['service_evidence']['status']=='correlational_fallback'
    assert caps['predictive']['status']=='not_requested'
    assert 'not causal proof' in intelligence_context_block(result)


@pytest.mark.asyncio
async def test_failed_catalog_does_not_erase_available_domain_prediction():
    service = router()
    service._get_predictions.return_value={'status':'available','predictions':{'revenue':{'status':'ok'}}}
    service._run_catalog_capabilities = AsyncMock(return_value={
        'world_model':{'status':'dormant','used_fallback':True,'reason':'permission_inactive'}})
    result = await service._run_enrichments('org-a','forecast',{'requires_prediction':True},
        {'catalog_model_inputs':{'world_model':{}}})
    assert result['capabilities']['predictive']['status']=='available'
    assert result['capabilities']['predictive']['data']['service_evidence']['predictions']['revenue']['status']=='ok'
    assert result['models']['world_model']['used_fallback']


@pytest.mark.asyncio
async def test_catalog_timeout_stays_visible_for_the_requested_model(monkeypatch):
    import asyncio
    service = router()
    async def slow(*args): await asyncio.Event().wait()
    service._run_catalog_capabilities = slow
    monkeypatch.setattr('app.services.intelligence_router.ENRICHMENT_TIMEOUT_SECONDS',.01)
    result = await service._run_enrichments('org-a','review',{},
        {'catalog_model_inputs':{'graph_neural_network':{}}})
    assert result['capabilities']['relational']['status']=='unavailable'
    assert result['models']['graph_neural_network']['reason']=='timeout'


@pytest.mark.asyncio
@pytest.mark.parametrize('domain',['sales',{'department_key':'sales'}])
async def test_domain_strings_and_structured_domains_route_to_the_same_existing_engine(domain):
    service = router()
    engine = MagicMock(DOMAIN_PREDICTION_PACKS={'sales':[]})
    engine.run_domain_predictions = AsyncMock(return_value={'predictions':{}})
    with patch('app.services.predictive_operations_engine.get_predictive_operations_engine',return_value=engine):
        result = await IntelligenceRouter._get_predictions(service,'org-a',{'domain':domain})
    engine.run_domain_predictions.assert_awaited_once_with('org-a','sales')
    assert result['status']=='insufficient_data'


@pytest.mark.asyncio
async def test_one_failing_predictive_model_preserves_successful_siblings():
    from app.services.predictive_operations_engine import PredictiveOperationsEngine
    engine = PredictiveOperationsEngine(SimpleNamespace())
    engine.DOMAIN_PREDICTION_PACKS={'operations':['good','broken']}
    async def predict(org,name):
        assert org=='org-a'
        if name=='broken': raise ValueError('private provider details')
        return {'status':'ok','predictions':[.7]}
    engine._predict_model = predict
    result = await engine.run_domain_predictions('org-a','operations')
    assert result['predictions']['good']['status']=='ok'
    assert result['predictions']['broken']['status']=='unavailable'
    assert 'private provider' not in str(result)


@pytest.mark.asyncio
async def test_actual_loaded_model_output_reaches_router_through_existing_domain_engine():
    from app.ml.anomaly import AnomalyDetector
    from app.services.predictive_operations_engine import PredictiveOperationsEngine
    trained = AnomalyDetector(n_estimators=10)
    await trained.train([{'duration_ms':1000+i*10,'step_count':2,'error_count':0,'retry_count':0}
                         for i in range(40)])
    loaded = AnomalyDetector(); loaded.load(trained.save())
    loaded.registry_ref={'model_id':'actual-test-artifact','version':2}
    service = router()
    service._get_predictions = IntelligenceRouter._get_predictions.__get__(service,IntelligenceRouter)
    engine = PredictiveOperationsEngine(service.settings)
    engine.DOMAIN_PREDICTION_PACKS={'operations':['workflow_anomaly_detector']}
    observed=[{'run_id':'observed-run','duration_ms':900000,'step_count':2,
               'error_count':0,'retry_count':0,'graph_features_from_snapshot':True,'is_approximated':False}]
    with patch('app.services.predictive_operations_engine.get_predictive_operations_engine',return_value=engine), patch(
        'app.ml.training_consent.training_is_approved',AsyncMock(return_value=True)), patch(
        'app.ml.feature_extraction.collect_workflow_run_features',return_value=observed) as collect, patch(
        'app.ml.model_catalog.load_org_trained_catalog_model',AsyncMock(return_value=loaded)) as load, patch(
        'app.ml.inference_evidence.record_execution',AsyncMock(return_value={'recorded':False,'scope':'inference_execution_only'})):
        result = await service._run_enrichments('org-a','Review workflow anomalies',
            {'department':'operations','requires_prediction':True},{})
    collect.assert_called_once_with(service.settings,'org-a')
    load.assert_awaited_once_with('org-a','workflow_anomaly_detector',settings=service.settings)
    prediction=result['prediction']['predictions']['workflow_anomaly_detector']
    assert prediction['status']=='ok' and prediction['used_fallback'] is False
    assert prediction['predictions']==[True] and prediction['run_ids']==['observed-run']
    assert prediction['registry_ref']==loaded.registry_ref
    assert result['capabilities']['predictive']['status']=='available'
    assert 'actual-test-artifact' in intelligence_context_block(result)
    assert 'not a forecast of unobserved future runs' in intelligence_context_block(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('spoken',[False,True])
async def test_actual_shared_turn_model_call_receives_all_seven_router_contributions(spoken):
    from app.services.unified_turn_reasoning_service import run_unified_turn_shadow
    from tests.services.test_unified_turn_reasoning import _mock_stream_client, _mock_narrowed
    service = router()
    service._get_predictions.return_value={'status':'available','predictions':{'workflow':{'status':'ok','predictions':[.7]}}}
    evidence = await service._run_enrichments('org-a','review',{'requires_prediction':True,'requires_causal':True},{
        'understanding':{'goal':'review','temporal_references':['yesterday']},
        'sentiment':{'recommended_adaptation':'reduce_verbosity'},'graph_context':{'entityId':'known'}})
    client = _mock_stream_client(content='Review the measured evidence before acting.')
    model_router = MagicMock(); model_router._openai=client
    settings = MagicMock(unified_turn_shadow_enabled=True,unified_turn_shadow_max_tools=24,
        unified_turn_embedding_tool_retrieval=False,unified_turn_task_max_tools=16,
        unified_turn_task_model_tier='',openai_api_key='sk-test')
    with patch('app.services.unified_turn_reasoning_service.get_tool_registry') as registry, patch(
        'app.services.unified_turn_reasoning_service.get_model_router',return_value=model_router), patch(
        'app.services.unified_turn_reasoning_service.narrow_tools_for_turn',return_value=_mock_narrowed([])):
        registry.return_value.get_tools_for_agent.return_value=[]
        await run_unified_turn_shadow(org_id='org-a',user_id='user',conversation_id='conversation',
            message='Review operations risks',task_state={},conversation_history=[],connected_integrations=[],
            settings=settings,spoken_mode=spoken,classification={'intelligence_context':evidence})
    messages=client.chat.completions.create.await_args.kwargs['messages']
    content=messages[-1]['content']
    assert all(f'"{key}"' in content for key in CAPABILITY_NAMES)
    assert 'yesterday' in content and 'known' in content and 'reduce_verbosity' in content
    assert 'correlational_fallback' in content and 'disabled' in content
    assert 'grants no permissions or approval' in content
