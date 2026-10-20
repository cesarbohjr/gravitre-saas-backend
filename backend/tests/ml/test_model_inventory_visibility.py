"""Exposure is capability metadata; TRAINED is not runtime proof."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.ml.model_catalog import build_ml_catalog_dashboard, model_inventory_definition
from app.routers.ml_admin import train_ml_model


@pytest.mark.asyncio
async def test_member_catalog_filters_advanced_but_admin_inventory_is_complete():
    with patch('app.ml.model_catalog.get_org_model_status', AsyncMock(return_value={})), patch(
        'app.services.strategy_performance_ledger.get_strategy_performance_ledger'
    ) as ledger, patch('app.services.adaptive_learning_service.get_adaptive_learning_service') as adaptive:
        ledger.return_value.load_model_outcome_scores = AsyncMock(return_value={})
        adaptive.return_value.is_enabled_for_org = AsyncMock(return_value=False)
        member = await build_ml_catalog_dashboard('org-a', settings=MagicMock())
        admin = await build_ml_catalog_dashboard('org-a', settings=MagicMock(), include_advanced=True)
    assert len(member['inventory']) == 14
    assert len(admin['inventory']) == 26
    assert 'world_model' not in member['catalog']
    assert 'world_model' not in member['inventory']
    assert admin['inventory']['world_model']['visibility'] == 'admin_technical'
    assert not admin['inventory']['world_model']['manual_training_supported']
    assert all(row['visibility'] == 'operational' for row in admin['learningCapabilities'])
    assert member['inventory']['intent_classifier']['artifact_readiness'] == 'not_verified'
    assert member['inventory']['intent_classifier']['inference_health'] == 'not_verified'
    assert member['inventory']['intent_classifier']['verified_outcomes_count'] is None
    assert member['learningActivity']['enabled'] is False


def test_dispatch_placeholder_is_not_manual_training_support():
    assert model_inventory_definition('intent_classifier')['manual_training_supported'] is True
    for name in ['sla_breach_predictor', 'deal_loss_scorer', 'federated_learning']:
        assert model_inventory_definition(name)['manual_training_supported'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('name', ['world_model', 'federated_learning', 'sla_breach_predictor', 'unknown'])
async def test_unsupported_training_cannot_be_queued_in_temporal(name, monkeypatch):
    monkeypatch.setenv('TEMPORAL_HOST', 'temporal.example')
    with patch('app.routers.ml_admin.start_ml_model_training_workflow', AsyncMock()) as queue:
        with pytest.raises(HTTPException) as error:
            await train_ml_model(name, 'org-a', ({}, 'org-a', 'admin'), MagicMock())
        assert error.value.status_code == 400
        queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_loaded_artifact_is_not_verified_inference_or_outcome():
    with patch('app.ml.model_catalog.get_org_model_status', AsyncMock(return_value={
        'artifact_loaded': True, 'runtime_status': 'trained', 'data_counts': {'rows': 100},
    })), patch('app.services.strategy_performance_ledger.get_strategy_performance_ledger') as ledger, patch(
        'app.services.adaptive_learning_service.get_adaptive_learning_service'
    ) as adaptive:
        ledger.return_value.load_model_outcome_scores = AsyncMock(return_value={'intent_classifier': 0.9})
        adaptive.return_value.is_enabled_for_org = AsyncMock(return_value=True)
        result = await build_ml_catalog_dashboard('org-b', settings=MagicMock())
    row = result['inventory']['intent_classifier']
    assert row['artifact_readiness'] == 'loaded'
    assert row['inference_health'] == 'not_verified'
    assert row['verified_outcomes_count'] is None
    assert row['data_eligibility']['status'] == 'requires_training_validation'
    assert result['learningActivity']['activity_status'] == 'not_verified'


def test_technical_inventory_and_training_enforce_actual_member_role():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.dependencies import get_current_user, get_org_context
    from app.config import Settings, get_settings
    from app.routers.ml_admin import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {'user_id': 'member-a'}
    app.dependency_overrides[get_org_context] = lambda: 'org-a'
    app.dependency_overrides[get_settings] = lambda: Settings(app_env='dev')
    database = MagicMock()
    query = database.table.return_value
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value.data = [{'role': 'member'}]
    with patch('app.auth.dependencies._get_cached_service_client', return_value=database), patch(
        'app.auth.dependencies.is_platform_admin', return_value=False,
    ), patch('app.routers.ml_admin.build_ml_catalog_dashboard', AsyncMock()) as build, patch(
        'app.routers.ml_admin.start_ml_model_training_workflow', AsyncMock(),
    ) as train:
        client = TestClient(app)
        assert client.get('/api/admin/ml/models').status_code == 403
        assert client.post('/api/admin/ml/models/intent_classifier/train').status_code == 403
        build.assert_not_awaited()
        train.assert_not_awaited()
