"""Wave D3 — meta-learning service tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.meta_learning_service import MetaLearningService


def _settings(**overrides: object) -> MagicMock:
    base = MagicMock(app_env="dev", domain_adaptive_learning_enabled=True)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.asyncio
async def test_meta_learning_org_isolation():
    svc = MetaLearningService(settings=_settings())
    org_a = {"meta_learning_state": {"model": {"llm:standard": {"wins": 20, "losses": 2, "samples": 22, "win_rate": 0.9}}}}
    org_b = {"meta_learning_state": {"model": {"llm:fast": {"wins": 5, "losses": 15, "samples": 20, "win_rate": 0.25}}}}

    async def load_side_effect(org_id: str, segment_key: str) -> dict:
        return org_a if org_id == "org-a" else org_b

    with patch.object(svc, "_load_segment_state", side_effect=load_side_effect):
        with patch.object(svc, "_ledger") as ledger:
            ledger.get_strategy_stats = AsyncMock(return_value={"decided_samples": 0, "wins": 0, "losses": 0})
            guidance_a = await svc.get_selection_guidance(
                "org-a",
                "default:marketing:seo:qa",
                "model",
                ["llm:standard", "llm:fast"],
                default_key="llm:standard",
            )
            guidance_b = await svc.get_selection_guidance(
                "org-b",
                "default:marketing:seo:qa",
                "model",
                ["llm:standard", "llm:fast"],
                default_key="llm:fast",
            )
    assert guidance_a.get("recommended_key") != guidance_b.get("recommended_key") or guidance_a != guidance_b


@pytest.mark.asyncio
async def test_meta_learning_segment_isolation():
    svc = MetaLearningService(settings=_settings())

    async def load_side_effect(org_id: str, segment_key: str) -> dict:
        if "marketing" in segment_key:
            return {
                "meta_learning_state": {
                    "agent": {"agent:MARKETING": {"wins": 18, "losses": 2, "samples": 20, "win_rate": 0.9}}
                }
            }
        return {
            "meta_learning_state": {
                "agent": {"agent:SALES": {"wins": 16, "losses": 4, "samples": 20, "win_rate": 0.8}}
            }
        }

    with patch.object(svc, "_load_segment_state", side_effect=load_side_effect):
        with patch.object(svc, "_ledger") as ledger:
            ledger.get_strategy_stats = AsyncMock(return_value={"decided_samples": 0, "wins": 0, "losses": 0})
            marketing = await svc.get_best_strategy_for_segment(
                "org-1",
                "default:marketing:seo:qa",
                "agent",
                ["agent:MARKETING", "agent:SALES"],
                default_key="agent:MARKETING",
            )
            sales = await svc.get_best_strategy_for_segment(
                "org-1",
                "default:sales:forecasting:qa",
                "agent",
                ["agent:MARKETING", "agent:SALES"],
                default_key="agent:SALES",
            )
    assert marketing["best_strategy"] == "agent:MARKETING"
    assert sales["best_strategy"] == "agent:SALES"


@pytest.mark.asyncio
async def test_meta_learning_insufficient_data():
    svc = MetaLearningService(settings=_settings())
    with patch.object(svc, "_load_segment_state", return_value={"meta_learning_state": {}}):
        with patch.object(svc, "_ledger") as ledger:
            ledger.get_strategy_stats = AsyncMock(return_value={"decided_samples": 2, "wins": 1, "losses": 1})
            result = await svc.recommend_strategy(
                "org-1",
                "default:marketing:seo:qa",
                "model",
                ["llm:standard", "llm:fast"],
                default_key="llm:standard",
            )
    assert result["status"] == "insufficient_data"
    assert result["soft_priors"]["llm:standard"] == 1.0


@pytest.mark.asyncio
async def test_meta_learning_weighted_guidance_produces_soft_priors():
    svc = MetaLearningService(settings=_settings())
    state = {
        "meta_learning_state": {
            "model": {
                "llm:standard": {"wins": 30, "losses": 5, "samples": 35, "win_rate": 0.8571},
                "llm:fast": {"wins": 8, "losses": 12, "samples": 20, "win_rate": 0.4},
            }
        }
    }
    with patch.object(svc, "_load_segment_state", return_value=state):
        with patch.object(svc, "_ledger") as ledger:
            ledger.get_strategy_stats = AsyncMock(
                side_effect=lambda org, key, **kwargs: {
                    "llm:standard": {"decided_samples": 35, "wins": 30, "losses": 5, "win_rate": 0.8571},
                    "llm:fast": {"decided_samples": 20, "wins": 8, "losses": 12, "win_rate": 0.4},
                }.get(key, {"decided_samples": 0})
            )
            guidance = await svc.get_selection_guidance(
                "org-1",
                "default:marketing:seo:qa",
                "model",
                ["llm:standard", "llm:fast"],
                default_key="llm:fast",
            )
    assert guidance["status"] == "guidance"
    assert guidance["hard_override"] is False
    assert guidance["soft_priors"]["llm:standard"] > guidance["soft_priors"]["llm:fast"]


def test_meta_learning_no_hard_override_when_ledger_won():
    svc = MetaLearningService(settings=_settings())
    selection = {"llm_tier": "reasoning", "primary_model": "llm"}
    guidance = {
        "status": "guidance",
        "recommended_key": "llm:fast",
        "guidance_strength": 0.25,
        "hard_override": False,
    }
    updated = svc.apply_model_soft_prior(selection, guidance, ledger_reason="ledger_win_rate")
    assert updated["llm_tier"] == "reasoning"
    assert updated["meta_learning_applied"] is False


def test_meta_learning_agent_never_replaces_persona():
    svc = MetaLearningService(settings=_settings())
    selection = {"persona_key": "DEFAULT"}
    guidance = {
        "status": "guidance",
        "recommended_key": "agent:MARKETING",
        "guidance_strength": 0.25,
    }
    updated = svc.apply_agent_soft_prior(selection, guidance)
    assert updated["persona_key"] == "DEFAULT"
    assert updated["meta_learning_applied"] is False


def test_meta_learning_disabled_returns_disabled():
    svc = MetaLearningService(settings=_settings(domain_adaptive_learning_enabled=False))
    assert svc.is_enabled() is False


@pytest.mark.asyncio
async def test_record_strategy_outcome_persists_meta_state():
    svc = MetaLearningService(settings=_settings())
    with patch.object(svc, "_load_segment_state", return_value={"meta_learning_state": {}}):
        with patch.object(svc, "_persist_meta_state", new_callable=AsyncMock) as persist:
            with patch.object(svc, "_ledger") as ledger:
                ledger.record = AsyncMock()
                result = await svc.record_strategy_outcome(
                    "org-1",
                    "default:marketing:seo:qa",
                    "model",
                    "llm:standard",
                    "positive",
                )
    assert result["status"] == "recorded"
    persist.assert_called_once()
