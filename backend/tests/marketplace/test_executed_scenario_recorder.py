from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from app.marketplace.marketplace3.scenario_runner import record_executed_scenarios
from app.marketplace.marketplace3.certification_store import outcome_pack_config_digest
from app.marketplace.marketplace3.production_evidence import collect_production_evidence
from app.marketplace.marketplace3.msp_service_desk import build_msp_service_desk_outcome_pack_config
from app.marketplace.schemas import OutcomePackAssetConfig

class Query:
    def __init__(self, db, table): self.db, self.table, self.filters, self.inserted = db, table, [], None
    def select(self, *a): return self
    def eq(self, k, v): self.filters.append(lambda r: r.get(k) == v); return self
    def in_(self, k, v): self.filters.append(lambda r: r.get(k) in v); return self
    def contains(self, k, v): self.filters.append(lambda r: all(r.get(k, {}).get(a) == b for a,b in v.items())); return self
    def gte(self, *a): return self
    def limit(self, *a): return self
    def order(self, *a, **kw): return self
    def insert(self, rows): self.inserted = deepcopy(rows); return self
    def execute(self):
        if self.inserted is not None:
            self.db.rows.setdefault(self.table, []).extend(self.inserted)
            return SimpleNamespace(data=self.inserted)
        return SimpleNamespace(data=[r for r in self.db.rows.get(self.table, []) if all(f(r) for f in self.filters)])
class DB:
    def __init__(self, rows): self.rows = rows
    def table(self, name): return Query(self, name)


def world():
    config = OutcomePackAssetConfig.model_validate(build_msp_service_desk_outcome_pack_config())
    raw = config.model_dump(mode="json")
    digest = outcome_pack_config_digest(config)
    stamp = datetime.now(timezone.utc).isoformat()
    rows = {k: [] for k in ("workflow_defs", "workflow_runs", "workflow_steps", "play_installations", "intelligence_outcome_events", "marketplace_outcome_pack_checks")}
    from app.marketplace.service import _resolve_workflow_steps, marketplace_entity_id
    agents = {a.seed_label: marketplace_entity_id("org", "pack", a.seed_label) for a in config.agents}
    for i, play in enumerate(config.plays):
        wid, rid = f"w{i}", f"r{i}"
        steps = _resolve_workflow_steps(deepcopy(play.workflow_steps), agent_ids=agents, connector_ids={p.provider: "connector" for p in config.runtime_profiles})
        for step in steps:
            if step.get("type") == "agent": step.setdefault("metadata", {}).setdefault("briefing_from_steps", True)
        from app.marketplace.pack_prewiring import definition_with_sequential_graph
        definition = definition_with_sequential_graph(steps)
        rows['workflow_defs'].append({"id": wid, "org_id": "org", "definition": definition, "config": {"marketplaceAssetId": "pack", "marketplaceConfigDigest": digest, "marketplacePlayKey": play.key}})
        rows['workflow_runs'].append({"id": rid, "org_id": "org", "workflow_id": wid, "definition_snapshot": definition, "status": "completed", "environment": "production", "run_type": "execute", "created_at": stamp})
        rows['play_installations'].append({"id": f"p{i}", "org_id": "org", "play_key": play.key, "environment_name": "production", "status": "ready", "configuration": {"marketplaceAssetId": "pack", "marketplaceConfigDigest": digest}})
        for step in play.workflow_steps:
            if step['type'] != 'invoke_tool': continue
            action = step['config']['action']
            rows['workflow_steps'].append({"id": rid+step['id'], "run_id": rid, "org_id": "org", "step_id": step['id'], "step_type": "invoke_tool", "status": "completed", "output_snapshot": {"invoke_action": action, "verification": {"verified": True, "method": "field_assert", "action": action, "resource_id": "ticket-1"}}})
        for key in play.kpi_keys:
            rows['intelligence_outcome_events'].append({"org_id": "org", "workflow_run_id": rid, "outcome_event": "play_business_result", "measurement_status": "recorded", "before_value": 1, "after_value": 2, "measured_at": stamp, "metadata": {"contract": "play_business_result/v1", "play_key": play.key, "metric_key": key, "verified": True, "verification_state": "VERIFIED SUCCESS", "verification_method": "independent_readback", "source_records": [{"id": "ticket-1"}], "evidence_ids": ["source-proof"]}})
    for metric in config.outcome_contract.kpis:
        if any(metric.key in play.kpi_keys for play in config.plays):
            continue
        recipe = next(recipe for recipe in config.verification_recipes if any(c.metric_key == metric.key for c in recipe.contributions))
        i, play = next((i, p) for i, p in enumerate(config.plays) if {step.get("config", {}).get("action") for step in p.workflow_steps}.intersection(recipe.match_actions))
        reference = next(row for row in rows['intelligence_outcome_events'] if row['workflow_run_id'] == f"r{i}")
        row = deepcopy(reference)
        row['metadata'].update({"metric_key": metric.key, "recipe_key": recipe.key})
        rows['intelligence_outcome_events'].append(row)
    bad = {**rows['workflow_runs'][0], "id": "denied", "status": "failed"}
    rows['workflow_runs'].append(bad)
    rows['workflow_steps'].append({"run_id": "denied", "org_id": "org", "status": "failed", "step_type": "invoke_tool", "error_code": "APPROVAL_DENIED", "output_snapshot": {}})
    return DB(rows), config, {"id": "pack", "org_id": "org", "config": raw}

