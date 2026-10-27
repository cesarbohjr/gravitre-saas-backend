"""Per-cell production-boundary contracts; external I/O is synthetic, never live-certified."""
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.services.intelligence_router import CAPABILITY_NAMES, intelligence_context_block
from tests.operators.test_agent_intelligence import agent_row, intelligence  # noqa: F401
from tests.services.test_phase2_intelligence_coordination import router

SURFACES = ('flows','plays','agents','workflows','connectors','knowledge','memory','governance')
SCENARIOS = ('customer_support','sales_operations','it_incident_management')

async def packet(capability, marker):
    service = router()
    service._get_predictions.return_value = {'status':'available','observation':marker}
    service._get_causal_analysis.return_value = {'status':'correlational_fallback','observation':marker,'causation_established':False}
    service._get_adaptive_context.return_value = {'status':'available','observation':marker,'verified_sample_count':100}
    result = await service._run_enrichments('org-1', marker, {
        'requires_prediction':True,'requires_causal':True,'requires_graph':True}, {
        'understanding':{'goal':marker,'temporal_references':[marker]},
        'sentiment':{'recommended_adaptation':'offer_options','observation':marker},
        'graph_context':{'observation':marker,'relatedEntities':[{'id':marker}]}})
    assert marker in json.dumps(result['capabilities'][capability])
    return {'capabilities':{capability:result['capabilities'][capability]}}

async def flow_probe(evidence):
    from app.services.unified_turn_reasoning_service import run_unified_turn_shadow
    from tests.services.test_unified_turn_reasoning import _mock_stream_client, _mock_narrowed
    client = _mock_stream_client(content='Review evidence; approval remains required.')
    model = MagicMock(_openai=client)
    settings = MagicMock(unified_turn_shadow_enabled=True,unified_turn_shadow_max_tools=24,
        unified_turn_embedding_tool_retrieval=False,unified_turn_task_max_tools=16,
        unified_turn_task_model_tier='',openai_api_key='sk-test')
    with patch('app.services.unified_turn_reasoning_service.get_tool_registry') as registry, patch(
        'app.services.unified_turn_reasoning_service.get_model_router',return_value=model), patch(
        'app.services.unified_turn_reasoning_service.narrow_tools_for_turn',return_value=_mock_narrowed([])):
        registry.return_value.get_tools_for_agent.return_value=[]
        await run_unified_turn_shadow(org_id='org-1',user_id='user-1',conversation_id='conversation',
            message='Review risk',task_state={},conversation_history=[],connected_integrations=[],
            settings=settings,classification={'intelligence_context':evidence})
    return client.chat.completions.create.await_args.kwargs['messages'][-1]['content']

async def agent_probe(intelligence, agent_row, block, monkeypatch, surface):
    client=MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value=SimpleNamespace(data=[])
    monkeypatch.setattr('app.services.execution_intelligence_context.execution_intelligence_context',AsyncMock(return_value=block))
    monkeypatch.setattr('app.operators.agent_intelligence.load_agent_task_history',lambda *a,**k:[])
    monkeypatch.setattr('app.operators.agent_intelligence.write_audit_event',lambda *a,**k:None)
    if surface=='workflows':
        from app.services.handoff_service import run_agent_task
        monkeypatch.setattr('app.services.handoff_service.get_supabase_client',lambda *_:client)
        monkeypatch.setattr('app.operators.agent_intelligence.get_agent_intelligence',lambda:intelligence)
        await run_agent_task(intelligence.settings,org_id='org-1',agent=agent_row,
            task='Review evidence',run_id='run-1',actor_id='user-1')
    else:
        await intelligence.execute_task(org_id='org-1',agent=agent_row,task='Review evidence',client=client)
    return intelligence.react_engine.run.await_args.kwargs['system_prompt']

async def play_probe(block, monkeypatch):
    from app.routers import plays
    client=MagicMock()
    monkeypatch.setattr(plays,'get_supabase_client',lambda *_:client)
    monkeypatch.setattr(plays,'_load_installation',lambda *a,**k:{'id':'inst-1','operating_mode':'ACT WITH APPROVAL'})
    monkeypatch.setattr(plays,'connected_vendors',lambda *a:set())
    monkeypatch.setattr(plays,'resolve_play_readiness',lambda *a,**k:SimpleNamespace(act_with_approval_ready=True))
    monkeypatch.setattr(plays,'_observed_signals',lambda *a:[])
    monkeypatch.setattr(plays,'list_play_workflow_bindings',lambda *a:[{'workflowId':'11111111-1111-4111-8111-111111111111'}])
    monkeypatch.setattr(plays,'get_workflow_def',lambda *a:{'id':'11111111-1111-4111-8111-111111111111'})
    monkeypatch.setattr(plays,'resolve_policy',lambda *a:(1,['admin']))
    monkeypatch.setattr(plays,'write_audit_event',lambda *a,**k:None)
    monkeypatch.setattr('app.services.work_loop_links.resolve_run_links',lambda *a,**k:(None,None))
    enrich=AsyncMock(return_value=block)
    monkeypatch.setattr('app.services.execution_intelligence_context.execution_intelligence_context',enrich)
    execute=AsyncMock(return_value={'run_id':'run-1','status':'awaiting_approval','approval_required':True})
    monkeypatch.setattr('app.routers.workflows.execute_workflow',execute)
    response=await plays.run_play('customer-rescue',plays.RunPlayRequest(installationId='inst-1'),
        ({'user_id':'user-1'},'org-1','admin'),'production',SimpleNamespace())
    assert response['status']=='awaiting_approval'
    assert enrich.await_args.kwargs['org_id']=='org-1'
    assert execute.await_args.kwargs['org_id']=='org-1'
    return execute.await_args.args[0].parameters['intelligence_evidence']

