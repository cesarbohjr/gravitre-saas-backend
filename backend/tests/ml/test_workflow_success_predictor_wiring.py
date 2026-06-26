from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.base import ModelMetrics
from app.ml.forecasting import WorkflowSuccessPredictor
from app.ml.inference import InferenceService
from app.workers.training_worker import TrainingWorker


def _workflow_features(count: int = 35) -> list[dict]:
    return [
        {
            "step_count": 3 + (i % 2),
            "error_count": 0 if i % 4 else 2,
            "retry_count": 0,
            "longest_step_duration_ms": 500.0,
            "avg_step_duration_ms": 250.0,
            "node_count": 4,
            "connector_node_count": 1,
            "agent_node_count": 1,
            "condition_node_count": 1,
            "has_approval_gate": 0,
            "max_graph_depth": 3,
            "run_hour_of_day": 10,
            "run_day_of_week": 2,
            "run_is_weekend": 0,
        }
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_training_worker_recognizes_success_predictor_model_base(monkeypatch):
    worker = TrainingWorker()
    fake_client = MagicMock()
    monkeypatch.setattr("app.workers.training_worker.get_supabase_client", lambda settings: fake_client)

    jobs = [{"id": "job1", "dataset_id": "ds1", "model_base": "success_predictor", "org_id": "org1", "created_by": "u1"}]
    datasets = [{"id": "ds1", "name": "dataset-1"}]
    records = [
        {"input": '{"step_count": 3, "node_count": 4}', "expected_output": "success"},
        {"input": '{"step_count": 5, "node_count": 6}', "expected_output": "failure"},
    ] * 20

    def table_select(name):
        q = MagicMock()
        q.eq.return_value = q
        q.order.return_value = q
        q.limit.return_value = q
        if name == "training_jobs":
            q.execute.return_value = SimpleNamespace(data=jobs)
        elif name == "training_datasets":
            q.execute.return_value = SimpleNamespace(data=datasets)
        elif name == "training_records":
            q.execute.return_value = SimpleNamespace(data=records)
        else:
            q.execute.return_value = SimpleNamespace(data=[])
        return q

    fake_client.table.side_effect = lambda name: SimpleNamespace(
        select=lambda *_args, **_kwargs: table_select(name),
        update=lambda *_args, **_kwargs: SimpleNamespace(eq=lambda *_a, **_k: SimpleNamespace(execute=lambda: SimpleNamespace(data=[{}]))),
    )

    fake_registry = MagicMock()
    fake_registry.list_models = AsyncMock(return_value=[])
    fake_registry.create_model = AsyncMock(return_value=SimpleNamespace(id="model1"))
    fake_registry.add_version = AsyncMock(return_value=SimpleNamespace(version=1))
    fake_registry.deploy_version = AsyncMock(return_value=True)
    monkeypatch.setattr("app.workers.training_worker.get_model_registry", lambda: fake_registry)

    await worker.process_job("job1")
    assert fake_registry.add_version.await_count == 1


@pytest.mark.asyncio
async def test_inference_service_can_load_success_predictor_artifact():
    service = InferenceService()
    artifact = WorkflowSuccessPredictor()
    x_rows = _workflow_features(40)
    y_values = [True] * 20 + [False] * 20
    await artifact.train(x_rows, y_values)
    blob = artifact.save()
    runtime = WorkflowSuccessPredictor()
    runtime.load(blob)
    preds, probs = await runtime.predict([x_rows[0]], return_probabilities=True)
    assert preds
    assert probs is not None


@pytest.mark.asyncio
async def test_orchestrator_surfaces_at_risk_workflows():
    from app.services.company_intelligence_orchestrator import CompanyIntelligenceOrchestrator

    orchestrator = CompanyIntelligenceOrchestrator()
    predictor = WorkflowSuccessPredictor()
    await predictor.train(_workflow_features(), [True] * 20 + [False] * 15)

    client = MagicMock()
    with patch(
        "app.services.company_intelligence_orchestrator.fetch_active_workflow_definitions",
        new=AsyncMock(
            return_value=[
                {
                    "workflow_id": "wf-risky",
                    "definition_snapshot": {
                        "graph": {
                            "nodes": [{"id": "n1", "node_type": "agent"}],
                            "edges": [],
                        }
                    },
                }
            ]
        ),
    ):
        predictions = await orchestrator._predict_active_workflow_risk(predictor, "org-1", client)
    assert predictions
    assert predictions[0]["workflow_id"] == "wf-risky"
    assert "success_probability" in predictions[0]
