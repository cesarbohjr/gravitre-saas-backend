from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.marketplace.marketplace3.workspace import contract_view, department_workspace
from app.marketplace.marketplace3.portfolio_readiness import _outcome_assets
from app.marketplace.schemas import OutcomePackAssetConfig
from app.marketplace.service import MarketplaceError

ORG = '00000000-0000-0000-0000-000000000001'
RUN = '00000000-0000-0000-0000-000000000002'
EVENT = '00000000-0000-0000-0000-000000000003'

class Table:
    def __init__(self, rows): self.rows = deepcopy(rows)
    def select(self, *_): return self
    def eq(self, key, value): self.rows = [r for r in self.rows if r.get(key) == value]; return self
    def in_(self, key, values): self.rows = [r for r in self.rows if r.get(key) in values]; return self
    def limit(self, count): self.rows = self.rows[:count]; return self
    def order(self, *_args, **_kwargs): return self
    def execute(self): return SimpleNamespace(data=self.rows)

class Client:
    def __init__(self):
        config = _outcome_assets()[2].config
        play = config['plays'][0]
        self.asset = {'id': 'pack', 'slug': 'revenue-operations-3', 'title': 'Revenue Operations 3.0', 'asset_type': 'outcome_pack', 'config': {}}
        self.tables = {
            'marketplace_installs': [{'id': 'install', 'org_id': ORG, 'asset_id': 'pack', 'status': 'active', 'asset_version': 1, 'metadata': {'workflowIds': ['flow-1']}}],
            'marketplace_asset_versions': [{'asset_id': 'pack', 'version_number': 1, 'config': config}],
            'workflow_runs': [{'id': RUN, 'org_id': ORG, 'workflow_id': 'flow-1', 'status': 'completed', 'run_type': 'execute', 'environment': 'production', 'completed_at': '2026-10-02', 'created_at': '2026-10-02'}],
            'intelligence_outcome_events': [{'id': EVENT, 'org_id': ORG, 'workflow_run_id': RUN, 'outcome_event': 'play_business_result', 'measurement_status': 'recorded', 'before_value': 15, 'after_value': 5, 'measured_at': '2026-10-02', 'metadata': {'contract': 'play_business_result/v1', 'play_key': play['key'], 'metric_key': play['kpi_keys'][0], 'outcome_type': play['outcome_events'][0], 'verification_state': 'VERIFIED SUCCESS', 'verified': True, 'verification_method': 'independent_source_read', 'source_records': [{'system': 'hubspot', 'record_type': 'contact', 'record_id': '42'}]}}],
        }
    def table(self, name): return Table(self.tables[name])

@pytest.fixture
def client(monkeypatch):
    client = Client()
    monkeypatch.setattr('app.marketplace.marketplace3.workspace.fetch_marketplace_asset', lambda *_: client.asset)
    return client

@pytest.mark.parametrize('asset', _outcome_assets(), ids=lambda a: a.slug)
def test_all_eight_department_contracts_cover_original_dashboard_choices(asset):
    config = OutcomePackAssetConfig.model_validate(asset.config)
    view = contract_view(config)
    assert view['dashboard'] == asset.config['dashboard']
    assert len(view['plays']) == len(config.plays)
    assert view['dataset']['entities']
    assert view['outcome']['kpis']


def test_workspace_pins_installed_version_and_resolves_live_measurement(client):
    result = department_workspace(client, ORG, 'revenue-operations-3')
    assert len(result['measurements']) == 1
    assert result['measurements'][0]['resultValue'] == 5
    assert result['contract']['plays'][0]['name'] == 'Inbound Lead Qualifier'
    assert result['install']['version'] == 1
    assert client.asset['config'] == {}  # Current mutable config is not the installed contract.


def test_other_tenant_cannot_read_install_or_evidence(client):
    with pytest.raises(MarketplaceError) as error:
        department_workspace(client, 'other-org', 'revenue-operations-3')
    assert error.value.code == 'NOT_FOUND'

@pytest.mark.parametrize('field,value', [('run_type', 'dry_run'), ('environment', 'staging'), ('status', 'failed'), ('workflow_id', 'unrelated-workflow'), ('org_id', 'other-org')])
def test_nonproduction_or_unrelated_runs_cannot_populate_charts(client, field, value):
    client.tables['workflow_runs'][0][field] = value
    assert department_workspace(client, ORG, 'revenue-operations-3')['measurements'] == []


def test_unverified_measurement_cannot_populate_charts(client):
    client.tables['intelligence_outcome_events'][0]['metadata']['verified'] = False
    assert department_workspace(client, ORG, 'revenue-operations-3')['measurements'] == []


def test_missing_installed_version_does_not_fall_back_to_current_config(client):
    client.tables['marketplace_asset_versions'] = []
    with pytest.raises(MarketplaceError) as error:
        department_workspace(client, ORG, 'revenue-operations-3')
    assert error.value.code == 'WORKSPACE_VERSION_MISSING'
