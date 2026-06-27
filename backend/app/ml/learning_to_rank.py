"""v7 learning-to-rank extension over v5 source reliability weighting."""
from __future__ import annotations

import pickle
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.core.logging import get_logger
from app.ml.base import BaseMLModel, ModelMetrics, ModelType
from app.ml.registry import get_model_registry
from app.ml.source_reliability import (
    RELIABILITY_WEIGHT,
    clip_reliability_weight,
)

logger = get_logger(__name__)

FEATURE_NAMES = [
    "rerank_score",
    "source_reliability_score",
    "rank_position",
    "source_document_age_days",
]

RETRIEVAL_RANKER_MODEL_NAME = "company-retrieval-ranker"


class RetrievalRanker(BaseMLModel):
    """
    Learns reliability coefficient from chunk outcome features.
    Falls back to v5 RELIABILITY_WEIGHT when insufficient training data exists.
    """

    model_type = ModelType.CLASSIFIER
    MIN_TRAINING_EXAMPLES = 100

    def __init__(self) -> None:
        self.model: LogisticRegression | None = None
        self.scaler = StandardScaler()
        self.learned_reliability_weight: float | None = None

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[str] | list[float] | None = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        examples = list(X) if isinstance(X, list) else []
        if y is None and examples and "outcome_helpful" in examples[0]:
            labels = [1 if ex.get("outcome_helpful") else 0 for ex in examples]
        elif y is not None:
            labels = [1 if bool(value) else 0 for value in y]
        else:
            raise ValueError("Training labels required for RetrievalRanker")

        if len(examples) < self.MIN_TRAINING_EXAMPLES:
            raise ValueError(
                f"Need at least {self.MIN_TRAINING_EXAMPLES} examples, got {len(examples)}"
            )

        matrix = np.array([[float(ex.get(name) or 0.0) for name in FEATURE_NAMES] for ex in examples])
        y_arr = np.array(labels, dtype=int)
        x_train, x_test, y_train, y_test = train_test_split(
            matrix, y_arr, test_size=0.2, random_state=42, stratify=y_arr if len(set(y_arr)) > 1 else None
        )
        x_train_scaled = self.scaler.fit_transform(x_train)
        x_test_scaled = self.scaler.transform(x_test)

        self.model = LogisticRegression(max_iter=1000, class_weight="balanced")
        self.model.fit(x_train_scaled, y_train)

        rel_idx = FEATURE_NAMES.index("source_reliability_score")
        raw_coef = float(self.model.coef_[0][rel_idx])
        self.learned_reliability_weight = clip_reliability_weight(abs(raw_coef))

        predictions = self.model.predict(x_test_scaled)
        metrics = ModelMetrics(
            accuracy=float(accuracy_score(y_test, predictions)),
            f1_score=float(f1_score(y_test, predictions, zero_division=0)),
            training_samples=len(x_train),
            validation_samples=len(x_test),
            custom_metrics={
                "learned_reliability_weight": self.learned_reliability_weight,
            },
        )
        if len(set(y_test)) > 1:
            try:
                probabilities = self.model.predict_proba(x_test_scaled)[:, 1]
                metrics.auc_roc = float(roc_auc_score(y_test, probabilities))
            except ValueError:
                pass
        return metrics

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        examples = list(X) if isinstance(X, list) else []
        if not examples or self.model is None:
            return [], None
        matrix = np.array([[float(ex.get(name) or 0.0) for name in FEATURE_NAMES] for ex in examples])
        scaled = self.scaler.transform(matrix)
        preds = self.model.predict(scaled).tolist()
        probs = None
        if return_probabilities:
            prob_values = self.model.predict_proba(scaled)
            probs = [{"helpful": float(row[1]), "not_helpful": float(row[0])} for row in prob_values]
        return preds, probs

    async def predict_weight_adjustment(self, chunk_features: dict[str, Any]) -> float:
        """Learned coefficient for v5 additive mechanism; bounded fallback included."""
        if self.learned_reliability_weight is not None:
            return self.learned_reliability_weight
        return RELIABILITY_WEIGHT

    def get_learned_weight(self) -> float | None:
        return self.learned_reliability_weight

    def save(self) -> bytes:
        payload = {
            "model": self.model,
            "scaler": self.scaler,
            "learned_reliability_weight": self.learned_reliability_weight,
            "feature_names": FEATURE_NAMES,
        }
        return pickle.dumps(payload)

    def load(self, data: bytes) -> None:
        payload = pickle.loads(data)
        self.model = payload.get("model")
        self.scaler = payload.get("scaler") or StandardScaler()
        self.learned_reliability_weight = payload.get("learned_reliability_weight")


