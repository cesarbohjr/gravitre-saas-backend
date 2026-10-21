"""Every catalog entry has an explicit lifecycle; execution is not outcome proof."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.inference_evidence import PROOF_TYPE, record_execution, recent_execution_evidence
from app.ml.lifecycle import model_lifecycle_contract, resolve_lifecycle
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, load_org_trained_catalog_model


def test_all_26_models_have_assigned_lifecycles_without_silent_activation():
    from app.ml.automatic_training import CONSENT_MANAGED_MODELS
    from app.ml.base import ModelStatus
    assert len(GRAVITRE_ML_CATALOG) == 26
    for name in GRAVITRE_ML_CATALOG:
        assert model_lifecycle_contract(name)["mode"] != "unassigned"
    core = {name for name, meta in GRAVITRE_ML_CATALOG.items() if meta["status"] == ModelStatus.TRAINED}
    assert len(core) == 14 and core <= set(CONSENT_MANAGED_MODELS)
    assert model_lifecycle_contract("federated_learning")["state"] == "infrastructure_prerequisites_unverified"
    # Generation now has an implemented governed tool, never training controls.
    image = model_lifecycle_contract("diffusion_model")
    assert image["consent_prompt_supported"]
    assert image["mode"] == "governed_provider_tool"
    assert not image["automatic_training_supported"]


def test_lifecycle_never_uses_catalog_or_artifact_as_inference_proof():
    runtime = {"artifact_loaded": True, "deployed_model_id": "model-a", "deployed_version": 2}
    permission = {"consent_state": "approved", "observed_count": 0, "candidate_data_detected": False}
    assert resolve_lifecycle("intent_classifier", runtime, permission)["state"] == "artifact_ready_inference_unverified"
    evidence = {"model_id": "model-a", "version": 1}
    assert not resolve_lifecycle("intent_classifier", runtime, permission, evidence)["inference_verified"]
    evidence["version"] = 2
    assert resolve_lifecycle("intent_classifier", runtime, permission, evidence)["state"] == "inference_verified"
    assert resolve_lifecycle("intent_classifier", {**runtime, "artifact_load_failed": True}, permission, evidence)["state"] == "failed"
    permission["consent_state"] = "paused"
    assert resolve_lifecycle("intent_classifier", runtime, permission, evidence)["state"] == "paused"
    permission["consent_state"] = "revoked"
    assert resolve_lifecycle("intent_classifier", runtime, permission, evidence)["state"] == "disabled"


@pytest.mark.asyncio
async def test_execution_ledger_contains_no_input_output_and_skips_diagnostics():
    registry = SimpleNamespace(log_prediction=AsyncMock())
    with patch("app.ml.registry.get_model_registry", return_value=registry):
        diagnostic = await record_execution("org-a", "intent_classifier", {"model_id": "m", "version": 1}, 12, "diagnostic")
        assert not diagnostic["recorded"]
        registry.log_prediction.assert_not_called()
        actual = await record_execution("org-a", "intent_classifier", {"model_id": "m", "version": 1}, 12, "intelligence_router")
    assert actual["recorded"]
    payload = registry.log_prediction.call_args.kwargs
    assert payload["org_id"] == "org-a"
    assert set(payload["prediction"]) == {"execution_evidence"}
    assert payload["prediction"]["execution_evidence"]["proof_type"] == PROOF_TYPE
    assert payload["input_hash"].startswith("invocation:")


@pytest.mark.asyncio
async def test_evidence_ignores_legacy_and_expired_rows():
    now = datetime.now(UTC)
    proof = {"proof_type": PROOF_TYPE, "catalog_model": "intent_classifier", "source": "intelligence_router", "trace_id": "trace-a"}
    rows = [{"model_id": "m", "version": 2, "created_at": now.isoformat(), "execution_evidence": proof},
            {"model_id": "x", "version": 1, "created_at": (now-timedelta(days=2)).isoformat(),
             "execution_evidence": {**proof, "catalog_model": "churn_risk_scorer"}},
            {"model_id": "legacy", "version": 1, "created_at": now.isoformat()},
            {"model_id": "bad", "version": 1, "created_at": now.isoformat(), "execution_evidence": {**proof, "source": []}}]
    with patch("app.ml.inference_evidence._read_recent", return_value=rows):
        evidence = await recent_execution_evidence("org-a", MagicMock())
    assert list(evidence) == ["intent_classifier"]
    assert evidence["intent_classifier"]["downstream_consumption"] == "not_verified"


@pytest.mark.asyncio
async def test_wrapper_loads_existing_ranker_and_requires_both_permissions():
    model = SimpleNamespace(name="company-retrieval-ranker", id="ranker-a", deployed_version=2)
    registry = SimpleNamespace(list_models=AsyncMock(return_value=[model]), load_model_artifact=AsyncMock(return_value=b"ranker"))
    instance = MagicMock()
    # This fixture represents a local ranker, not an invented federated tag
    # returned by MagicMock's dynamic attribute creation.
    instance.federation = None
    instance._ranker.federation = None
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=True)), patch(
        "app.ml.registry.get_model_registry", return_value=registry
    ), patch("app.ml.model_catalog.get_model_instance", return_value=instance):
        loaded = await load_org_trained_catalog_model("org-a", "retrieval_memory_learner", settings=MagicMock())
    instance.load.assert_called_once_with(b"ranker")
    assert loaded.registry_ref == {"model_id": "ranker-a", "version": 2}
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(side_effect=[True, False])), patch(
        "app.ml.registry.get_model_registry"
    ) as lookup:
        await load_org_trained_catalog_model("org-a", "retrieval_memory_learner", settings=MagicMock())
    lookup.assert_not_called()


@pytest.mark.asyncio
async def test_manual_training_cannot_queue_before_current_consent(monkeypatch):
    from fastapi import HTTPException
    from app.routers.ml_admin import train_ml_model
    monkeypatch.setenv("TEMPORAL_HOST", "temporal.test:7233")
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=False)), patch(
        "app.routers.ml_admin.start_ml_model_training_workflow", AsyncMock()
    ) as queue:
        with pytest.raises(HTTPException) as error:
            await train_ml_model("sla_breach_predictor", "org-a", ({"user_id": "admin"}, "org-a"), MagicMock())
    assert error.value.status_code == 409
    queue.assert_not_called()


@pytest.mark.asyncio
async def test_composite_cannot_train_an_unapproved_component():
    from app.ml.intelligence_training import train_retrieval_memory_learner
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(side_effect=[True, False])), patch(
        "app.ml.intelligence_training.train_v5_retrieval_ranker", AsyncMock()
    ) as ranker, patch("app.ml.intelligence_training.get_supabase_client") as client:
        result = await train_retrieval_memory_learner("org-a", settings=MagicMock())
    assert result["reason"] == "component_training_permission_inactive"
    ranker.assert_not_called()
    client.assert_not_called()


@pytest.mark.asyncio
async def test_retrieval_wrapper_delegates_real_prediction_not_summary_counts():
    from app.ml.retrieval_learning import RetrievalMemoryLearner
    model = RetrievalMemoryLearner(MagicMock())
    model._ranker = SimpleNamespace(model=object(), predict=AsyncMock(return_value=([1], [{"helpful": .8}])))
    with patch.object(model, "get_retrieval_quality_summary", AsyncMock()) as summary:
        predictions, _ = await model.predict([{"rerank_score": .6}], org_id="org-a", return_probabilities=True)
    assert predictions == [1]
    summary.assert_not_called()


@pytest.mark.asyncio
async def test_all_temporal_enqueue_callers_share_consent_gate():
    from app.temporal.starters import start_ml_model_training_workflow
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=False)), patch(
        "app.temporal.starters.get_temporal_client", AsyncMock()
    ) as client:
        result = await start_ml_model_training_workflow("org-a", "deal_loss_scorer")
    assert result["status"] == "awaiting_consent"
    client.assert_not_called()


@pytest.mark.asyncio
async def test_training_readiness_uses_bound_labels_not_aggregate_outcome_counts():
    from app.services.training_signal_service import TrainingSignalService
    service = TrainingSignalService.__new__(TrainingSignalService)
    service.settings = MagicMock()
    service.MODEL_MIN_THRESHOLDS = {"sla_breach_predictor": {"min_labeled_ticket_records": 60},
                                    "deal_loss_scorer": {"min_labeled_deal_records": 25}}
    service._client = MagicMock()
    service._last_trained_at = AsyncMock(return_value=None)
    with patch("app.ml.model_catalog._count_org_data_points", return_value={
        "data_counts": {"provenance_bearing_bound_candidates": 65, "ticket_volume_rows": 0, "measured_deal_outcomes": 0}
    }):
        readiness = await service.get_training_readiness("org-a")
    assert readiness["by_model"]["sla_breach_predictor"]["signals_available"] == 65
    assert readiness["by_model"]["deal_loss_scorer"]["signals_available"] == 65


@pytest.mark.asyncio
async def test_draft_registry_target_is_not_recent_training_evidence():
    from app.services.training_signal_service import TrainingSignalService
    service = TrainingSignalService.__new__(TrainingSignalService)
    row = SimpleNamespace(name="catalog-sla-breach", current_version=0, updated_at=datetime.now(UTC))
    with patch("app.ml.registry.get_model_registry", return_value=SimpleNamespace(list_models=AsyncMock(return_value=[row]))):
        assert await service._last_trained_at("org-a", "sla_breach_predictor") is None
