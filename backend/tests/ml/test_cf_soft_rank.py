"""CF v1 soft-rank — gate, cold start, never-drop, STA-314 no-execute."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ml.cf_interaction_ingest import (
    MIN_SCORED_INTERACTIONS_30D,
    item_affinity_scores,
    training_gate_status,
)
from app.ml.cf_soft_rank import card_item_keys, soft_rank_cards
from app.services.cf_rank_service import soft_rank_heuristic_payload
from app.services.recommendation_heuristics_service import (
    assert_no_execute_surface,
    build_heuristic_recommendations,
)


def test_card_item_keys_from_unused_and_pack():
    unused = {"id": "unused-hubspot", "evidence": {"vendor": "hubspot"}}
    pack = {
        "id": "pack-hubspot-sales-ops",
        "evidence": {"vendor": "hubspot", "suggestedPackId": "sales-ops"},
    }
    assert "card:unused-hubspot" in card_item_keys(unused)
    assert "connector:hubspot" in card_item_keys(unused)
    keys = card_item_keys(pack)
    assert "pack:sales-ops" in keys
    assert "connector:hubspot" in keys


def test_soft_rank_reorders_without_dropping():
    cards = [
        {"id": "unused-slack", "evidence": {"vendor": "slack"}, "priority": 70},
        {"id": "unused-hubspot", "evidence": {"vendor": "hubspot"}, "priority": 70},
        {"id": "nonexec-zendesk", "evidence": {"vendor": "zendesk"}, "priority": 95},
    ]
    affinity = {
        "connector:hubspot": 10.0,
        "card:unused-hubspot": 5.0,
        "connector:slack": 1.0,
    }
    ranked = soft_rank_cards(cards, affinity)
    assert [c["id"] for c in ranked] == [
        "unused-hubspot",
        "unused-slack",
        "nonexec-zendesk",
    ]
    assert len(ranked) == 3
    assert ranked[0]["cf_score"] >= ranked[1]["cf_score"]


def test_gate_cold_start_and_ready():
    client = MagicMock()

    def _fake_load(client_arg, org_id, *, lookback_days=30):
        return [{"item_key": "connector:hubspot", "weight": 1.0}] * 10

    import app.ml.cf_interaction_ingest as ingest

    original = ingest.load_scored_interactions
    ingest.load_scored_interactions = _fake_load  # type: ignore[assignment]
    try:
        gate = training_gate_status(client, "org-1")
        assert gate["ready"] is False
        assert gate["cold_start"] is True
        assert gate["required"] == MIN_SCORED_INTERACTIONS_30D
    finally:
        ingest.load_scored_interactions = original  # type: ignore[assignment]

    def _fake_ready(client_arg, org_id, *, lookback_days=30):
        return [{"item_key": "connector:hubspot", "weight": 1.0}] * MIN_SCORED_INTERACTIONS_30D

    ingest.load_scored_interactions = _fake_ready  # type: ignore[assignment]
    try:
        gate = training_gate_status(client, "org-1")
        assert gate["ready"] is True
        assert gate["cold_start"] is False
    finally:
        ingest.load_scored_interactions = original  # type: ignore[assignment]


def test_soft_rank_payload_cold_start_preserves_order(monkeypatch):
    payload = build_heuristic_recommendations(
        connected_connectors=[
            {"vendor": "slack", "label": "Slack", "status": "connected", "executable": True},
            {"vendor": "hubspot", "label": "HubSpot", "status": "connected", "executable": True},
        ],
        usage_by_connector={},
        installed_packs=set(),
    )
    original_ids = [c["id"] for c in payload["recommendations"]]

    monkeypatch.setattr(
        "app.services.cf_rank_service.training_gate_status",
        lambda *a, **k: {
            "ready": False,
            "cold_start": True,
            "current": 0,
            "required": 50,
            "advisory_only": True,
        },
    )
    out = soft_rank_heuristic_payload(MagicMock(), "org-1", payload)
    assert out["cfRanked"] is False
    assert [c["id"] for c in out["recommendations"]] == original_ids
    assert_no_execute_surface(out)


def test_soft_rank_payload_ready_reorders(monkeypatch):
    payload = build_heuristic_recommendations(
        connected_connectors=[
            {"vendor": "slack", "label": "Slack", "status": "connected", "executable": True},
            {"vendor": "hubspot", "label": "HubSpot", "status": "connected", "executable": True},
        ],
        usage_by_connector={},
        installed_packs=set(),
    )
    monkeypatch.setattr(
        "app.services.cf_rank_service.training_gate_status",
        lambda *a, **k: {
            "ready": True,
            "cold_start": False,
            "current": 50,
            "required": 50,
            "advisory_only": True,
        },
    )
    monkeypatch.setattr(
        "app.services.cf_rank_service.load_scored_interactions",
        lambda *a, **k: [
            {"item_key": "connector:hubspot", "weight": 8.0},
            {"item_key": "card:unused-hubspot", "weight": 4.0},
            {"item_key": "connector:slack", "weight": 0.5},
        ],
    )
    out = soft_rank_heuristic_payload(MagicMock(), "org-1", payload)
    assert out["cfRanked"] is True
    ids = [c["id"] for c in out["recommendations"]]
    assert ids[0] == "unused-hubspot"
    assert set(ids) == {"unused-hubspot", "unused-slack"}
    assert_no_execute_surface(out)
    with pytest.raises(AssertionError):
        soft_rank_heuristic_payload(
            MagicMock(),
            "org-1",
            {"recommendations": [{"id": "x", "toolName": "bad"}]},
        )


def test_item_affinity_scores_sum():
    scores = item_affinity_scores(
        [
            {"item_key": "connector:hubspot", "weight": 1.0},
            {"item_key": "connector:hubspot", "weight": 2.0},
            {"item_key": "card:unused-slack", "weight": -1.5},
        ]
    )
    assert scores["connector:hubspot"] == 3.0
    assert scores["card:unused-slack"] == -1.5


def test_router_applies_cf_before_dismiss():
    """Source-order guard: CF soft-rank call appears before dismiss filter."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "routers"
        / "intelligence_engine.py"
    ).read_text(encoding="utf-8")
    handler = text.split("async def intelligence_heuristic_recommendations", 1)[1]
    handler = handler.split("async def intelligence_heuristic_dismiss", 1)[0]
    cf_idx = handler.find("soft_rank_heuristic_payload")
    dismiss_idx = handler.find("filter_dismissed_recommendations(")
    assert cf_idx > 0
    assert dismiss_idx > 0
    assert cf_idx < dismiss_idx
