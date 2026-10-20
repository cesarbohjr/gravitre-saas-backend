"""Phase 1 ML honesty repairs: champion gate, real columns, catalog names,
baseline labelling, out-of-sample churn scoring, no zero-vector scoring."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml import intelligence_training as it
from app.ml.base import ModelMetrics, ModelType


# ---------------------------------------------------------------------------
# Recording fake PostgREST client
# ---------------------------------------------------------------------------
class _Query:
    def __init__(self, log: list[dict[str, Any]], table: str, data: list[dict[str, Any]]):
        self._log = log
        self._entry: dict[str, Any] = {"table": table, "select": None, "filters": []}
        self._data = data
        log.append(self._entry)

    def select(self, cols: str, **_: Any) -> "_Query":
        self._entry["select"] = cols
        return self

    def _filter(self, op: str, col: str, *args: Any) -> "_Query":
        self._entry["filters"].append((op, col, args))
        return self

    def eq(self, col: str, val: Any) -> "_Query":
        return self._filter("eq", col, val)

    def gte(self, col: str, val: Any) -> "_Query":
        return self._filter("gte", col, val)

    def in_(self, col: str, vals: Any) -> "_Query":
        return self._filter("in", col, vals)

    def is_(self, col: str, val: Any) -> "_Query":
        return self._filter("is", col, val)

    def order(self, col: str, **_: Any) -> "_Query":
        return self._filter("order", col)

    def limit(self, n: int) -> "_Query":
        return self

    @property
    def not_(self) -> "_Query":
        parent = self

        class _Not:
            def is_(self, col: str, val: Any) -> "_Query":
                return parent._filter("not_is", col, val)

        return _Not()  # type: ignore[return-value]

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self._data, count=len(self._data))


class _Client:
    def __init__(self, data: list[dict[str, Any]] | None = None):
        self.log: list[dict[str, Any]] = []
        self._data = data or []

    def table(self, name: str) -> _Query:
        return _Query(self.log, name, self._data)


def _columns_used(entry: dict[str, Any]) -> set[str]:
    cols = {c.strip() for c in (entry["select"] or "").split(",") if c.strip()}
    cols |= {col for _op, col, _args in entry["filters"]}
    return cols


# ---------------------------------------------------------------------------
# Fix 3: champion / challenger gate
# ---------------------------------------------------------------------------
def test_gate_first_deployment_needs_held_out_metric():
    deploy, reason, ev = it.champion_challenger_decision(ModelMetrics(accuracy=0.8), None, has_champion=False)
    assert (deploy, reason) == (True, "first_deployment_with_held_out_metric")
    assert ev["primary_metric"] == "accuracy"
    deploy, reason, _ = it.champion_challenger_decision(ModelMetrics(), None, has_champion=False)
    assert (deploy, reason) == (False, "not_deployed_no_held_out_metric")


def test_gate_first_classifier_must_beat_chance():
    deploy, reason, _ = it.champion_challenger_decision(ModelMetrics(auc_roc=0.5), None, has_champion=False)
    assert (deploy, reason) == (False, "not_deployed_first_version_not_better_than_chance")
    deploy, _, _ = it.champion_challenger_decision(ModelMetrics(auc_roc=0.62), None, has_champion=False)
    assert deploy is True


def test_gate_higher_is_better_metric():
    deploy, reason, ev = it.champion_challenger_decision(
        ModelMetrics(auc_roc=0.70, accuracy=0.99), {"auc_roc": 0.80, "accuracy": 0.5}, has_champion=True
    )
    assert (deploy, reason) == (False, "challenger_worse_than_champion")
    assert ev["primary_metric"] == "auc_roc"
    deploy, reason, _ = it.champion_challenger_decision(
        ModelMetrics(auc_roc=0.80), {"auc_roc": 0.80}, has_champion=True
    )
    assert deploy is True and reason == "challenger_matches_or_beats_champion"


def test_gate_lower_is_better_metric():
    deploy, _, ev = it.champion_challenger_decision(
        ModelMetrics(mae=12.0), {"mae": 10.0}, has_champion=True
    )
    assert deploy is False
    assert ev["higher_is_better"] is False
    deploy, _, _ = it.champion_challenger_decision(ModelMetrics(mae=8.0), {"mae": 10.0}, has_champion=True)
    assert deploy is True


def test_gate_never_auto_deploys_unvalidated_models():
    # Unsupervised output (no held-out metric): registered, never promoted.
    deploy, reason, _ = it.champion_challenger_decision(
        ModelMetrics(custom_metrics={"silhouette": 0.4}), {"custom_metrics": {}}, has_champion=True
    )
    assert (deploy, reason) == (False, "not_deployed_no_held_out_metric")
    # Champion has no comparable metric: no replacement without a comparison.
    deploy, reason, _ = it.champion_challenger_decision(ModelMetrics(f1_score=0.9), {"mae": 3.0}, has_champion=True)
    assert (deploy, reason) == (False, "not_deployed_no_comparable_champion_metric")


@pytest.mark.asyncio
async def test_unvalidated_first_model_is_registered_but_not_deployed():
    registry = _fake_registry()
    with patch.object(it, "get_model_registry", return_value=registry):
        result = await it.register_trained_artifact_detailed(
            "org-1",
            name="catalog-anomaly",
            model_type=ModelType.CLASSIFIER,
            base_model="anomaly_detector",
            artifact=b"x",
            metrics=ModelMetrics(),
        )
    registry.add_version.assert_awaited_once()
    registry.deploy_version.assert_not_awaited()
    assert result["deployed"] is False
    assert result["reason"] == "not_deployed_no_held_out_metric"


def _fake_registry(*, existing: Any = None, champion_metrics: dict | None = None) -> MagicMock:
    registry = MagicMock()
    registry.list_models = AsyncMock(return_value=[existing] if existing else [])
    registry.create_model = AsyncMock(return_value=SimpleNamespace(id="new-model"))
    registry.add_version = AsyncMock(return_value=SimpleNamespace(version=4))
    registry.deploy_version = AsyncMock(return_value=True)
    registry.get_version_metrics = AsyncMock(return_value=champion_metrics)
    return registry


@pytest.mark.asyncio
async def test_worse_challenger_is_registered_but_not_deployed():
    existing = SimpleNamespace(id="m1", name="catalog-query-intent", deployed_version=3)
    registry = _fake_registry(existing=existing, champion_metrics={"f1_score": 0.9, "accuracy": 0.9})
    with patch.object(it, "get_model_registry", return_value=registry):
        result = await it.register_trained_artifact_detailed(
            "org-1",
            name="catalog-query-intent",
            model_type=ModelType.CLASSIFIER,
            base_model="intent_classifier",
            artifact=b"x",
            metrics=ModelMetrics(f1_score=0.7, accuracy=0.95),
        )
    registry.add_version.assert_awaited_once()
    registry.get_version_metrics.assert_awaited_once_with("m1", 3)
    registry.deploy_version.assert_not_awaited()
    assert result["model_id"] == "m1"
    assert result["deployed"] is False
    assert result["reason"] == "challenger_worse_than_champion"
    summary = it.registration_summary(result)
    assert summary["trained"] is True and summary["deployed"] is False


@pytest.mark.asyncio
async def test_better_challenger_deploys_new_version():
    existing = SimpleNamespace(id="m1", name="catalog-query-intent", deployed_version=3)
    registry = _fake_registry(existing=existing, champion_metrics={"f1_score": 0.7})
    with patch.object(it, "get_model_registry", return_value=registry):
        result = await it.register_trained_artifact_detailed(
            "org-1",
            name="catalog-query-intent",
            model_type=ModelType.CLASSIFIER,
            base_model="intent_classifier",
            artifact=b"x",
            metrics=ModelMetrics(f1_score=0.8),
        )
    registry.deploy_version.assert_awaited_once_with("m1", 4)
    assert result["deployed"] is True


@pytest.mark.asyncio
async def test_missing_blob_token_returns_explicit_reason():
    registry = _fake_registry()
    registry.add_version = AsyncMock(side_effect=ValueError("BLOB_READ_WRITE_TOKEN not configured"))
    with patch.object(it, "get_model_registry", return_value=registry):
        result = await it.register_trained_artifact_detailed(
            "org-1",
            name="catalog-churn-risk",
            model_type=ModelType.CLASSIFIER,
            base_model="churn_risk_scorer",
            artifact=b"x",
            metrics=ModelMetrics(accuracy=0.8),
        )
    assert result["model_id"] is None
    assert result["reason"] == it.REASON_ARTIFACT_STORAGE_UNAVAILABLE
    summary = it.registration_summary(result)
    assert summary["trained"] is False
    assert summary["reason"] == "artifact_storage_unavailable"
    registry.deploy_version.assert_not_awaited()


# ---------------------------------------------------------------------------
# Fix 2: trainers only select real agent_action_outcomes columns
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_revenue_trainer_selects_only_real_columns():
    client = _Client([])
    result = await it.train_revenue_forecaster("org-1", settings=MagicMock(), client=client)
    assert result["trained"] is False
    entries = [e for e in client.log if e["table"] == "agent_action_outcomes"]
    assert entries
    for entry in entries:
        assert _columns_used(entry) <= it.AGENT_ACTION_OUTCOMES_COLUMNS
    assert "metric_value_after" in entries[0]["select"]


@pytest.mark.asyncio
async def test_capacity_trainer_selects_only_real_columns():
    client = _Client([{"metric_value_after": 5.0, "measured_at": "2026-10-01"}])
    result = await it.train_capacity_forecaster("org-1", settings=MagicMock(), client=client)
    assert result["trained"] is False
    assert result["reason"] == "insufficient_data"
    for entry in client.log:
        assert _columns_used(entry) <= it.AGENT_ACTION_OUTCOMES_COLUMNS


@pytest.mark.asyncio
@pytest.mark.parametrize("trainer", ["train_sla_breach_predictor", "train_deal_loss_scorer"])
async def test_label_less_trainers_refuse_without_querying(trainer: str):
    client = _Client([])
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=False)):
        result = await getattr(it, trainer)("org-1", settings=MagicMock(), client=client)
    assert result["trained"] is False
    assert result["reason"] == "training_permission_inactive"
    assert client.log == []


@pytest.mark.asyncio
async def test_causal_loader_selects_only_real_columns():
    from app.ml.causal_analysis import CausalImpactAnalyzer

    client = _Client([{"metric_value_before": 1.0, "metric_value_after": 3.0, "measured_at": "2026-10-01"}])
    with patch("app.ml.causal_analysis.get_supabase_client", return_value=client):
        series = CausalImpactAnalyzer()._load_pairs("org-1", "deal_amount", MagicMock())
    assert series == [(1.0, 3.0)]
    for entry in client.log:
        assert _columns_used(entry) <= it.AGENT_ACTION_OUTCOMES_COLUMNS


# ---------------------------------------------------------------------------
# Fix 1: orchestrator writes to the catalog-* entries live loaders read
# ---------------------------------------------------------------------------
def test_orchestrator_uses_catalog_registry_names():
    from app.services.company_intelligence_orchestrator import COMPANY_MODEL_NAMES

    assert COMPANY_MODEL_NAMES["intent"] == it.CATALOG_MODEL_NAMES["intent_classifier"] == "catalog-query-intent"
    assert COMPANY_MODEL_NAMES["anomaly"] == it.CATALOG_MODEL_NAMES["workflow_anomaly_detector"]
    assert COMPANY_MODEL_NAMES["forecaster"] == it.CATALOG_MODEL_NAMES["workflow_duration_forecaster"]
    assert COMPANY_MODEL_NAMES["success"] == it.CATALOG_MODEL_NAMES["workflow_success_predictor"]
    for name in COMPANY_MODEL_NAMES.values():
        assert name in set(it.CATALOG_MODEL_NAMES.values())


@pytest.mark.asyncio
async def test_orchestrator_registration_goes_through_champion_gate():
    from app.services import company_intelligence_orchestrator as orch_mod

    orchestrator = orch_mod.CompanyIntelligenceOrchestrator(settings=MagicMock())
    gated = AsyncMock(
        return_value={"model_id": "m1", "deployed": False, "reason": "challenger_worse_than_champion"}
    )
    with patch.object(orch_mod, "register_trained_artifact_detailed", gated):
        model_id = await orchestrator._register_or_update_model(
            "org-1",
            name=orch_mod.COMPANY_MODEL_NAMES["anomaly"],
            model_type=ModelType.ANOMALY_DETECTOR,
            base_model="anomaly_detector",
            artifact=b"x",
            metrics=ModelMetrics(),
        )
    assert model_id == "m1"
    assert gated.await_args.kwargs["name"] == "catalog-workflow-anomaly"


# ---------------------------------------------------------------------------
# Fix 5: revenue forecaster labelled as the mean baseline it is
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_revenue_forecaster_reports_mean_baseline():
    from app.ml.revenue_forecasting import RevenueForecaster

    forecaster = RevenueForecaster()
    series = [{"value": float(v)} for v in range(1, 21)]
    metrics = await forecaster.train([], time_series=series)
    assert metrics.custom_metrics["algorithm"] == "mean_baseline"
    assert metrics.validation_samples == 4
    out = await forecaster.predict_structured(horizon_days=14)
    assert out["method"] == "mean_baseline"
    expected = sum(range(7, 21)) / 14
    assert out["predicted_values"] == [pytest.approx(expected)] * 2
    assert "Holt" not in (RevenueForecaster.__doc__ or "")


# ---------------------------------------------------------------------------
# Fix 4: churn advisory scores only unlabelled customers
# ---------------------------------------------------------------------------
def _churn_client(labelled: list[dict], unlabelled: list[dict]) -> MagicMock:
    client = MagicMock()

    def _table(_name: str) -> MagicMock:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.not_.is_.return_value = MagicMock(
            execute=MagicMock(return_value=MagicMock(data=labelled))
        )
        chain.is_.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=unlabelled)))
        return chain

    client.table.side_effect = _table
    return client


_LABELLED = {
    "id": "1",
    "target_entity_id": "known-1",
    "metric_value_after": 1.0,
    "measured_at": "2026-07-18T00:00:00Z",
    "confidence_note": json.dumps({"days_since_last_activity": 90, "churned": True}),
}


@pytest.mark.asyncio
async def test_churn_advisory_never_scores_labelled_rows():
    from app.services.churn_advisory_service import build_churn_advisory_cards

    client = _churn_client([_LABELLED], [])
    with patch("app.ml.model_catalog.load_org_trained_catalog_model", AsyncMock(return_value=None)):
        payload = await build_churn_advisory_cards("org-1", settings=MagicMock(), client=client)
    assert payload["recommendations"] == []
    assert payload["reason"] == "no_unlabeled_customer_signals"
    assert payload["gate"]["current"] == 1


@pytest.mark.asyncio
async def test_churn_advisory_scores_only_unresolved_customers():
    from app.services.churn_advisory_service import build_churn_advisory_cards

    unresolved = {
        "id": "2",
        "target_entity_id": "open-2",
        "metric_value_after": None,
        "measured_at": None,
        "confidence_note": json.dumps({"days_since_last_activity": 40}),
    }
    # Same customer as the labelled row but unresolved -> still excluded.
    dup = {**unresolved, "id": "3", "target_entity_id": "known-1"}
    client = _churn_client([_LABELLED], [unresolved, dup])
    with patch("app.ml.model_catalog.load_org_trained_catalog_model", AsyncMock(return_value=None)):
        payload = await build_churn_advisory_cards("org-1", settings=MagicMock(), client=client)
    ids = [card["evidence"]["customerId"] for card in payload["recommendations"]]
    assert ids == ["open-2"]
    for card in payload["recommendations"]:
        assert card["executable"] is False


@pytest.mark.asyncio
async def test_completed_fine_tune_is_not_auto_deployed(monkeypatch):
    """Phase 1: a fine-tuned LLM job used to deploy itself with no held-out evaluation."""
    from types import SimpleNamespace

    from app.workers.training_worker import TrainingWorker

    worker = TrainingWorker()
    fake_client = MagicMock()
    monkeypatch.setattr("app.workers.training_worker.get_supabase_client", lambda settings: fake_client)
    rows = {
        "training_jobs": [{"id": "job1", "dataset_id": "ds1", "model_base": "gpt-4o-mini", "org_id": "org1", "created_by": "u1"}],
        "training_datasets": [{"id": "ds1", "name": "dataset-1"}],
        "training_records": [{"input": "hi", "expected_output": "hello"}],
    }

    def table_select(name):
        q = MagicMock()
        q.eq.return_value = q
        q.execute.return_value = SimpleNamespace(data=rows.get(name, []))
        return q

    fake_client.table.side_effect = lambda name: SimpleNamespace(
        select=lambda *_a, **_k: table_select(name),
        update=lambda *_a, **_k: SimpleNamespace(eq=lambda *_a, **_k: SimpleNamespace(execute=lambda: SimpleNamespace(data=[{}]))),
    )
    monkeypatch.setattr(
        worker, "_train_fine_tuned", AsyncMock(return_value=(None, b"ft-artifact"))
    )
    registry = MagicMock()
    registry.list_models = AsyncMock(return_value=[])
    registry.create_model = AsyncMock(return_value=SimpleNamespace(id="model1"))
    registry.add_version = AsyncMock(return_value=SimpleNamespace(version=1))
    registry.deploy_version = AsyncMock(return_value=True)
    monkeypatch.setattr("app.workers.training_worker.get_model_registry", lambda: registry)

    await worker.process_job("job1")

    registry.add_version.assert_awaited_once()
    registry.deploy_version.assert_not_awaited()


@pytest.fixture(autouse=True)
def _approved_training_scope_for_artifact_tests():
    """These tests exercise artifact/promotion behavior after consent is granted."""
    from unittest.mock import AsyncMock, patch
    with patch("app.ml.training_consent.training_is_approved", new_callable=AsyncMock, return_value=True):
        yield