@pytest.mark.asyncio
async def test_real_install_run_step_and_outcome_chain_records_six_independent_checks():
    db, config, asset = world()
    with patch('app.marketplace.marketplace3.scenario_runner.probe_outcome_pack_permissions', new_callable=AsyncMock, return_value={"passed": True, "ownRowId": "own", "foreignRowId": "foreign"}):
        result = await record_executed_scenarios(db, None, org_id='org', asset=asset, config=config, access_token='test-token')
    assert all(result['checks'].values())
    assert len(db.rows['marketplace_outcome_pack_checks']) == 6
    assert all('test-token' not in row['evidence_ref'] for row in db.rows['marketplace_outcome_pack_checks'])
    proof = collect_production_evidence(db, org_id='org', asset_id='pack', config_digest=outcome_pack_config_digest(config), config=config)
    assert proof.covers({a for p in config.runtime_profiles for a in p.actions})
    assert proof.play_keys == {p.key for p in config.plays}

@pytest.mark.asyncio
async def test_failed_permission_probe_and_changed_install_cannot_become_certification():
    db, config, asset = world()
    db.rows['play_installations'][0]['configuration']['marketplaceConfigDigest'] = 'old'
    with patch('app.marketplace.marketplace3.scenario_runner.probe_outcome_pack_permissions', new_callable=AsyncMock, return_value={"passed": False, "reason": "foreign_visible"}):
        result = await record_executed_scenarios(db, None, org_id='org', asset=asset, config=config, access_token='test-token')
    assert result['checks']['permissions_passed'] is False
    assert result['checks']['fresh_install_passed'] is False

@pytest.mark.asyncio
async def test_failure_after_a_write_is_not_a_safe_negative_scenario():
    db, config, asset = world()
    db.rows['workflow_steps'].append({"run_id": "denied", "org_id": "org", "status": "completed", "step_type": "email_send"})
    with patch('app.marketplace.marketplace3.scenario_runner.probe_outcome_pack_permissions', new_callable=AsyncMock, return_value={"passed": True}):
        result = await record_executed_scenarios(db, None, org_id='org', asset=asset, config=config, access_token='test-token')
    assert result['checks']['failure_path_passed'] is False


@pytest.mark.asyncio
async def test_edited_workflow_cannot_reuse_the_old_pack_digest_for_certification():
    db, config, asset = world()
    db.rows['workflow_defs'][0]['definition']['steps'].append({"id":"extra", "name":"Unexpected", "type":"noop"})
    with patch('app.marketplace.marketplace3.scenario_runner.probe_outcome_pack_permissions', new_callable=AsyncMock, return_value={"passed": True}):
        result = await record_executed_scenarios(db, None, org_id='org', asset=asset, config=config, access_token='test-token')
    assert result['checks']['golden_path_passed'] is False
    assert result['checks']['fresh_install_passed'] is False


@pytest.mark.asyncio
async def test_graph_rewiring_cannot_reuse_unchanged_steps_as_certification():
    db, config, asset = world()
    db.rows['workflow_defs'][0]['definition']['graph']['edges'] = []
    with patch('app.marketplace.marketplace3.scenario_runner.probe_outcome_pack_permissions', new_callable=AsyncMock, return_value={"passed": True}):
        result = await record_executed_scenarios(db, None, org_id='org', asset=asset, config=config, access_token='test-token')
    assert result['checks']['golden_path_passed'] is False
