"""Execution/provenance gates and real advanced learning, without network."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.ml.graph_models import GraphNeuralNetworkScorer
from app.ml.inference_validation import validate_inference_result
from app.ml.model_catalog import infer_catalog_capability


def graph_examples(n=120):
    rng = np.random.default_rng(17)
    rows, labels = [], []
    for i in range(n):
        positive = i % 2
        features = rng.normal(0, .05, (4, 2))
        features[2, 0] = 2 if positive else -2
        rows.append({"node_features": features.tolist(), "edges": [[0, 2], [1, 3]],
                     "source": 0, "target": 1, "graph_id": f"snapshot-{i}",
                     "observed_at": (datetime(2025, 1, 1, tzinfo=UTC)+timedelta(days=i)).isoformat()})
        labels.append(positive)
    return rows, labels


@pytest.mark.asyncio
async def test_graph_model_learns_neighbor_signal_and_artifact_roundtrip():
    rows, labels = graph_examples()
    model = GraphNeuralNetworkScorer()
    metrics = await model.train(rows, labels)
    assert metrics.auc_roc > .95
    assert metrics.training_samples == 96
    assert metrics.validation_samples == 24
    restored = GraphNeuralNetworkScorer()
    restored.load(model.save())
    original = await model.predict(rows[-10:])
    actual = await restored.predict(rows[-10:])
    assert actual == original
    assert actual[0][0] < .3 and actual[0][1] > .7
    changed = {**rows[-1], "edges": []}
    changed_prediction, _ = await restored.predict([changed])
    assert abs(changed_prediction[0]-actual[0][-1]) > .15


@pytest.mark.asyncio
async def test_graph_model_rejects_leakage_labels_and_untrained_artifacts():
    rows, labels = graph_examples()
    model = GraphNeuralNetworkScorer()
    with pytest.raises(ValueError, match="Untrained"):
        model.save()
    assert (await model.predict_structured())["status"] == "dormant"
    with pytest.raises(ValueError, match="Independent measured"):
        await model.train(rows, None)
    rows[-1]["graph_id"] = rows[0]["graph_id"]
    with pytest.raises(ValueError, match="disjoint"):
        await model.train(rows, labels)
    rows[-1]["edges"].append([0, 1])
    with pytest.raises(ValueError, match="withheld"):
        await model.train(rows, labels)


@pytest.mark.parametrize("result", [
    {"status": "ok", "predictions": []},
    {"status": "ok", "predictions": [float("nan")]},
    {"status": "ok", "predictions": [{"status": "not_trained", "risk_score": 0}]},
    {"status": "ok", "predictions": [1], "probabilities": []},
])
def test_invalid_results_cannot_verify_inference(result):
    with pytest.raises(ValueError):
        validate_inference_result(result)


@pytest.mark.asyncio
async def test_inference_uses_authenticated_org_and_rejects_nonfinite_output():
    instance = SimpleNamespace(registry_ref={"model_id": "a", "version": 1}, predict=AsyncMock(return_value=([.7], None)))
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=True)), patch(
        "app.ml.model_catalog.load_org_trained_catalog_model", AsyncMock(return_value=instance)
    ):
        result = await infer_catalog_capability("org-a", "retrieval_memory_learner", {
            "org_id": "org-b", "inputs": [{"org_id": "org-b", "feature": 1}]}, settings=MagicMock())
        assert result["status"] == "ok"
        assert instance.predict.call_args.kwargs["org_id"] == "org-a"
        instance.predict.return_value = ([float("inf")], None)
        result = await infer_catalog_capability("org-a", "workflow_duration_forecaster", {"inputs": [{"step_count": 1}]}, settings=MagicMock())
        assert result["status"] == "dormant" and result["used_fallback"]


@pytest.mark.asyncio
async def test_rag_pause_blocks_registry_reads():
    from app.ml.learning_to_rank import get_weight_for_org
    from app.ml.source_reliability import RELIABILITY_WEIGHT
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=False)), patch(
        "app.ml.learning_to_rank.get_model_registry"
    ) as registry:
        assert await get_weight_for_org("org-a", MagicMock(), MagicMock()) == RELIABILITY_WEIGHT
        registry.assert_not_called()


@pytest.mark.asyncio
async def test_domain_workflows_use_real_scoped_features_and_shared_inference():
    from app.services.predictive_operations_engine import PredictiveOperationsEngine
    engine = PredictiveOperationsEngine(MagicMock())
    rows = [{"run_id": "run-a", "duration_ms": 1234, "step_count": 2,
             "graph_features_from_snapshot": True, "is_approximated": False},
            {"run_id": "approximated", "is_approximated": True}]
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=True)), patch(
        "app.ml.feature_extraction.collect_workflow_run_features", return_value=rows
    ) as collect, patch("app.ml.model_catalog.infer_catalog_capability", AsyncMock(return_value={"status": "ok", "predictions": [False]})) as infer:
        result = await engine._predict_workflow_runs("org-a", "workflow_anomaly_detector")
        assert result["run_ids"] == ["run-a"]
        assert collect.call_args.args[1] == "org-a"
        assert infer.call_args.args[2]["inputs"] == [{"duration_ms": 1234, "step_count": 2, "error_count": 0, "retry_count": 0}]


@pytest.mark.asyncio
async def test_bound_trainer_denies_before_read_when_permission_inactive():
    from app.ml.advanced_training import train_graph_neural_network
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=False)), patch(
        "app.ml.bound_training_data.collect_bound_records"
    ) as collect:
        assert (await train_graph_neural_network("org-a", settings=MagicMock()))["reason"] == "training_permission_inactive"
        collect.assert_not_called()


@pytest.mark.asyncio
async def test_meta_learning_adapts_heldout_tasks_without_cross_org_data():
    from app.ml.meta_learning import MetaLearningAdaptor
    episodes = []
    for task in range(30):
        def example(i):
            feature = (-1 if i % 2 == 0 else 1) * (.4 + (i % 3)*.2)
            return {"id": f"task-{task}-row-{i}", "features": [feature, .1 * (task % 3)], "label": int(feature > 0)}
        episodes.append({"task_id": f"task-{task}", "support": [example(i) for i in range(4)],
                         "query": [example(i) for i in range(4, 10)]})
    model = MetaLearningAdaptor()
    metrics = await model.train(episodes)
    assert metrics.auc_roc == 1
    assert metrics.custom_metrics["cross_org_training"] is False
    assert metrics.custom_metrics["query_log_loss"] < metrics.custom_metrics["support_only_log_loss"]
    restored = MetaLearningAdaptor()
    restored.load(model.save())
    result = await restored.predict_structured(inputs=[{"support": episodes[-1]["support"], "query_features": [[-1, 0], [1, 0]]}])
    assert result["predictions"][0][0] < .2 and result["predictions"][0][1] > .8
    episodes[-1]["support"][0]["id"] = episodes[0]["support"][0]["id"]
    with pytest.raises(ValueError, match="disjoint"):
        await MetaLearningAdaptor().train(episodes)


def test_workflow_collector_preserves_measured_labels_and_missing_duration():
    from app.ml.feature_extraction import collect_workflow_run_features, features_to_success_train, features_to_forecaster_train
    runs = [{"id": "a", "status": "completed", "duration_ms": 50},
            {"id": "b", "status": "failed", "duration_ms": 75},
            {"id": "c", "status": "running", "duration_ms": None}]
    with patch("app.ml.feature_extraction._fetch_recent_runs", return_value=runs), patch(
        "app.ml.feature_extraction._fetch_steps_for_runs", return_value={}
    ):
        rows = collect_workflow_run_features(MagicMock(), "org-a", client=MagicMock())
    assert rows[-1]["duration_ms"] is None
    assert features_to_success_train(rows)[1] == [True, False]
    assert features_to_forecaster_train(rows)[1] == [50, 75]


@pytest.mark.asyncio
async def test_catalog_result_reaches_fenced_shared_text_voice_evidence():
    from app.services.intelligence_router import IntelligenceRouter, intelligence_context_block
    router = IntelligenceRouter.__new__(IntelligenceRouter)
    router.settings = MagicMock()
    router._run_catalog_capabilities = AsyncMock(return_value={"graph_neural_network": {
        "status": "ok", "predictions": [.75], "registry_ref": {"model_id": "graph-a", "version": 1}}})
    result = await router._run_enrichments("org-a", "review", {}, {"catalog_model_inputs": {
        "graph_neural_network": {"inputs": [1]}}, "defer_optional": True})
    block = intelligence_context_block(result)
    assert 'graph_neural_network' in block and 'graph-a' in block
    assert result["capabilities"]["predictive"]["status"] == "available"


@pytest.mark.asyncio
async def test_admin_verification_checks_actual_inference_and_reports_scope():
    from app.routers.ml_admin import InferenceVerificationRequest, verify_ml_inference
    with patch("app.ml.model_catalog.infer_catalog_capability", AsyncMock(return_value={"status": "ok", "used_fallback": False})) as infer:
        result = await verify_ml_inference("intent_classifier", InferenceVerificationRequest(inputs={"inputs": ["real query"]}),
                                           "org-a", ({"user_id": "admin"}, "org-a"), MagicMock())
        assert result["inference_health"] == "verified"
        assert result["org_id"] == "org-a"
        infer.assert_awaited_once()
        assert "does not establish model accuracy" in result["evidence_scope"]


def test_bound_corpus_uses_canonical_registry_and_rejects_wrong_purpose_or_org():
    from app.ml.bound_training_data import collect_bound_records

    class Query:
        def __init__(self, rows):
            self.rows = list(rows)
        def select(self, *_): return self
        def eq(self, key, value):
            self.rows = [row for row in self.rows if row.get(key) == value]
            return self
        def in_(self, key, values):
            self.rows = [row for row in self.rows if row.get(key) in values]
            return self
        def limit(self, count):
            self.rows = self.rows[:count]
            return self
        def order(self, *_): return self
        def execute(self): return SimpleNamespace(data=self.rows)

    contract = {"schema_version": 1, "model_name": "graph_neural_network", "target_definition": "human-reviewed relationship outcome"}
    tables = {
        "trained_models": [{"id": "model-a", "org_id": "org-a", "base_model": "graph_neural_network"}],
        "training_dataset_bindings": [{"org_id": "org-a", "target_id": "model-a", "target_type": "model",
                                       "purpose": "training", "dataset_id": "data-a", "metadata": contract}],
        "training_records": [
            {"org_id": "org-a", "dataset_id": "data-a", "input": "{}", "expected_output": "1",
             "metadata": {"synthetic": False, "source_ref": "audit-1", "label_source": "human_reviewed"}},
            {"org_id": "org-b", "dataset_id": "data-a", "input": "{}", "expected_output": "1",
             "metadata": {"synthetic": False, "source_ref": "audit-2", "label_source": "human_reviewed"}},
            {"org_id": "org-a", "dataset_id": "data-a", "input": "{}", "expected_output": "1", "metadata": {"synthetic": True}},
        ],
    }
    db = SimpleNamespace(table=lambda name: Query(tables[name]))
    with patch("app.ml.bound_training_data.get_supabase_client", return_value=db):
        records = collect_bound_records("org-a", "graph_neural_network", MagicMock())
        assert len(records) == 1 and records[0]["org_id"] == "org-a"
        assert collect_bound_records("org-b", "graph_neural_network", MagicMock()) == []
        tables["training_dataset_bindings"][0]["purpose"] = "benchmark"
        assert collect_bound_records("org-a", "graph_neural_network", MagicMock()) == []


@pytest.mark.asyncio
async def test_memory_review_receives_advice_without_changing_human_approval_state():
    from app.services.memory_promotion_service import MemoryPromotionService
    service = MemoryPromotionService(MagicMock())
    items = [{"id": "candidate-a", "status": "pending_approval", "frequency": 7}]
    with patch.object(service, "list_candidates", return_value={"items": items, "total": 1}), patch(
        "app.ml.model_catalog.infer_catalog_capability", AsyncMock(return_value={"status": "ok", "probabilities": [{"approve": .8, "reject": .2}],
                                                                               "registry_ref": {"model_id": "model-a", "version": 1}})
    ) as infer:
        result = await service.list_candidates_with_ml_advice("org-a", limit=50)
        assert result["items"][0]["status"] == "pending_approval"
        assert result["items"][0]["mlAdvice"]["approval_probability"] == .8
        assert result["items"][0]["mlAdvice"]["advisory_only"] is True
        assert infer.call_args.args[0] == "org-a"


@pytest.mark.asyncio
async def test_generic_registry_inference_also_overrides_payload_org_scope():
    from app.ml.base import ModelType
    from app.ml.inference import InferenceService
    model = SimpleNamespace(id="m", org_id="org-a", name="catalog-retrieval-memory", base_model="retrieval_memory_learner",
                            model_type=ModelType.CLASSIFIER, deployed_version=1, current_version=1)
    registry = SimpleNamespace(get_model=AsyncMock(return_value=model), log_prediction=AsyncMock())
    runtime = SimpleNamespace(predict=AsyncMock(return_value=([{"status": "ok", "summary": "scoped"}], None)))
    service = InferenceService()
    with patch("app.ml.inference.get_model_registry", return_value=registry), patch.object(
        service, "_load_runtime_model", AsyncMock(return_value=runtime)
    ), patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=True)):
        await service.predict("org-a", "m", [{"org_id": "org-b", "feature": 1}])
    assert runtime.predict.call_args.kwargs["org_id"] == "org-a"


@pytest.mark.asyncio
async def test_new_bound_draft_does_not_delay_first_automatic_training():
    from app.ml.automatic_training import reconcile_automatic_models
    lock = MagicMock()
    lock.acquire.return_value = True
    redis = MagicMock()
    redis.lock.return_value = lock
    registry = SimpleNamespace(list_models=AsyncMock(return_value=[SimpleNamespace(
        name="catalog-graph-neural-network", current_version=0, updated_at=datetime.now(UTC))]))
    with patch("app.ml.automatic_training.get_sync_redis", return_value=redis), patch(
        "app.ml.training_consent.load_training_consents", return_value={}
    ), patch("app.ml.training_consent.consent_is_approved", side_effect=lambda _, name: name == "graph_neural_network"), patch(
        "app.ml.registry.get_model_registry", return_value=registry
    ), patch("app.ml.intelligence_training.train_catalog_model", AsyncMock(return_value={"trained": False, "reason": "eligible_bound_training_records_required"})) as train:
        result = await reconcile_automatic_models("org-a", MagicMock())
    train.assert_awaited_once()
    assert train.call_args.args == ("org-a", "graph_neural_network")
    assert result["models"]["graph_neural_network"]["reason"] == "eligible_bound_training_records_required"
    lock.release.assert_called_once()
