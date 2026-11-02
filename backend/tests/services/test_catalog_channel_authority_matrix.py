"""Catalog-wide shared channel boundaries; not provider/product certification.

Every agent's two prompt builders consume the same progressive contract. Every
implemented connector's read/write representatives pass real scope/cancellation
checks. External executors are never called, and passing grants no authority.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import pytest
from app.marketplace.seed_catalog import list_catalog_assets
from app.services.agent_connector_profile import resolve_profile,prompt_section
from app.operators.agent_prompts import build_agent_system_prompt,build_agent_instructions_section
from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.services.tool_service import list_registered_actions
from app.services.agent_tool_permissions import assert_agent_tool_permission,required_scopes_for_action
from app.services.outcome_verification import is_write_action
from app.services.tool_types import ToolContext,ToolPermissionDeniedError,ToolValidationError
from app.services.turn_cancellation import TurnCancellation,bound_turn_cancellation
from app.services.voice_barge_in_write import raise_if_barge_in_blocks_invoke
from tests.support.fake_supabase import FakeSupabase

ORG='11111111-1111-4111-8111-111111111111';AGENT='22222222-2222-4222-8222-222222222222';ACTOR='33333333-3333-4333-8333-333333333333'
AGENTS=[asdict(a) for a in list_catalog_assets() if a.asset_type=='ai_agent']
registered=set(list_registered_actions());representatives={}
for spec in all_catalog_action_specs():
    if spec.id in registered:
        key=(spec.id.split('.')[0],is_write_action(spec.id))
        representatives.setdefault(key,spec)
ACTIONS=tuple(representatives.values());WRITES=tuple(s for s in ACTIONS if is_write_action(s.id))
STATES=('disconnected','connected_without_grants','revoked','expired','partial','foreign')

@pytest.mark.parametrize('asset',AGENTS,ids=lambda a:a['slug'])
@pytest.mark.parametrize('state',STATES)
def test_every_agent_preserves_channel_guidance_and_never_grants_execution(asset,state):
    agent=deepcopy(asset['config']);agent.update(id=AGENT,org_id=ORG)
    agent.setdefault('config',{})['marketplaceSlug']=asset['slug']
    profile=resolve_profile(agent,org_id=ORG,connectors=[])
    connectors=[]
    for item in profile['recommendations']:
        row={'org_id':ORG,'type':item['connectorType'],'status':'active'}
        if state=='disconnected':continue
        if state=='revoked':row['status']='revoked'
        if state=='expired':row['status']='expired'
        if state=='foreign':row['org_id']='other-org'
        connectors.append(row)
    current=resolve_profile(agent,org_id=ORG,connectors=connectors)
    assert current['offlineCapabilities']
    for row in current['recommendations']:
        assert row['canExecute'] is False
        if not row['supported']:assert row['state']=='not_supported' and row['connectPath'] is None
        elif state in ('revoked','expired'):assert row['state']=='needs_attention'
        elif state in ('disconnected','foreign'):assert row['state']=='available'
        else:assert row['state']=='connected'
    shared=prompt_section(agent)
    assert shared in build_agent_system_prompt(agent)
    assert shared in build_agent_instructions_section(agent)
    assert 'checked for every action' in shared

@pytest.mark.parametrize('spec',ACTIONS,ids=lambda s:s.id)
@pytest.mark.parametrize('state',('granted','missing','expired','partial','foreign','revoked'))
def test_every_implemented_connector_uses_scoped_fresh_permissions(spec,state,mock_settings):
    database=FakeSupabase();vendor=spec.id.split('.')[0];ctype='platform' if vendor=='assistant' else vendor
    grant={'org_id':ORG,'agent_id':AGENT,'connector_id':None,'connector_type':ctype,'scopes':required_scopes_for_action(spec.id),'expires_at':None}
    if state=='expired':grant['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    if state=='partial':grant['scopes']=[]
    if state=='foreign':grant['org_id']='other-org'
    database.tables['agent_tool_permissions']=[] if state in ('missing','revoked') else [grant]
    context=ToolContext(mock_settings,database,ORG,ACTOR,agent_id=AGENT)
    if state=='granted':assert_agent_tool_permission(context,spec.id,None,ctype)
    else:
        with pytest.raises(ToolPermissionDeniedError):assert_agent_tool_permission(context,spec.id,None,ctype)
    # A fresh read must see revocation immediately; no reinstall or new session.
    database.tables['agent_tool_permissions']=[]
    with pytest.raises(ToolPermissionDeniedError):assert_agent_tool_permission(context,spec.id,None,ctype)

@pytest.mark.parametrize('spec',WRITES,ids=lambda s:s.id)
def test_every_connector_write_stays_fenced_across_new_text_or_voice_turn(spec,mock_settings):
    context=ToolContext(mock_settings,FakeSupabase(),ORG,ACTOR,agent_id=AGENT)
    old=TurnCancellation();old.cancel('fixture_interrupt')
    with bound_turn_cancellation(old):
        with pytest.raises(ToolValidationError):raise_if_barge_in_blocks_invoke(context,spec.id)
        fresh=TurnCancellation()
        with bound_turn_cancellation(fresh):raise_if_barge_in_blocks_invoke(context,spec.id)
        with pytest.raises(ToolValidationError):raise_if_barge_in_blocks_invoke(context,spec.id)
