"""Approved software tranche, canonical Marketplace lifecycle and shared prompts."""
from copy import deepcopy
from dataclasses import asdict
from uuid import NAMESPACE_URL,uuid5
import pytest
from app.capabilities.software_roles import ROLES,reference,render_software_role
from app.marketplace.agency_agents_catalog import load_agency_inventory
from app.marketplace.seed_catalog import catalog_assets_by_slug
from app.marketplace.seed_service import upsert_catalog_asset
from app.marketplace.service import install_asset,preview_install,MarketplaceError
from app.operators.agent_prompts import build_agent_system_prompt,build_agent_instructions_section
from tests.marketplace.test_approved_agency_enrichment import db

@pytest.mark.parametrize('role',ROLES,ids=lambda r:r['target_slug'])
def test_software_lifecycle_and_shared_guidance_without_connectors(db,role):
    asset=catalog_assets_by_slug()[role['target_slug']]
    old=asdict(asset);old['config']['config'].pop('software_guidance')
    row={**old,'id':str(uuid5(NAMESPACE_URL,asset.slug)),'org_id':None,'publisher_id':'publisher','status':'published','visibility':'public','current_version':1,'required_permissions':[]}
    db.tables['marketplace_assets']=[row]
    snapshot={'asset_id':row['id'],'version_number':1,'published_at':'2026-10-28T00:00:00Z',**{k:deepcopy(row[k]) for k in ('config','required_connectors','required_permissions','install_variables')}}
    db.tables['marketplace_asset_versions']=[deepcopy(snapshot)]
    installed=install_asset(db,'org-a',row['id'],actor_id='admin',environment_name='test')
    agent_id=installed['entities']['agentId']
    assert not render_software_role(db.rows('agents',id=agent_id)[0])
    upsert_catalog_asset(db,'publisher',asset)
    assert row['current_version']==2 and db.tables['marketplace_asset_versions'][0]==snapshot
    preview=preview_install(db,'org-a',row['id'],environment_name='test')
    assert preview['canInstall'] and preview['connectorProfile']['recommendations']
    upgrade=install_asset(db,'org-a',row['id'],actor_id='admin',environment_name='test')
    assert upgrade['entities']['agentId']==agent_id
    agent=db.rows('agents',id=agent_id)[0];text=render_software_role(agent)
    assert text and text in build_agent_system_prompt(agent) and text in build_agent_instructions_section(agent)
    rolled=install_asset(db,'org-a',row['id'],actor_id='admin',environment_name='test',version_number=1)
    assert rolled['entities']['agentId']==agent_id and not render_software_role(db.rows('agents',id=agent_id)[0])
    assert db.permissions.call_count==len(asset.config['systems']) and not db.tables.get('connectors')
    db.tables['marketplace_asset_versions'][-1]['published_at']=None
    with pytest.raises(MarketplaceError,match='publication is incomplete'):
        install_asset(db,'org-a',row['id'],actor_id='admin',force=True)



def test_exact_software_source_census_exclusions_and_governance():
    from app.capabilities.software_roles import EXCLUDED
    inventory=load_agency_inventory()['agents']
    sources={r['slug']:r for r in inventory}
    included=[s for r in ROLES for s in r['sources']]
    assert len({s['slug'] for s in included})==len(included)==70
    engineering={r['slug'] for r in inventory if r['division']=='engineering'}
    excluded={r['source_slug'] for r in EXCLUDED}
    assert {s['slug'] for s in included if sources[s['slug']]['division']=='engineering'} | excluded == engineering
    assert not excluded & {s['slug'] for s in included}
    assert excluded=={'agency-engineering-network-engineer','agency-engineering-china-network-engineer','agency-engineering-embedded-firmware-engineer','agency-engineering-iot-fleet-engineer','agency-engineering-electrical-engineer','agency-engineering-orgscript-engineer'}
    assert {s['slug'] for s in included if sources[s['slug']]['division']=='testing'} == {r['slug'] for r in inventory if r['division']=='testing'}
    assets=catalog_assets_by_slug()
    assert len(ROLES)==23 and sum(r['new_agent'] for r in ROLES)==22
    for role in ROLES:
        for source in role['sources']:
            assert source['source_path']==sources[source['slug']]['source_path']
            assert source['source_sha256']==sources[source['slug']]['source_sha256']
        asset=assets[role['target_slug']]
        if role['new_agent']:
            assert not asset.config['systems'] and not asset.config['capabilities']
        assert asset.department==role['department']
        workflow=assets[role['target_slug']+'-software-review']
        assert not workflow.required_connectors
        assert workflow.config['steps'][0]['metadata']['agent_seed']==asset.config['seed_label']
        forged=deepcopy(asset.config);forged['config']['software_guidance']['version']=True
        assert not render_software_role(forged)
