from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ml.base import ModelMetrics
from app.workers.training_worker import TrainingWorker


@pytest.mark.asyncio
async def test_training_worker_process_job_classifier(monkeypatch):
    worker = TrainingWorker()
    fake_client = MagicMock()
    monkeypatch.setattr("app.workers.training_worker.get_supabase_client", lambda settings: fake_client)

    jobs = [{"id": "job1", "dataset_id": "ds1", "model_base": "random_forest", "org_id": "org1", "created_by": "u1"}]
    datasets = [{"id": "ds1", "name": "dataset-1"}]
    records = [{"input": '{"f1": 1, "f2": 2}', "expected_output": "A"} for _ in range(10)] + [
        {"input": '{"f1": 2, "f2": 3}', "expected_output": "B"} for _ in range(10)
    ]

    def select_side_effect(*args, **kwargs):
        query = MagicMock()
        query.eq.return_value = query
        query.order.return_value = query
        query.limit.return_value = query
        if args and args[0] == "*":
            # chained by table name
            pass
        query.execute.return_value = SimpleNamespace(data=[])
        return query

    table = MagicMock()
    fake_client.table.return_value = table

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
    monkeypatch.setattr("app.workers.training_worker.get_model_registry", lambda: fake_registry)
    monkeypatch.setattr(worker, "_train_classifier", AsyncMock(return_value=(ModelMetrics(accuracy=0.9), b"model-bytes")))

    await worker.process_job("job1")
    assert fake_registry.add_version.await_count == 1
