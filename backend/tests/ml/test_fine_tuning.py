from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ml.fine_tuning import FineTunedLLM, FineTuningExample, convert_dataset_to_examples


@pytest.mark.asyncio
async def test_fine_tuning_train_and_status_with_mocked_client():
    model = FineTunedLLM()
    client = SimpleNamespace(
        fine_tuning=SimpleNamespace(
            jobs=SimpleNamespace(
                create=AsyncMock(return_value=SimpleNamespace(id="ftjob_1", status="validating_files")),
                retrieve=AsyncMock(
                    return_value=SimpleNamespace(
                        id="ftjob_1",
                        status="succeeded",
                        created_at=1,
                        finished_at=2,
                        fine_tuned_model="ft:gpt-4o-mini:test",
                        trained_tokens=123,
                        error=None,
                    )
                ),
                list_events=AsyncMock(return_value=SimpleNamespace(data=[])),
            )
        ),
        files=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(id="file_1"))),
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
                    )
                )
            )
        ),
        models=SimpleNamespace(delete=AsyncMock(return_value=SimpleNamespace(deleted=True))),
    )
    model.client = client  # bypass real OpenAI
    model.openai_job_id = "ftjob_1"
    model.fine_tuned_model_id = "ft:gpt-4o-mini:test"

    outputs, _ = await model.predict([{"messages": [{"role": "user", "content": "hi"}]}])
    assert outputs == ["ok"]

    status = await model.get_job_status()
    assert status["status"] == "succeeded"


def test_convert_dataset_to_examples():
    rows = [{"input": "hello", "expected_output": "world"}]
    examples = convert_dataset_to_examples(rows, system_prompt="you are helpful")
    assert isinstance(examples[0], FineTuningExample)
    assert examples[0].messages[0]["role"] == "system"
