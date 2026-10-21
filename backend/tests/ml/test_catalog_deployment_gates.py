"""Direct registry callers cannot bypass catalog promotion/permission gates."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ml.registry import ModelRegistry


@pytest.fixture
def registry(monkeypatch):
    registry = ModelRegistry()
    registry._settings = SimpleNamespace()
    client = MagicMock()
    query = client.table.return_value
    query.select.return_value = query
    query.eq.return_value = query
    query.update.return_value = query
    query.execute.return_value = SimpleNamespace(data=[{
        'id': 'model', 'org_id': 'org', 'name': 'catalog-graph-neural-network',
        'base_model': 'graph_neural_network', 'current_version': 2, 'deployed_version': 1,
        'artifact_url': 'https://artifact.example/graph-v2.npz',
    }])
    monkeypatch.setattr(registry, '_get_client', lambda: client)
    registry.get_version_metrics = AsyncMock(side_effect=[
        {'auc_roc': .8, 'validation_samples': 30},
        {'auc_roc': .9, 'validation_samples': 30},
    ])
    return registry, query


@pytest.mark.asyncio
async def test_manual_catalog_deploy_denied_without_fresh_consent(registry, monkeypatch):
    instance, query = registry
    approval = AsyncMock(return_value=False)
    monkeypatch.setattr('app.ml.training_consent.training_is_approved', approval)
    with pytest.raises(ValueError, match='training_consent_required'):
        await instance.deploy_version('model', 2)
    approval.assert_awaited_once_with('org', 'graph_neural_network', instance.settings)
    instance.get_version_metrics.assert_not_awaited()
    query.update.assert_not_called()


@pytest.mark.asyncio
async def test_manual_catalog_deploy_cannot_replace_better_champion(registry, monkeypatch):
    instance, query = registry
    monkeypatch.setattr('app.ml.training_consent.training_is_approved', AsyncMock(return_value=True))
    with pytest.raises(ValueError, match='challenger_worse_than_champion'):
        await instance.deploy_version('model', 2)
    query.update.assert_not_called()


@pytest.mark.asyncio
async def test_manual_catalog_deploy_allows_validated_improvement(registry, monkeypatch):
    instance, query = registry
    monkeypatch.setattr('app.ml.training_consent.training_is_approved', AsyncMock(return_value=True))
    instance.get_version_metrics.side_effect = [
        {'auc_roc': .95, 'validation_samples': 30},
        {'auc_roc': .9, 'validation_samples': 30},
    ]
    assert await instance.deploy_version('model', 2)
    assert query.update.call_args.args[0]['deployed_version'] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('version', [0, -1, True])
async def test_invalid_version_never_updates_pointer(registry, version):
    instance, query = registry
    with pytest.raises(ValueError, match='positive artifact version'):
        await instance.deploy_version('model', version)
    query.update.assert_not_called()


@pytest.mark.asyncio
async def test_catalog_pointer_requires_artifact_reference(registry, monkeypatch):
    instance, query = registry
    monkeypatch.setattr('app.ml.training_consent.training_is_approved', AsyncMock(return_value=True))
    instance.get_version_metrics.side_effect = [
        {'auc_roc': .95, 'validation_samples': 30},
        {'auc_roc': .9, 'validation_samples': 30},
    ]
    del query.execute.return_value.data[0]['artifact_url']
    with pytest.raises(ValueError, match='catalog_artifact_required'):
        await instance.deploy_version('model', 2)
    query.update.assert_not_called()
