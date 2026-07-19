"""CF matrix factorization — user × item latent factors (advisory soft-rank only).

Uses TruncatedSVD on the org interaction matrix (ALS-style latent factors).
Never auto-executes recommendations.
"""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from sklearn.decomposition import TruncatedSVD

from app.ml.base import BaseMLModel, ModelMetrics, ModelStatus, ModelType

MIN_INTERACTIONS = 50
MIN_USERS = 2
MIN_ITEMS = 3
DEFAULT_N_COMPONENTS = 8
ORG_ACTOR_PREFIX = "org:"


class CfMatrixFactorizer(BaseMLModel):
    """Latent-factor recommender for heuristic card soft-rank."""

    model_type = ModelType.EMBEDDING
    catalog_status = ModelStatus.TRAINED
    advisory_only = True
    MIN_TRAINING_EXAMPLES = MIN_INTERACTIONS

    def __init__(self) -> None:
        self._user_index: dict[str, int] = {}
        self._item_index: dict[str, int] = {}
        self._user_ids: list[str] = []
        self._item_ids: list[str] = []
        self._user_factors: np.ndarray | None = None
        self._item_factors: np.ndarray | None = None
        self._item_bias: np.ndarray | None = None
        self._global_mean: float = 0.0
        self._n_components: int = DEFAULT_N_COMPONENTS
        self._trained: bool = False

    @property
    def is_trained(self) -> bool:
        return bool(self._trained and self._item_factors is not None)

    def build_matrix(
        self,
        interactions: list[dict[str, Any]],
    ) -> tuple[np.ndarray, list[str], list[str]]:
        """Aggregate interactions into dense user×item rating matrix."""
        users: dict[str, int] = {}
        items: dict[str, int] = {}
        triples: list[tuple[str, str, float]] = []
        for row in interactions:
            actor = str(row.get("actor_id") or row.get("user_id") or "").strip()
            item = str(row.get("item_key") or "").strip()
            if not actor or not item:
                continue
            weight = float(row.get("weight") or 0.0)
            if actor not in users:
                users[actor] = len(users)
            if item not in items:
                items[item] = len(items)
            triples.append((actor, item, weight))

        user_ids = [""] * len(users)
        for uid, idx in users.items():
            user_ids[idx] = uid
        item_ids = [""] * len(items)
        for iid, idx in items.items():
            item_ids[idx] = iid

        matrix = np.zeros((len(user_ids), len(item_ids)), dtype=np.float64)
        for actor, item, weight in triples:
            matrix[users[actor], items[item]] += weight
        return matrix, user_ids, item_ids

    async def train(
        self,
        X: np.ndarray | list[dict] | None = None,
        y: Any = None,
        *,
        interactions: list[dict[str, Any]] | None = None,
        n_components: int = DEFAULT_N_COMPONENTS,
        **kwargs: Any,
    ) -> ModelMetrics:
        _ = y, kwargs
        rows = interactions or (list(X) if isinstance(X, list) else [])
        if len(rows) < MIN_INTERACTIONS:
            raise ValueError(f"Need at least {MIN_INTERACTIONS} interactions, got {len(rows)}")

        matrix, user_ids, item_ids = self.build_matrix(rows)
        if len(user_ids) < MIN_USERS:
            raise ValueError(f"Need at least {MIN_USERS} actors, got {len(user_ids)}")
        if len(item_ids) < MIN_ITEMS:
            raise ValueError(f"Need at least {MIN_ITEMS} items, got {len(item_ids)}")

        # Shift negatives into non-negative space for TruncatedSVD stability.
        shifted = matrix - matrix.min() if matrix.min() < 0 else matrix.copy()
        n_comp = int(max(2, min(n_components, len(user_ids) - 1, len(item_ids) - 1)))
        svd = TruncatedSVD(n_components=n_comp, random_state=42)
        user_factors = svd.fit_transform(shifted)
        item_factors = svd.components_.T  # items × k
        reconstructed = user_factors @ item_factors.T
        # Map reconstructed back relative to original scale via bias terms.
        item_bias = matrix.mean(axis=0)
        global_mean = float(matrix.mean()) if matrix.size else 0.0
        residual = matrix - reconstructed
        rmse = float(np.sqrt(np.mean(np.square(residual)))) if residual.size else 0.0

        self._user_ids = user_ids
        self._item_ids = item_ids
        self._user_index = {u: i for i, u in enumerate(user_ids)}
        self._item_index = {it: i for i, it in enumerate(item_ids)}
        self._user_factors = user_factors.astype(np.float64)
        self._item_factors = item_factors.astype(np.float64)
        self._item_bias = item_bias.astype(np.float64)
        self._global_mean = global_mean
        self._n_components = n_comp
        self._trained = True

        explained = float(getattr(svd, "explained_variance_ratio_", np.array([])).sum() or 0.0)
        return ModelMetrics(
            mse=rmse**2,
            mae=float(np.mean(np.abs(residual))) if residual.size else None,
            training_samples=len(rows),
            validation_samples=len(user_ids) * len(item_ids),
            custom_metrics={
                "n_users": len(user_ids),
                "n_items": len(item_ids),
                "n_components": n_comp,
                "rmse": rmse,
                "explained_variance": explained,
                "method": "truncated_svd",
                "advisory_only": True,
            },
        )

    def score_items(
        self,
        *,
        actor_id: str | None = None,
        org_id: str | None = None,
        item_keys: list[str] | None = None,
    ) -> dict[str, float]:
        """Score item keys for an actor (falls back to org mean user factors)."""
        if not self.is_trained or self._user_factors is None or self._item_factors is None:
            return {}

        user_vec = self._resolve_user_vector(actor_id=actor_id, org_id=org_id)
        if user_vec is None:
            return {}

        keys = item_keys or list(self._item_ids)
        scores: dict[str, float] = {}
        for key in keys:
            idx = self._item_index.get(key)
            if idx is None:
                continue
            item_vec = self._item_factors[idx]
            bias = float(self._item_bias[idx]) if self._item_bias is not None else 0.0
            scores[key] = float(np.dot(user_vec, item_vec) + bias + self._global_mean)
        return scores

    def _resolve_user_vector(
        self,
        *,
        actor_id: str | None,
        org_id: str | None,
    ) -> np.ndarray | None:
        assert self._user_factors is not None
        if actor_id and actor_id in self._user_index:
            return self._user_factors[self._user_index[actor_id]]
        if org_id:
            org_actor = f"{ORG_ACTOR_PREFIX}{org_id}"
            if org_actor in self._user_index:
                return self._user_factors[self._user_index[org_actor]]
        # Mean user latent vector (org-level collaborative prior).
        return self._user_factors.mean(axis=0)

    async def predict(
        self,
        X: np.ndarray | list[dict],
        return_probabilities: bool = False,
        **kwargs: Any,
    ) -> tuple[list[Any], list[dict[str, float]] | None]:
        _ = return_probabilities
        actor_id = kwargs.get("actor_id")
        org_id = kwargs.get("org_id")
        item_keys = None
        if isinstance(X, list) and X and isinstance(X[0], dict):
            item_keys = [str(r.get("item_key") or r.get("id") or "") for r in X]
        scores = self.score_items(actor_id=actor_id, org_id=org_id, item_keys=item_keys)
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [{"item_key": k, "score": v} for k, v in ordered], None

    def save(self) -> bytes:
        return pickle.dumps(
            {
                "user_ids": self._user_ids,
                "item_ids": self._item_ids,
                "user_factors": self._user_factors,
                "item_factors": self._item_factors,
                "item_bias": self._item_bias,
                "global_mean": self._global_mean,
                "n_components": self._n_components,
                "trained": self._trained,
            }
        )

    def load(self, data: bytes) -> None:
        payload = pickle.loads(data)
        self._user_ids = list(payload.get("user_ids") or [])
        self._item_ids = list(payload.get("item_ids") or [])
        self._user_index = {u: i for i, u in enumerate(self._user_ids)}
        self._item_index = {it: i for i, it in enumerate(self._item_ids)}
        self._user_factors = payload.get("user_factors")
        self._item_factors = payload.get("item_factors")
        self._item_bias = payload.get("item_bias")
        self._global_mean = float(payload.get("global_mean") or 0.0)
        self._n_components = int(payload.get("n_components") or DEFAULT_N_COMPONENTS)
        self._trained = bool(payload.get("trained"))
