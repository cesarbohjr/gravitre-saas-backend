"""Traditional ML classifiers using sklearn and XGBoost."""
from __future__ import annotations

import pickle
from typing import Any, Literal

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.core.logging import get_logger
from app.ml.base import BaseMLModel, ModelMetrics, ModelType

logger = get_logger(__name__)

ClassifierType = Literal["logistic", "random_forest", "gradient_boosting", "xgboost"]


class SklearnClassifier(BaseMLModel):
    """Wrapper for sklearn classifiers."""

    model_type = ModelType.CLASSIFIER

    def __init__(
        self,
        classifier_type: ClassifierType = "random_forest",
        hyperparameters: dict[str, Any] | None = None,
    ):
        self.classifier_type = classifier_type
        self.hyperparameters = hyperparameters or {}
        self.model = None
        self.label_encoder = LabelEncoder()
        self.scaler = StandardScaler()
        self.feature_names: list[str] = []
        self._classes: list[str] = []

    def _create_model(self):
        if self.classifier_type == "logistic":
            return LogisticRegression(max_iter=1000, class_weight="balanced", **self.hyperparameters)
        if self.classifier_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=self.hyperparameters.get("n_estimators", 100),
                max_depth=self.hyperparameters.get("max_depth", 10),
                class_weight="balanced",
                n_jobs=-1,
                random_state=42,
                **{k: v for k, v in self.hyperparameters.items() if k not in ["n_estimators", "max_depth"]},
            )
        if self.classifier_type == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=self.hyperparameters.get("n_estimators", 100),
                max_depth=self.hyperparameters.get("max_depth", 5),
                learning_rate=self.hyperparameters.get("learning_rate", 0.1),
                random_state=42,
                **{
                    k: v
                    for k, v in self.hyperparameters.items()
                    if k not in ["n_estimators", "max_depth", "learning_rate"]
                },
            )
        if self.classifier_type == "xgboost":
            try:
                from xgboost import XGBClassifier

                return XGBClassifier(
                    n_estimators=self.hyperparameters.get("n_estimators", 100),
                    max_depth=self.hyperparameters.get("max_depth", 6),
                    learning_rate=self.hyperparameters.get("learning_rate", 0.1),
                    use_label_encoder=False,
                    eval_metric="mlogloss",
                    n_jobs=-1,
                    random_state=42,
                    **{
                        k: v
                        for k, v in self.hyperparameters.items()
                        if k not in ["n_estimators", "max_depth", "learning_rate"]
                    },
                )
            except ImportError:
                logger.warning("XGBoost not installed, falling back to GradientBoosting")
                self.classifier_type = "gradient_boosting"
                return self._create_model()
        raise ValueError(f"Unknown classifier type: {self.classifier_type}")

    async def train(
        self,
        X: np.ndarray | list[dict],
        y: np.ndarray | list[str],
        feature_names: list[str] | None = None,
        validation_split: float = 0.2,
        **kwargs: Any,
    ) -> ModelMetrics:
        import time

        start_time = time.time()
        if isinstance(X, list) and X and isinstance(X[0], dict):
            feature_names = feature_names or list(X[0].keys())
            X = np.array([[row.get(f, 0) for f in feature_names] for row in X])

        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        y_encoded = self.label_encoder.fit_transform(y)
        self._classes = list(self.label_encoder.classes_)
        X_scaled = self.scaler.fit_transform(X)

        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y_encoded, test_size=validation_split, random_state=42, stratify=y_encoded
        )
        self.model = self._create_model()
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_val)
        y_pred_proba = self.model.predict_proba(X_val) if hasattr(self.model, "predict_proba") else None
        cv_scores = cross_val_score(self.model, X_scaled, y_encoded, cv=5)
        is_multiclass = len(self._classes) > 2
        average = "weighted" if is_multiclass else "binary"

        metrics = ModelMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred, average=average, zero_division=0),
            recall=recall_score(y_val, y_pred, average=average, zero_division=0),
            f1_score=f1_score(y_val, y_pred, average=average, zero_division=0),
            confusion_matrix=confusion_matrix(y_val, y_pred).tolist(),
            classification_report=classification_report(y_val, y_pred, output_dict=True),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            training_duration_seconds=time.time() - start_time,
            custom_metrics={"cv_mean": float(cv_scores.mean()), "cv_std": float(cv_scores.std())},
        )
        if not is_multiclass and y_pred_proba is not None:
            metrics.auc_roc = roc_auc_score(y_val, y_pred_proba[:, 1])

        logger.info(
            "classifier_trained type=%s accuracy=%.4f f1=%.4f samples=%s",
            self.classifier_type,
            metrics.accuracy or 0.0,
            metrics.f1_score or 0.0,
            metrics.training_samples or 0,
        )
        return metrics

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        if self.model is None:
            raise ValueError("Model not trained")
        if isinstance(X, list) and X and isinstance(X[0], dict):
            X = np.array([[row.get(f, 0) for f in self.feature_names] for row in X])
        X_scaled = self.scaler.transform(X)
        y_pred_encoded = self.model.predict(X_scaled)
        predictions = self.label_encoder.inverse_transform(y_pred_encoded).tolist()
        probabilities = None
        if return_probabilities and hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(X_scaled)
            probabilities = [{cls: float(p) for cls, p in zip(self._classes, row)} for row in proba]
        return predictions, probabilities

    def save(self) -> bytes:
        return pickle.dumps(
            {
                "classifier_type": self.classifier_type,
                "hyperparameters": self.hyperparameters,
                "model": self.model,
                "label_encoder": self.label_encoder,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "_classes": self._classes,
            }
        )

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        self.classifier_type = loaded["classifier_type"]
        self.hyperparameters = loaded["hyperparameters"]
        self.model = loaded["model"]
        self.label_encoder = loaded["label_encoder"]
        self.scaler = loaded["scaler"]
        self.feature_names = loaded["feature_names"]
        self._classes = loaded["_classes"]

    def get_feature_importance(self) -> dict[str, float] | None:
        if self.model is None:
            return None
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        elif hasattr(self.model, "coef_"):
            importances = (
                np.abs(self.model.coef_).mean(axis=0) if self.model.coef_.ndim > 1 else np.abs(self.model.coef_)
            )
        else:
            return None
        return {
            name: float(imp)
            for name, imp in sorted(zip(self.feature_names, importances), key=lambda x: x[1], reverse=True)
        }