@pytest.mark.asyncio
@pytest.mark.parametrize('scenario',SCENARIOS)
@pytest.mark.parametrize('surface',SURFACES)
@pytest.mark.parametrize('capability',CAPABILITY_NAMES)
async def test_capability_surface_boundary(capability,surface,scenario,intelligence,agent_row,monkeypatch):
    marker=f'{scenario}:{capability}:source-record-1'
    evidence=await packet(capability,marker)
    block=intelligence_context_block(evidence)
    assert 'grants no permissions or approval' in block
    observed=''
    if surface=='flows':
        observed=await flow_probe(evidence)
    elif surface in ('agents','workflows'):
        observed=await agent_probe(intelligence,agent_row,block,monkeypatch,surface)
    elif surface=='plays':
        observed=await play_probe(block,monkeypatch)
    elif surface=='knowledge':
        from app.services.unified_retrieval_service import UnifiedRetrievalService
        rag=MagicMock(retrieve_hybrid_rows=AsyncMock(return_value=([
            {'id':'chunk-1','content':block,'score':.9,'title':'Evidence','metadata':{'source_id':'source-1'}}],{})))
        service=UnifiedRetrievalService(settings=SimpleNamespace(rag_top_k=5),rag_service=rag)
        rows,_=await service.retrieve_knowledge_rows(org_id='org-1',query='Review evidence',top_k=5,
            environment_name='production',agent_id='agent-1')
        assert rag.retrieve_hybrid_rows.await_args.args[0]=='org-1'
        observed=rows[0]['content']
    elif surface=='memory':
        from app.services.agent_memory_service import format_retrieval_prompt_section
        observed=format_retrieval_prompt_section({'memories':[{'content':block}],'rag_chunks':[]})
    elif surface=='connectors':
        from app.services.react_write_gate import block_react_write_execution,WRITE_APPROVAL_REQUIRED
        from app.services.tool_registry import get_tool_registry
        result=block_react_write_execution('apollo_lists_create',{'name':marker,'intelligence_evidence':block},get_tool_registry())
        assert result['error_code']==WRITE_APPROVAL_REQUIRED
        assert result['success'] is False and result['pending_approval'] is True
        observed=json.dumps(result)
    elif surface=='governance':
        from app.services import voice_pause_gate
        from app.services.voice_barge_in_write import begin_write_effect,reset_write_effects_for_tests
        from app.services.tool_types import ToolValidationError
        ctx=SimpleNamespace(org_id='org-1',conversation_id=marker,settings=SimpleNamespace(),intelligence_evidence=block)
        monkeypatch.setattr('app.services.chat_turn_cancel_service.is_stop_requested',lambda *a,**k:False)
        voice_pause_gate.pause(ctx.org_id,ctx.conversation_id)
        try:
            with pytest.raises(ToolValidationError,match='Paused before sending'):
                begin_write_effect(ctx,'gmail.send')
            observed=ctx.intelligence_evidence
        finally:
            voice_pause_gate.end_pause(ctx.org_id,ctx.conversation_id)
            reset_write_effects_for_tests()
    assert marker in observed,(capability,surface,observed)
    assert capability in observed
    output=os.environ.get('SEVEN_INTELLIGENCE_EVIDENCE_DIR')
    if output:
        sha=os.environ.get('GITHUB_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        record={'cell_id':f'{capability}:{surface}','scenario_id':scenario,'status':'PASS_OFFLINE_CONTRACT',
            'commit_sha':sha,'seed':1000,'test_selector':f'tests/e2e/test_seven_intelligence_cross_surface.py::test_capability_surface_boundary[{capability}-{surface}-{scenario}]',
            'evidence_scope':'production_boundary_with_synthetic_external_io','observed':marker,'expected':marker,
            'write_attempts':int(surface=='governance'),'writes_committed':0,'approval_state':'not_granted','provider_readback':None}
        dest=Path(output)/f'{capability}-{surface}-{scenario}.json'
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(record,indent=2)+'\n')
