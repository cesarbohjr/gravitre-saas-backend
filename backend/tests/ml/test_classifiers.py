from __future__ import annotations

import numpy as np
import pytest

from app.ml.classifiers import IntentClassifier, SklearnClassifier


@pytest.mark.asyncio
async def test_sklearn_classifier_train_predict_and_reload():
    X = [
        {"amount": 10, "errors": 0, "retries": 0},
        {"amount": 20, "errors": 1, "retries": 1},
        {"amount": 11, "errors": 0, "retries": 0},
        {"amount": 30, "errors": 2, "retries": 1},
        {"amount": 9, "errors": 0, "retries": 0},
        {"amount": 26, "errors": 1, "retries": 1},
        {"amount": 8, "errors": 0, "retries": 0},
        {"amount": 28, "errors": 2, "retries": 2},
        {"amount": 7, "errors": 0, "retries": 0},
        {"amount": 24, "errors": 1, "retries": 1},
    ]
    y = ["safe", "risk", "safe", "risk", "safe", "risk", "safe", "risk", "safe", "risk"]

    clf = SklearnClassifier(classifier_type="random_forest")
    metrics = await clf.train(X, y)
    assert metrics.training_samples is not None

    predictions, probs = await clf.predict([{"amount": 12, "errors": 0, "retries": 0}], return_probabilities=True)
    assert len(predictions) == 1
    assert probs is not None and len(probs) == 1

    blob = clf.save()
    loaded = SklearnClassifier()
    loaded.load(blob)
    predictions2, _ = await loaded.predict([{"amount": 12, "errors": 0, "retries": 0}])
    assert len(predictions2) == 1


@pytest.mark.asyncio
async def test_intent_classifier_train_and_predict_text():
    texts = [
        "run billing reconciliation",
        "sync stripe invoices",
        "reconcile billing ledger",
        "close monthly billing",
        "create invoice billing summary",
        "summarize weekly incidents",
        "generate incident report",
        "publish reporting dashboard",
        "summarize incident trends",
        "write weekly operations report",
        "retry failed connector",
        "fix connector retry workflow",
        "replay failed webhook task",
        "repair automation retries",
        "resolve connector timeout",
    ]
    labels = [
        "billing",
        "billing",
        "billing",
        "billing",
        "billing",
        "reporting",
        "reporting",
        "reporting",
        "reporting",
        "reporting",
        "operations",
        "operations",
        "operations",
        "operations",
        "operations",
    ]

    model = IntentClassifier()
    metrics = await model.train_from_text(texts, labels, validation_split=0.2)
    assert metrics.accuracy is not None

    preds, probs = await model.predict_text(["create billing report"], return_probabilities=True)
    assert len(preds) == 1
    assert probs is not None