class IntentClassifier(SklearnClassifier):
    """Specialized classifier for intent detection in workflows."""

    def __init__(self, **kwargs: Any):
        super().__init__(classifier_type="random_forest", **kwargs)
        self.vectorizer = None

    async def train_from_text(self, texts: list[str], labels: list[str], **kwargs: Any) -> ModelMetrics:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), stop_words="english")
        X = self.vectorizer.fit_transform(texts).toarray()
        self.feature_names = self.vectorizer.get_feature_names_out().tolist()
        return await self.train(X, labels, **kwargs)

    async def predict_text(
        self, texts: list[str], return_probabilities: bool = False
    ) -> tuple[list[str], list[dict[str, float]] | None]:
        if self.vectorizer is None:
            raise ValueError("Model not trained with text data")
        X = self.vectorizer.transform(texts).toarray()
        return await self.predict(X, return_probabilities)

    def save(self) -> bytes:
        return pickle.dumps({"parent": super().save(), "vectorizer": self.vectorizer})

    def load(self, data: bytes) -> None:
        loaded = pickle.loads(data)
        super().load(loaded["parent"])
        self.vectorizer = loaded["vectorizer"]


_classifier_cache: dict[str, SklearnClassifier] = {}


def get_classifier(
    classifier_type: ClassifierType = "random_forest",
    hyperparameters: dict[str, Any] | None = None,
) -> SklearnClassifier:
    """Get or create a classifier instance."""
    key = f"{classifier_type}_{hash(str(hyperparameters))}"
    if key not in _classifier_cache:
        _classifier_cache[key] = SklearnClassifier(classifier_type, hyperparameters)
    return _classifier_cache[key]
