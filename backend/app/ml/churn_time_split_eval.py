"""Time-split comparison: entity-feature churn model vs the 5-feature baseline.

Both models are fitted on the same earlier window and scored on the same later
window (``app.ml.splits.time_split``). The report carries AUC and precision@k
for each. The decision itself is made by the existing champion gate
(``intelligence_training.champion_challenger_decision``), which calls
``baseline_gate_refusal`` on the flat ``bg_*`` fields this module writes into
``ModelMetrics.custom_metrics``: the challenger is refused unless it has at
least ``MIN_LABELLED_SAMPLES`` labels and beats the baseline AUC by
``AUC_MARGIN`` without losing precision@k.

Nothing here claims an improvement; it only measures one on a given split.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, roc_auc_score

from app.ml.base import ModelMetrics
from app.ml.churn_scoring import FEATURE_KEYS, ChurnRiskScorer
from app.ml.splits import time_split

MIN_LABELLED_SAMPLES = 60
AUC_MARGIN = 0.02
TOP_K_FRACTION = 0.2

REFUSE_INSUFFICIENT = "not_deployed_insufficient_labelled_samples"
REFUSE_NO_COMPARISON = "not_deployed_no_baseline_comparison"
REFUSE_MARGIN = "not_deployed_did_not_beat_baseline_by_margin"
REFUSE_PRECISION = "not_deployed_precision_at_k_below_baseline"


def precision_at_k(y_true: list[int] | np.ndarray, scores: list[float] | np.ndarray, k: int) -> float | None:
    """Share of churners among the k highest-scored holdout customers."""
    y = np.asarray(y_true)
    s = np.asarray(scores, dtype=float)
    if k <= 0 or len(y) == 0:
        return None
    k = min(k, len(y))
    top = np.argsort(-s, kind="stable")[:k]
    return float(y[top].sum()) / k


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def baseline_gate_refusal(custom: dict[str, Any] | None) -> str | None:
    """Reason to refuse a challenger that carries a baseline comparison, or None.

    Re-checks the numbers rather than trusting a stored verdict. Metrics without
    ``bg_compared`` are not baseline-gated (every other trainer).
    """
    c = custom or {}
    if "bg_compared" not in c:
        return None
    labelled = _num(c.get("bg_labelled_samples")) or 0
    required = _num(c.get("bg_min_labelled_samples"))
    required = MIN_LABELLED_SAMPLES if required is None else max(required, MIN_LABELLED_SAMPLES)
    if labelled < required:
        return REFUSE_INSUFFICIENT
    if c.get("bg_compared") is not True:
        return REFUSE_NO_COMPARISON
    base_auc = _num(c.get("bg_baseline_auc_roc"))
    new_auc = _num(c.get("bg_challenger_auc_roc"))
    margin = _num(c.get("bg_auc_margin"))
    margin = AUC_MARGIN if margin is None else max(margin, AUC_MARGIN)
    if base_auc is None or new_auc is None:
        return REFUSE_NO_COMPARISON
    if new_auc - base_auc < margin - 1e-12:
        return REFUSE_MARGIN
    base_p = _num(c.get("bg_baseline_precision_at_k"))
    new_p = _num(c.get("bg_challenger_precision_at_k"))
    if base_p is not None and (new_p is None or new_p < base_p):
        return REFUSE_PRECISION
    return None


def evaluate_entity_challenger(
    rows: list[dict[str, Any]],
    labels: list[int],
    observed_at: list[Any],
    *,
    entity_keys: tuple[str, ...] | list[str],
    min_labelled: int = MIN_LABELLED_SAMPLES,
    auc_margin: float = AUC_MARGIN,
) -> tuple[dict[str, Any], ChurnRiskScorer | None, ModelMetrics | None]:
    """Fit baseline and challenger on one time split; return report, challenger, metrics.

    ``rows`` hold the 5 CRM features plus the entity features (None = missing).
    Returns ``(report, None, None)`` when no time split is possible, so the
    caller keeps the existing baseline path.
    """
    report: dict[str, Any] = {
        "labelled": len(rows),
        "min_labelled": int(min_labelled),
        "auc_margin": float(auc_margin),
        "split": "time",
    }
    split = time_split(list(observed_at), list(labels))
    if split is None:
        report["reason"] = "time_split_unavailable"
        return report, None, None
    train_idx, hold_idx, holdout_from = split
    y = np.array([1 if v else 0 for v in labels])
    k = max(1, math.ceil(len(hold_idx) * TOP_K_FRACTION))
    results: dict[str, dict[str, Any]] = {}
    fitted: dict[str, ChurnRiskScorer] = {}
    for name, keys in (("baseline", list(FEATURE_KEYS)), ("challenger", list(FEATURE_KEYS) + list(entity_keys))):
        scorer = ChurnRiskScorer(feature_names=keys)
        matrix = scorer._vectorize(rows)
        scorer._fit(matrix[train_idx], y[train_idx])
        proba = scorer._model.predict_proba(matrix[hold_idx])[:, 1]  # type: ignore[union-attr]
        y_hold = y[hold_idx]
        results[name] = {
            "auc_roc": float(roc_auc_score(y_hold, proba)) if len(set(y_hold.tolist())) > 1 else None,
            "precision_at_k": precision_at_k(y_hold, proba, k),
            "accuracy": float(accuracy_score(y_hold, (proba >= 0.5).astype(int))),
        }
        fitted[name] = scorer
    report.update(
        {
            "holdout_from": holdout_from,
            "train_samples": len(train_idx),
            "holdout_samples": len(hold_idx),
            "k": k,
            "baseline": results["baseline"],
            "challenger": results["challenger"],
        }
    )
    custom: dict[str, Any] = {
        "split": "time",
        "holdout_from": holdout_from,
        "feature_set": "crm_plus_entity",
        "bg_compared": True,
        "bg_labelled_samples": len(rows),
        "bg_min_labelled_samples": int(min_labelled),
        "bg_auc_margin": float(auc_margin),
        "bg_k": k,
        "bg_baseline_auc_roc": results["baseline"]["auc_roc"],
        "bg_challenger_auc_roc": results["challenger"]["auc_roc"],
        "bg_baseline_precision_at_k": results["baseline"]["precision_at_k"],
        "bg_challenger_precision_at_k": results["challenger"]["precision_at_k"],
    }
    refusal = baseline_gate_refusal(custom)
    report["passes_baseline_gate"] = refusal is None
    report["reason"] = refusal or "beats_baseline_by_margin"
    metrics = ModelMetrics(
        accuracy=results["challenger"]["accuracy"],
        auc_roc=results["challenger"]["auc_roc"],
        training_samples=len(train_idx),
        validation_samples=len(hold_idx),
        custom_metrics=custom,
    )
    return report, fitted["challenger"], metrics
