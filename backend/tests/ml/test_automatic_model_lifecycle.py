"""Runtime evidence and consent boundaries for automatic model capabilities."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.ml.active_learning import ActiveLearningCoordinator
from app.ml.neuro_symbolic import NeuroSymbolicReasoningEngine
from app.ml.world_models import WorldModelScaffold
from app.ml.planning_models import AgentPlanningModel
from app.ml.training_consent import consent_is_approved, training_disclosure, save_training_consent


@pytest.mark.asyncio
async def test_uncertainty_sampling_uses_valid_distributions_and_never_creates_labels():
    result = await ActiveLearningCoordinator().predict_structured(candidates=[
        {"id": "confident", "probabilities": {"a": .99, "b": .01}},
        {"id": "uncertain", "probabilities": {"a": .5, "b": .5}},
        {"id": "invalid", "probabilities": {"a": 2, "b": -1}},
        {"id": "nan", "probabilities": {"a": float("nan"), "b": .5}},
    ])
    assert result["eligible_count"] == 2
    assert result["candidates"][0] == {"id": "uncertain", "uncertainty": 1.0}
    assert result["advisory_only"] is True
    assert "labels" not in result


@pytest.mark.asyncio
async def test_constraints_do_not_coerce_types_or_authorize_execution():
    result = await NeuroSymbolicReasoningEngine().predict_structured(
        facts={"amount": 100, "approved": True}, rules=[
            {"id": "review", "field": "amount", "operator": "gte", "value": 100, "effect": "review"},
            {"id": "bad_type", "field": "approved", "operator": "eq", "value": 1},
            {"id": "missing", "field": "missing", "operator": "eq", "value": None},
        ])
    assert result["matches"] == [{"rule_id": "review", "effect": "review"}]
    assert result["advisory_only"] is True


@pytest.mark.asyncio
async def test_world_model_performs_roundtrip_prediction_and_refuses_extrapolation():
    rng = np.random.default_rng(7)
    values = rng.uniform(0, 10, 600)
    model = WorldModelScaffold()
    metrics = await model.train([{"before": float(v)} for v in values], (values*2+1).tolist())
    assert metrics.validation_samples == 120
    assert metrics.mae < metrics.custom_metrics["baseline_mae"]
    loaded = WorldModelScaffold()
    loaded.load(model.save())
    result = await loaded.predict_structured(inputs=[{"before": 5.0}])
    assert result["status"] == "ok"
    assert result["predictions"][0] == pytest.approx(11, abs=.01)
    with pytest.raises(ValueError, match="outside observed"):
        await loaded.predict([{"before": 1000}])
    with pytest.raises(ValueError, match="schema mismatch"):
        await loaded.predict([{"unknown": 5}])


@pytest.mark.asyncio
async def test_world_model_never_activates_from_catalog_or_empty_artifact():
    model = WorldModelScaffold()
    assert (await model.predict_structured(org_id="org"))["status"] == "dormant"
    with pytest.raises(ValueError):
        model.save()
    with pytest.raises(ValueError, match="500"):
        await model.train([{"before": 1.0}], [2])


@pytest.mark.asyncio
async def test_planning_predictor_ranks_measured_candidates_after_reload():
    rows = [{"action": "effective" if i % 2 else "ineffective", "value": float(i % 5)} for i in range(200)]
    labels = [i % 2 for i in range(200)]
    model = AgentPlanningModel()
    metrics = await model.train(rows, labels)
    assert metrics.auc_roc == 1
    loaded = AgentPlanningModel()
    loaded.load(model.save())
    result = await loaded.predict_structured(inputs=[{"action": "ineffective", "value": 2.0}, {"action": "effective", "value": 2.0}])
    assert result["recommendations"][0]["action"] == "effective"
    assert result["advisory_only"] is True


def test_consent_requires_exact_version_and_org_only_scope():
    disclosure = training_disclosure("world_model")
    record = {"state": "approved", "scope_digest": disclosure["scope_digest"], "sharing_scope": "organization_only"}
    assert consent_is_approved({"world_model": record}, "world_model")
    for changes in ({"state": "paused"}, {"state": "revoked"}, {"scope_digest": "old"}, {"sharing_scope": "cross_tenant"}):
        assert not consent_is_approved({"world_model": {**record, **changes}}, "world_model")
    assert not consent_is_approved({}, "world_model")


class ConsentQuery:
    def __init__(self, client):
        self.client, self.filters, self.payload = client, [], None
    def select(self, *_): return self
    def limit(self, *_): return self
    def eq(self, key, value): self.filters.append((key, value)); return self
    def is_(self, key, value): self.filters.append((key, value)); return self
    def update(self, payload): self.payload = payload; return self
    def execute(self):
        assert ("id", "org-a") in self.filters
        if self.payload is None:
            return SimpleNamespace(data=[{"settings": deepcopy(self.client.settings)}])
        assert any(key == "settings" for key, _ in self.filters), "CAS required"
        self.client.writes.append(self.payload)
        return SimpleNamespace(data=[] if self.client.conflict else [{"id": "org-a"}])


class ConsentClient:
    def __init__(self, conflict=False):
        self.settings = {"unrelated_security_setting": True}
        self.writes, self.conflict = [], conflict
    def table(self, name):
        assert name == "organizations"
        return ConsentQuery(self)


def test_consent_records_actor_scope_and_preserves_settings_with_cas():
    client = ConsentClient()
    scope = training_disclosure("world_model")["scope_digest"]
    with patch("app.ml.training_consent.get_supabase_client", return_value=client):
        result = save_training_consent("org-a", "world_model", "admin-id", "approved", scope, MagicMock())
    assert result["actor_id"] == "admin-id"
    assert client.writes[0]["settings"]["unrelated_security_setting"] is True
    assert client.writes[0]["settings"]["model_training_consents"]["world_model"]["history"][0]["scope_digest"] == scope


def test_concurrent_consent_update_cannot_silently_overwrite_revocation():
    with patch("app.ml.training_consent.get_supabase_client", return_value=ConsentClient(conflict=True)):
        with pytest.raises(ValueError, match="concurrently"):
            save_training_consent("org-a", "world_model", "admin", "approved", training_disclosure("world_model")["scope_digest"], MagicMock())


@pytest.mark.asyncio
async def test_automatic_training_without_consent_never_calls_trainer():
    from app.ml.automatic_training import reconcile_automatic_models
    redis = MagicMock()
    redis.lock.return_value.acquire.return_value = True
    with patch("app.ml.automatic_training.get_sync_redis", return_value=redis), \
         patch("app.ml.training_consent.load_training_consents", return_value={}), \
         patch("app.ml.registry.get_model_registry") as registry, \
         patch("app.ml.intelligence_training.train_catalog_model", new_callable=AsyncMock) as train:
        registry.return_value.list_models = AsyncMock(return_value=[])
        result = await reconcile_automatic_models("org", MagicMock())
    assert all(row["status"] == "awaiting_consent" for row in result["models"].values())
    train.assert_not_called()
    redis.lock.return_value.release.assert_called_once()


@pytest.mark.asyncio
async def test_read_error_is_not_consent_and_inputs_cannot_override_tenant():
    from app.ml.model_catalog import infer_catalog_capability
    with patch("app.ml.training_consent.load_training_consents", side_effect=RuntimeError("offline")), \
         patch("app.ml.model_catalog.load_org_trained_catalog_model", new_callable=AsyncMock) as load:
        result = await infer_catalog_capability("org-a", "world_model", {"org_id": "org-b"}, settings=MagicMock())
    assert result["reason"] == "training_permission_inactive"
    load.assert_not_called()
    instance = MagicMock()
    instance.predict_structured = AsyncMock(return_value={"status": "ok"})
    with patch("app.ml.model_catalog.get_model_instance", return_value=instance):
        await infer_catalog_capability("org-a", "active_learning", {"org_id": "org-b", "settings": "bad"}, settings=MagicMock())
    assert instance.predict_structured.call_args.kwargs["org_id"] == "org-a"


@pytest.mark.asyncio
async def test_paired_effect_uses_actual_before_values_and_never_reports_accuracy():
    from app.ml.causal_analysis import CausalImpactAnalyzer
    with patch.object(CausalImpactAnalyzer, "_load_pairs", return_value=[(100.0, 110.0)]*30):
        result = await CausalImpactAnalyzer().predict_structured(org_id="org", settings=MagicMock())
    assert result["estimated_effect"] == 10
    assert result["confidence"] is None
    assert "accuracy" not in result
    assert result["method"] == "paired_observational_difference"


@pytest.mark.asyncio
async def test_revocation_blocks_cached_unified_inference_before_runtime_loading():
    from app.ml.inference import InferenceService
    runtime = InferenceService()
    model = SimpleNamespace(org_id="org", base_model="world_model", deployed_version=1, current_version=2)
    registry = MagicMock()
    registry.get_model = AsyncMock(return_value=model)
    with patch("app.ml.inference.get_model_registry", return_value=registry), \
         patch("app.ml.training_consent.training_is_approved", new_callable=AsyncMock, return_value=False), \
         patch.object(runtime, "_load_runtime_model", new_callable=AsyncMock) as load:
        with pytest.raises(ValueError, match="permission is inactive"):
            await runtime.predict("org", "model", [{"before": 1}])
    load.assert_not_called()


def test_training_permissions_are_admin_only_at_real_role_boundary():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.dependencies import get_current_user, get_org_context
    from app.config import Settings, get_settings
    from app.routers.ml_admin import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "member"}
    app.dependency_overrides[get_org_context] = lambda: "org-a"
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="dev")
    database = MagicMock()
    query = database.table.return_value
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value.data = [{"role": "member"}]
    with patch("app.auth.dependencies._get_cached_service_client", return_value=database), \
         patch("app.auth.dependencies.is_platform_admin", return_value=False), \
         patch("app.ml.training_consent.save_training_consent") as save:
        client = TestClient(app)
        assert client.get("/api/admin/ml/training-permissions").status_code == 403
        assert client.post("/api/admin/ml/models/intent_classifier/verify-inference", json={
            "inputs": {"inputs": ["real query"]}
        }).status_code == 403
        assert client.post("/api/admin/ml/training-permissions/world_model", json={
            "state": "approved", "scope_digest": "a"*64}).status_code == 403
    save.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_roundtrip_and_unverified_quality_does_not_promote():
    from app.ml.self_supervised import SelfSupervisedEmbeddingLearner
    from app.ml.intelligence_training import champion_challenger_decision
    texts = [f"department account topic{i%10} customer{i%7} document{i}" for i in range(120)]
    model = SelfSupervisedEmbeddingLearner()
    metrics = await model.train(texts)
    allowed, reason, _ = champion_challenger_decision(metrics, None, has_champion=False)
    assert allowed is False
    assert reason == "not_deployed_no_held_out_metric"
    loaded = SelfSupervisedEmbeddingLearner()
    loaded.load(model.save())
    embeddings, _ = await loaded.predict(["department topic1 customer1"])
    assert np.linalg.norm(embeddings[0]) == pytest.approx(1)


@pytest.mark.asyncio
async def test_legacy_registry_base_alias_cannot_bypass_paused_model():
    from app.ml.inference import InferenceService
    registry = MagicMock()
    registry.get_model = AsyncMock(return_value=SimpleNamespace(
        org_id="org", name="catalog-workflow-anomaly", base_model="anomaly_detector", deployed_version=1, current_version=1))
    with patch("app.ml.inference.get_model_registry", return_value=registry), \
         patch("app.ml.training_consent.training_is_approved", new_callable=AsyncMock, return_value=False) as consent:
        with pytest.raises(ValueError, match="permission is inactive"):
            await InferenceService().predict("org", "model", [{"value": 1}])
    assert consent.call_args.args[1] == "workflow_anomaly_detector"
