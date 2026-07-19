"""CF matrix factorization — train, score, blend, STA-314."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from app.ml.cf_matrix_factorization import CfMatrixFactorizer, MIN_INTERACTIONS
from app.ml.cf_soft_rank import soft_rank_cards
from app.services.cf_rank_service import soft_rank_heuristic_payload
from app.services.recommendation_heuristics_service import (
    assert_no_execute_surface,
    build_heuristic_recommendations,
)


def _synthetic_interactions(n: int = 60) -> list[dict]:
    rows: list[dict] = []
    actors = ["u1", "u2", "u3", "org:smoke"]
    items = [
        "connector:hubspot",
        "connector:slack",
        "connector:zendesk",
        "card:unused-hubspot",
        "card:unused-slack",
    ]
    for i in range(n):
        actor = actors[i % len(actors)]
        item = items[i % len(items)]
        # Bias hubspot positive for u1/u2
        weight = 2.0 if "hubspot" in item and actor in {"u1", "u2"} else 0.5
        if "slack" in item and actor == "u3":
            weight = 2.5
        rows.append({"actor_id": actor, "item_key": item, "weight": weight, "source": "test"})
    return rows


def test_train_and_score_items():
    model = CfMatrixFactorizer()
    metrics = asyncio.run(model.train(interactions=_synthetic_interactions(60)))
    assert model.is_trained
    assert int(metrics.custom_metrics["n_users"]) >= 2
    assert int(metrics.custom_metrics["n_items"]) >= 3
    scores = model.score_items(actor_id="u1", item_keys=["connector:hubspot", "connector:slack"])
    assert "connector:hubspot" in scores
    assert "connector:slack" in scores


def test_save_load_roundtrip():
    model = CfMatrixFactorizer()
    asyncio.run(model.train(interactions=_synthetic_interactions(60)))
    blob = model.save()
    loaded = CfMatrixFactorizer()
    loaded.load(blob)
    assert loaded.is_trained
    a = model.score_items(actor_id="u1", item_keys=["connector:hubspot"])
    b = loaded.score_items(actor_id="u1", item_keys=["connector:hubspot"])
    assert abs(a["connector:hubspot"] - b["connector:hubspot"]) < 1e-6


def test_train_rejects_sparse_matrix():
    model = CfMatrixFactorizer()
    with pytest.raises(ValueError, match="interactions"):
        asyncio.run(model.train(interactions=_synthetic_interactions(10)))


def test_soft_rank_blends_mf_scores():
    cards = [
        {"id": "unused-slack", "evidence": {"vendor": "slack"}},
        {"id": "unused-hubspot", "evidence": {"vendor": "hubspot"}},
    ]
    affinity = {"connector:slack": 10.0, "connector:hubspot": 1.0}
    mf = {"connector:hubspot": 20.0, "connector:slack": 0.0}
    ranked = soft_rank_cards(cards, affinity, mf_scores=mf, method="matrix_factorization")
    assert ranked[0]["id"] == "unused-hubspot"
    assert ranked[0]["cf_method"] == "matrix_factorization"
    assert len(ranked) == 2


def test_rank_service_uses_injected_factorizer(monkeypatch):
    payload = build_heuristic_recommendations(
        connected_connectors=[
            {"vendor": "slack", "label": "Slack", "status": "connected", "executable": True},
            {"vendor": "hubspot", "label": "HubSpot", "status": "connected", "executable": True},
        ],
        usage_by_connector={},
        installed_packs=set(),
    )
    factorizer = CfMatrixFactorizer()
    asyncio.run(factorizer.train(interactions=_synthetic_interactions(60)))

    monkeypatch.setattr(
        "app.services.cf_rank_service.training_gate_status",
        lambda *a, **k: {
            "ready": True,
            "cold_start": False,
            "current": 60,
            "required": 50,
            "advisory_only": True,
            "matrix_factorization": {"ready": True},
        },
    )
    monkeypatch.setattr(
        "app.services.cf_rank_service.load_scored_interactions",
        lambda *a, **k: _synthetic_interactions(60),
    )
    out = soft_rank_heuristic_payload(
        MagicMock(),
        "org-1",
        payload,
        actor_id="u1",
        factorizer=factorizer,
    )
    assert out["cfRanked"] is True
    assert out["cfMethod"] == "matrix_factorization"
    assert_no_execute_surface(out)


def test_insufficient_interactions_constant():
    assert MIN_INTERACTIONS == 50
