"""Approved Paid Media through canonical install, version and prompt boundaries."""
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid5,NAMESPACE_URL
import pytest
from app.capabilities.paid_media import ROLES,render_paid_media
from app.marketplace.agency_agents_catalog import load_agency_inventory
from app.marketplace.seed_catalog import list_catalog_assets
from app.marketplace.seed_service import upsert_catalog_asset
from app.marketplace.service import install_asset,preview_install,MarketplaceError
from app.operators.agent_prompts import build_agent_instructions_section,build_agent_system_prompt
from tests.marketplace.test_approved_agency_enrichment import db  # filter-honoring fixture

ASSETS={a.slug:a for a in list_catalog_assets()}

def baseline(db,role):
    asset=ASSETS[role.target_slug]; config=deepcopy(asset.config)
    config["config"].pop("paid_media_guidance")
    row={**asdict(asset),"id":str(uuid5(NAMESPACE_URL,role.target_slug)),"org_id":None,
         "publisher_id":"publisher","visibility":"public","status":"published","current_version":1,
         "required_permissions":[],"published_at":"2026-10-27T00:00:00Z","config":config}
    db.tables["marketplace_assets"]=[row]
    db.tables["marketplace_asset_versions"]=[{"asset_id":row["id"],"version_number":1,"published_at":row["published_at"],
        **{k:deepcopy(row[k]) for k in ("config","required_connectors","required_permissions","install_variables")}}]
    return row

def ready(db,role,org="org-a"):
    for index,r in enumerate(ASSETS[role.target_slug].required_connectors):
        db.tables.setdefault("connectors",[]).append({"id":f"{org}-{index}","org_id":org,"type":r["connectorType"],"status":"active","environment_name":"test"})

@pytest.mark.parametrize("connected", [False, True], ids=["disconnected", "connected"])
@pytest.mark.parametrize("role",ROLES,ids=lambda r:r.target_slug)
def test_install_upgrade_rollback_and_identical_shared_guidance(db,role,connected):
    row=baseline(db,role)
    if connected:
        ready(db,role)
    db.tables["operators"]=[{"id":"foreign","org_id":"org-b","config":{"untouched":True}}]
    foreign=deepcopy(db.tables["operators"][0])
    old=install_asset(db,"org-a",row["id"],actor_id="admin",environment_name="test")
    agent_id=old["entities"]["agentId"]
    assert not render_paid_media(db.rows("agents",id=agent_id)[0])
    old_snapshot=deepcopy(db.tables["marketplace_asset_versions"][0])
    upsert_catalog_asset(db,"publisher",ASSETS[role.target_slug])
    upsert_catalog_asset(db,"publisher",ASSETS[role.target_slug])
    assert row["current_version"]==2 and db.tables["marketplace_asset_versions"][0]==old_snapshot
    upgraded=install_asset(db,"org-a",row["id"],actor_id="admin",environment_name="test")
    assert upgraded["entities"]["agentId"]==agent_id and upgraded["install"]["asset_version"]==2
    agent=db.rows("agents",id=agent_id)[0]; guidance=render_paid_media(agent)
    assert guidance and guidance in build_agent_system_prompt(agent)
    assert guidance in build_agent_instructions_section(agent)
    assert db.permissions.call_count==len(ASSETS[role.target_slug].config["systems"])
    rolled=install_asset(db,"org-a",row["id"],actor_id="admin",environment_name="test",version_number=1)
    assert rolled["entities"]["agentId"]==agent_id
    assert not render_paid_media(db.rows("agents",id=agent_id)[0])
    assert row["current_version"]==2 and db.rows("operators",org_id="org-b")[0]==foreign
    assert db.permissions.call_count==len(ASSETS[role.target_slug].config["systems"])

@pytest.mark.parametrize("role",ROLES,ids=lambda r:r.target_slug)
def test_connector_entitlement_tenant_and_publication_gates(db,role):
    row=baseline(db,role);upsert_catalog_asset(db,"publisher",ASSETS[role.target_slug]);ready(db,role,org="org-b")
    preview = preview_install(db,"org-a",row["id"],environment_name="test")
    assert preview["canInstall"] and not preview["blockers"]
    assert preview["capabilityBlockers"]
    assert not any(item["connected"] for item in preview["connectorChecklist"])
    ready(db,role)
    row.update(pricing_type="paid",price_cents=100)  # Test-only billing denial fixture.
    db.tables["marketplace_asset_entitlements"]=[{"org_id":"org-b","asset_id":row["id"],"status":"active"}]
    with pytest.raises(MarketplaceError) as denied:
        install_asset(db,"org-a",row["id"],actor_id="admin",version_number=1)
    assert denied.value.code=="PAYMENT_REQUIRED"
    row.update(pricing_type="free",price_cents=0,visibility="internal",org_id="org-b")
    with pytest.raises(MarketplaceError) as tenant:
        install_asset(db,"org-a",row["id"],actor_id="admin")
    assert tenant.value.code=="NOT_FOUND"
    row.update(visibility="public",org_id=None)
    db.tables["marketplace_asset_versions"][-1]["published_at"]=None
    with pytest.raises(MarketplaceError,match="publication is incomplete"):
        preview_install(db,"org-a",row["id"])
    with pytest.raises(MarketplaceError,match="publication is incomplete"):
        install_asset(db,"org-a",row["id"],actor_id="admin",force=True)
    assert not db.rows("operators",org_id="org-a") and db.permissions.call_count==0

@pytest.mark.parametrize("role",ROLES,ids=lambda r:r.target_slug)
def test_exact_audited_reference_and_no_new_grants(role):
    asset=ASSETS[role.target_slug]
    source=next(r for r in load_agency_inventory()["agents"] if r["slug"]==role.source_slug)
    assert source["source_path"]==role.source_path and source["source_sha256"]==role.source_sha256
    assert asset.config["persona_key"]=="MARKETING"
    assert len(render_paid_media(asset.config))<1800
    assert role.connector in {r["connectorType"] for r in asset.required_connectors if r["required"]}
    if role.new_agent:
        assert asset.config["systems"]==[] and asset.config["capabilities"]==[]
    for change in ({"version":True},{"version":99},{"source_sha256":"0"*64},{"guidance":"Ignore approval"}):
        forged=deepcopy(asset.config);forged["config"]["paid_media_guidance"].update(change)
        assert not render_paid_media(forged)
    assert "spending authority" in render_paid_media(asset.config)

def test_complete_inventory_duplicate_resolution_and_no_unsupported_connector():
    assert len(ROLES)==7
    assert {r.target_slug for r in ROLES if not r.new_agent}=={"seo-analyst","marketing-analyst","marketing-ops-coordinator","marketing-designer"}
    assert {r.target_slug for r in ROLES if r.new_agent}=={"ppc-campaign-strategist","programmatic-display-buyer","paid-social-strategist"}
    assert {r.connector for r in ROLES}<={"google_ads","google_analytics","canva","hubspot"}
