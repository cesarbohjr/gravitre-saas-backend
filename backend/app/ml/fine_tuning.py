"""OpenAI fine-tuning integration."""
from __future__ import annotations

import json
import pickle
import tempfile
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.core.logging import get_logger
from app.ml.base import BaseMLModel, ModelMetrics, ModelType

logger = get_logger(__name__)


class FineTuningExample(BaseModel):
    """Single fine-tuning example."""

    messages: list[dict[str, str]]


class FineTuningConfig(BaseModel):
    """Configuration for fine-tuning job."""

    base_model: str = "gpt-4o-mini-2024-07-18"
    n_epochs: int | str = "auto"
    batch_size: int | str = "auto"
    learning_rate_multiplier: float | str = "auto"
    suffix: str | None = None


class FineTunedLLM(BaseMLModel):
    """OpenAI fine-tuned model wrapper."""

    model_type = ModelType.FINE_TUNED_LLM

    def __init__(self, config: FineTuningConfig | None = None):
        self.config = config or FineTuningConfig()
        self.client: AsyncOpenAI | None = None
        self.fine_tuned_model_id: str | None = None
        self.openai_job_id: str | None = None
        self._training_file_id: str | None = None
        self._validation_file_id: str | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self.client is None:
            settings = get_settings()
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self.client

    async def prepare_training_data(
        self,
        examples: list[FineTuningExample],
        validation_split: float = 0.1,
    ) -> tuple[str, str | None]:
        client = self._get_client()
        split_idx = int(len(examples) * (1 - validation_split))
        train_examples = examples[:split_idx]
        val_examples = examples[split_idx:] if validation_split > 0 else []

        async def upload_jsonl(data: list[FineTuningExample], purpose: str) -> str:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
                for example in data:
                    f.write(json.dumps({"messages": example.messages}) + "\n")
                f.flush()
                with open(f.name, "rb") as upload_file:
                    response = await client.files.create(file=upload_file, purpose=purpose)
                    return response.id

        self._training_file_id = await upload_jsonl(train_examples, "fine-tune")
        if val_examples:
            self._validation_file_id = await upload_jsonl(val_examples, "fine-tune")

        logger.info(
            "fine_tuning_data_uploaded training_file_id=%s validation_file_id=%s train=%s val=%s",
            self._training_file_id,
            self._validation_file_id,
            len(train_examples),
            len(val_examples),
        )
        return self._training_file_id, self._validation_file_id

    async def train(
        self,
        X: list[dict] | None = None,
        y: list[str] | None = None,
        examples: list[FineTuningExample] | None = None,
        training_file_id: str | None = None,
        validation_file_id: str | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = X, y
        client = self._get_client()
        if examples and not training_file_id:
            training_file_id, validation_file_id = await self.prepare_training_data(
                examples,
                validation_split=kwargs.get("validation_split", 0.1),
            )
        if not training_file_id:
            raise ValueError("Either examples or training_file_id required")

        job_params: dict[str, Any] = {"training_file": training_file_id, "model": self.config.base_model}
        if validation_file_id:
            job_params["validation_file"] = validation_file_id
        if self.config.suffix:
            job_params["suffix"] = self.config.suffix
        hyperparameters: dict[str, Any] = {}
        if self.config.n_epochs != "auto":
            hyperparameters["n_epochs"] = self.config.n_epochs
        if self.config.batch_size != "auto":
            hyperparameters["batch_size"] = self.config.batch_size
        if self.config.learning_rate_multiplier != "auto":
            hyperparameters["learning_rate_multiplier"] = self.config.learning_rate_multiplier
        if hyperparameters:
            job_params["hyperparameters"] = hyperparameters

        job = await client.fine_tuning.jobs.create(**job_params)
        self.openai_job_id = job.id
        logger.info("fine_tuning_job_created job_id=%s base_model=%s status=%s", job.id, self.config.base_model, job.status)
        return ModelMetrics(
            custom_metrics={
                "openai_job_id": job.id,
                "status": job.status,
                "base_model": self.config.base_model,
            }
        )

    async def get_job_status(self) -> dict[str, Any]:
        if not self.openai_job_id:
            raise ValueError("No fine-tuning job started")
        client = self._get_client()
        job = await client.fine_tuning.jobs.retrieve(self.openai_job_id)
        result = {
            "job_id": job.id,
            "status": job.status,
            "created_at": job.created_at,
            "finished_at": job.finished_at,
            "fine_tuned_model": job.fine_tuned_model,
            "trained_tokens": job.trained_tokens,
            "error": job.error.message if job.error else None,
        }
        if job.status == "succeeded" and job.fine_tuned_model:
            self.fine_tuned_model_id = job.fine_tuned_model
        return result

    async def get_training_metrics(self) -> ModelMetrics:
        if not self.openai_job_id:
            raise ValueError("No fine-tuning job started")
        client = self._get_client()
        job = await client.fine_tuning.jobs.retrieve(self.openai_job_id)
        if job.status != "succeeded":
            return ModelMetrics(custom_metrics={"status": job.status, "error": job.error.message if job.error else None})

        events = await client.fine_tuning.jobs.list_events(fine_tuning_job_id=self.openai_job_id, limit=100)
        training_loss = None
        validation_loss = None
        for event in events.data:
            if event.type == "metrics" and event.data:
                if "train_loss" in event.data:
                    training_loss = event.data["train_loss"]
                if "valid_loss" in event.data:
                    validation_loss = event.data["valid_loss"]
        self.fine_tuned_model_id = job.fine_tuned_model
        return ModelMetrics(
            training_loss=training_loss,
            validation_loss=validation_loss,
            custom_metrics={
                "openai_job_id": job.id,
                "fine_tuned_model": job.fine_tuned_model,
                "trained_tokens": job.trained_tokens,
                "status": "succeeded",
            },
        )

    async def predict(
        self,
        X: list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[str], None]:
        _ = return_probabilities, kwargs
        if not self.fine_tuned_model_id:
            raise ValueError("Model not trained or training not complete")
        client = self._get_client()
        results: list[str] = []
        for item in X:
            messages = item.get("messages", [{"role": "user", "content": str(item)}])
            response = await client.chat.completions.create(
                model=self.fine_tuned_model_id,
                messages=messages,
                temperature=item.get("temperature", 0.7),
                max_tokens=item.get("max_tokens", 500),
            )
            results.append(response.choices[0].message.content or "")
        return results, None

    def save(self) -> bytes:
        return pickle.dumps(
            {
                "config": self.config.model_dump(),
                "fine_tuned_model_id": self.fine_tuned_model_id,
                "openai_job_id": self.openai_job_id,
            }
        )

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self.config = FineTuningConfig(**loaded["config"])
        self.fine_tuned_model_id = loaded["fine_tuned_model_id"]
        self.openai_job_id = loaded["openai_job_id"]

    async def cancel_job(self) -> dict[str, Any]:
        if not self.openai_job_id:
            raise ValueError("No fine-tuning job to cancel")
        client = self._get_client()
        job = await client.fine_tuning.jobs.cancel(self.openai_job_id)
        return {"job_id": job.id, "status": job.status}

    async def delete_model(self) -> bool:
        if not self.fine_tuned_model_id:
            raise ValueError("No fine-tuned model to delete")
        client = self._get_client()
        response = await client.models.delete(self.fine_tuned_model_id)
        logger.info("fine_tuned_model_deleted model_id=%s", self.fine_tuned_model_id)
        return bool(response.deleted)


def convert_dataset_to_examples(records: list[dict], system_prompt: str | None = None) -> list[FineTuningExample]:
    """Convert training records to OpenAI fine-tuning examples."""
    examples: list[FineTuningExample] = []
    for record in records:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": record["input"]})
        messages.append({"role": "assistant", "content": record["expected_output"]})
        examples.append(FineTuningExample(messages=messages))
    return examples
