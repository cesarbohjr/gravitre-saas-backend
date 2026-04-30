"""Base classes for Gravitre ML models."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field

T = TypeVar("T")


class ModelType(str, Enum):
    """Types of ML models supported."""

    CLASSIFIER = "classifier"
    FINE_TUNED_LLM = "fine_tuned_llm"
    ANOMALY_DETECTOR = "anomaly_detector"
    FORECASTER = "forecaster"
    EMBEDDING = "embedding"


class ModelStatus(str, Enum):
    """Training/deployment status."""

    DRAFT = "draft"
    TRAINING = "training"
    VALIDATING = "validating"
    READY = "ready"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ModelMetrics(BaseModel):
    """Standard metrics for model evaluation."""

    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    auc_roc: float | None = None
    mse: float | None = None
    mae: float | None = None
    r2_score: float | None = None
    confusion_matrix: list[list[int]] | None = None
    classification_report: dict[str, Any] | None = None
    training_loss: float | None = None
    validation_loss: float | None = None
    training_samples: int | None = None
    validation_samples: int | None = None
    training_duration_seconds: float | None = None
    custom_metrics: dict[str, float | str | int | bool | None] = Field(default_factory=dict)


class ModelVersion(BaseModel):
    """Model version metadata."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    model_id: str
    version: int
    artifact_url: str | None = None
    artifact_size_bytes: int | None = None
    metrics: ModelMetrics = Field(default_factory=ModelMetrics)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    feature_names: list[str] = Field(default_factory=list)
    label_encoder: dict[str, int] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None


class TrainedModel(BaseModel):
    """Trained model metadata."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str
    name: str
    description: str | None = None
    model_type: ModelType
    status: ModelStatus = ModelStatus.DRAFT
    current_version: int = 0
    deployed_version: int | None = None
    dataset_id: str | None = None
    base_model: str | None = None
    task_type: str | None = None
    target_column: str | None = None
    feature_columns: list[str] = Field(default_factory=list)
    versions: list[ModelVersion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None


class PredictionRequest(BaseModel):
    """Request for model prediction."""

    model_id: str
    version: int | None = None
    inputs: list[dict[str, Any]]
    return_probabilities: bool = False


class PredictionResult(BaseModel):
    """Result from model prediction."""

    model_id: str
    version: int
    predictions: list[Any]
    probabilities: list[dict[str, float]] | None = None
    latency_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BaseMLModel(ABC, Generic[T]):
    """Abstract base class for all ML models."""

    model_type: ModelType
    model: T | None = None

    @abstractmethod
    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[str] | list[float] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        """Train the model on data."""

    @abstractmethod
    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        """Make predictions."""

    @abstractmethod
    def save(self) -> bytes:
        """Serialize model to bytes."""

    @abstractmethod
    def load(self, data: bytes) -> None:
        """Load model from bytes."""

    def get_feature_importance(self) -> dict[str, float] | None:
        """Get feature importance if available."""
        return None