async def collect_training_examples(org_id: str, client: Any) -> list[dict[str, Any]]:
    """Build training rows from rag_chunk_outcomes with resolved feedback."""
    outcomes = (
        client.table("rag_chunk_outcomes")
        .select("rerank_score, rank_position, source_document_id, outcome_helpful, recorded_at")
        .eq("org_id", org_id)
        .not_.is_("outcome_helpful", "null")
        .execute()
        .data
        or []
    )
    if not outcomes:
        return []

    doc_ids = sorted({str(row.get("source_document_id") or "") for row in outcomes if row.get("source_document_id")})
    doc_updated: dict[str, str] = {}
    if doc_ids:
        docs = (
            client.table("rag_documents")
            .select("id, updated_at")
            .eq("org_id", org_id)
            .in_("id", doc_ids)
            .execute()
            .data
            or []
        )
        doc_updated = {str(row["id"]): str(row.get("updated_at") or "") for row in docs}

    from app.ml.source_reliability import fetch_source_reliability_scores

    reliability_scores = await fetch_source_reliability_scores(org_id, client)
    now = datetime.now(timezone.utc)
    examples: list[dict[str, Any]] = []
    for row in outcomes:
        doc_id = str(row.get("source_document_id") or "")
        updated_raw = doc_updated.get(doc_id, "")
        age_days = 0.0
        if updated_raw:
            try:
                updated_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
                age_days = max(0.0, (now - updated_at).total_seconds() / 86400.0)
            except (TypeError, ValueError):
                age_days = 0.0
        examples.append(
            {
                "rerank_score": float(row.get("rerank_score") or 0.0),
                "source_reliability_score": float(reliability_scores.get(doc_id) or 0.5),
                "rank_position": float(row.get("rank_position") or 1),
                "source_document_age_days": age_days,
                "outcome_helpful": bool(row.get("outcome_helpful")),
            }
        )
    return examples


async def count_training_examples(org_id: str, client: Any) -> int:
    result = (
        client.table("rag_chunk_outcomes")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .not_.is_("outcome_helpful", "null")
        .execute()
    )
    return int(getattr(result, "count", None) or 0)


async def get_weight_for_org(org_id: str, settings: Any, client: Any) -> float:
    """Return learned reliability weight for org, or v5 fixed constant."""
    try:
        registry = get_model_registry()
        models = await registry.list_models(org_id=org_id, model_type=ModelType.CLASSIFIER)
        ranker_model = next((m for m in models if m.name == RETRIEVAL_RANKER_MODEL_NAME), None)
        if not ranker_model or not ranker_model.deployed_version:
            return RELIABILITY_WEIGHT
        artifact = await registry.load_model_artifact(ranker_model.id, ranker_model.deployed_version)
        ranker = RetrievalRanker()
        ranker.load(artifact)
        weight = ranker.get_learned_weight()
        if weight is not None:
            return clip_reliability_weight(weight)
    except Exception as exc:  # noqa: BLE001
        logger.debug("retrieval_ranker_load_fallback org_id=%s error=%s", org_id, exc)
    return RELIABILITY_WEIGHT
