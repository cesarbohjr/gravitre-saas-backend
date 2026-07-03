"""Empirical strategy performance ledger (meta-learning v1 / contextual bandit v1)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.model_catalog import GRAVITRE_ML_CATALOG
from app.ml.base import ModelStatus
from app.services.learning_strategy_keys import build_model_strategy_key
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

MIN_SAMPLES_FOR_PREFERENCE = 20
MIN_WIN_RATE_DELTA = 0.05
MIN_SAMPLES_FOR_UCB = 5


def _ucb_score(wins: int, losses: int, total_trials: int) -> float:
    decided = wins + losses
    if decided <= 0:
        return 0.0
    exploitation = wins / decided
    exploration = math.sqrt(2 * math.log(max(total_trials, 1)) / decided)
    return exploitation + exploration


class StrategyPerformanceLedger:
    """
    Records strategy outcomes for routing preferences.
    v1: empirical win-rate ranking (not neural RL — see outcome_attribution_service).
    """

    TABLE = "strategy_performance_records"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def record(
        self,
        org_id: str,
        strategy_key: str,
        outcome_polarity: str,
        *,
        strategy_family: str = "route",
        segment_key: str = "default",
        latency_ms: int | None = None,
        approval_required: bool | None = None,
        approval_granted: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if outcome_polarity not in {"win", "loss", "neutral"}:
            outcome_polarity = "neutral"
        row = {
            "id": str(uuid4()),
            "org_id": org_id,
            "strategy_key": strategy_key,
            "strategy_family": strategy_family,
            "segment_key": segment_key,
            "outcome_polarity": outcome_polarity,
            "latency_ms": latency_ms,
            "approval_required": approval_required,
            "approval_granted": approval_granted,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._client().table(self.TABLE).insert(row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("strategy_ledger_insert_skipped org=%s key=%s error=%s", org_id, strategy_key, exc)

    async def record_from_signal(
        self,
        org_id: str,
        strategy_key: str | None,
        polarity: str,
        *,
        segment_key: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not strategy_key:
            return
        if polarity == "positive":
            outcome = "win"
        elif polarity == "negative":
            outcome = "loss"
        else:
            outcome = "neutral"
        await self.record(
            org_id,
            strategy_key,
            outcome,
            segment_key=segment_key,
            metadata=metadata,
        )

    async def get_strategy_stats(
        self,
        org_id: str,
        strategy_key: str,
        *,
        segment_key: str | None = None,
        since_days: int = 30,
    ) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        try:
            query = (
                self._client()
                .table(self.TABLE)
                .select("outcome_polarity, latency_ms")
                .eq("org_id", org_id)
                .eq("strategy_key", strategy_key)
                .gte("created_at", since)
            )
            if segment_key:
                query = query.eq("segment_key", segment_key)
            rows = query.limit(5000).execute().data or []
        except Exception:  # noqa: BLE001
            rows = []
        wins = sum(1 for r in rows if r.get("outcome_polarity") == "win")
        losses = sum(1 for r in rows if r.get("outcome_polarity") == "loss")
        decided = wins + losses
        latencies = [int(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None]
        ucb = _ucb_score(wins, losses, max(len(rows), 1))
        return {
            "strategy_key": strategy_key,
            "sample_size": len(rows),
            "decided_samples": decided,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / decided, 4) if decided else None,
            "ucb_score": round(ucb, 4) if decided else None,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        }

    async def rank_strategies(
        self,
        org_id: str,
        candidate_keys: list[str],
        *,
        segment_key: str = "default",
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for key in candidate_keys:
            stats = await self.get_strategy_stats(org_id, key, segment_key=segment_key)
            ranked.append(stats)
        ranked.sort(
            key=lambda item: (
                item.get("win_rate") is not None,
                item.get("win_rate") or 0.0,
                item.get("sample_size") or 0,
            ),
            reverse=True,
        )
        return ranked

    async def choose_preferred_strategy(
        self,
        org_id: str,
        default_key: str,
        candidate_keys: list[str],
        *,
        segment_key: str = "default",
    ) -> dict[str, Any]:
        """
        Contextual bandit v2: empirical win-rate (v1) with UCB exploration fallback.
        Not neural RL — tabular ledger only.
        """
        from app.services.org_learning_profile_service import get_org_learning_profile_service

        keys = list(dict.fromkeys([default_key, *candidate_keys]))
        ranked = await self.rank_strategies(org_id, keys, segment_key=segment_key)
        profile = await get_org_learning_profile_service(self.settings).load_profile(org_id)
        segment_weights = (
            (profile.get("segments") or {}).get(segment_key, {}).get("strategy_weights") or {}
        )
        default_stats = next((item for item in ranked if item["strategy_key"] == default_key), None)
        default_rate = (default_stats or {}).get("win_rate") or 0.0
        for item in ranked:
            weight = float(segment_weights.get(item["strategy_key"]) or 1.0)
            if item.get("ucb_score") is not None:
                item["weighted_ucb_score"] = round(float(item["ucb_score"]) * weight, 4)
        for item in ranked:
            if item["strategy_key"] == default_key:
                continue
            decided = int(item.get("decided_samples") or 0)
            win_rate = item.get("win_rate")
            if decided >= MIN_SAMPLES_FOR_PREFERENCE and win_rate is not None:
                if win_rate >= default_rate + MIN_WIN_RATE_DELTA:
                    return {
                        "selected_key": item["strategy_key"],
                        "reason": "ledger_win_rate",
                        "bandit_version": "v2",
                        "stats": item,
                        "default_stats": default_stats,
                    }
        ucb_candidates = [
            item
            for item in ranked
            if int(item.get("decided_samples") or 0) >= MIN_SAMPLES_FOR_UCB
            and item.get("weighted_ucb_score") is not None
        ]
        if ucb_candidates:
            best_ucb = max(ucb_candidates, key=lambda row: float(row.get("weighted_ucb_score") or 0))
            if best_ucb["strategy_key"] != default_key and float(best_ucb.get("weighted_ucb_score") or 0) > float(
                (default_stats or {}).get("weighted_ucb_score") or (default_stats or {}).get("ucb_score") or 0
            ):
                return {
                    "selected_key": best_ucb["strategy_key"],
                    "reason": "ledger_ucb_v2",
                    "bandit_version": "v2",
                    "stats": best_ucb,
                    "default_stats": default_stats,
                }
        return {
            "selected_key": default_key,
            "reason": "default_insufficient_evidence",
            "bandit_version": "v2",
            "stats": default_stats,
        }

    async def load_model_outcome_scores(self, org_id: str) -> dict[str, float | None]:
        scores: dict[str, float | None] = {}
        for name, meta in GRAVITRE_ML_CATALOG.items():
            if meta.get("status") != ModelStatus.TRAINED:
                scores[name] = None
                continue
            stats = await self.get_strategy_stats(org_id, build_model_strategy_key(name))
            decided = int(stats.get("decided_samples") or 0)
            scores[name] = stats.get("win_rate") if decided >= 5 else None
        return scores

    async def load_admin_summary(self, org_id: str) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        try:
            rows = (
                self._client()
                .table(self.TABLE)
                .select("strategy_key, outcome_polarity, segment_key")
                .eq("org_id", org_id)
                .gte("created_at", since)
                .limit(5000)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []
        by_key: dict[str, dict[str, int]] = {}
        for row in rows:
            key = str(row.get("strategy_key") or "unknown")
            bucket = by_key.setdefault(key, {"win": 0, "loss": 0, "neutral": 0})
            pol = str(row.get("outcome_polarity") or "neutral")
            bucket[pol] = bucket.get(pol, 0) + 1
        top = sorted(
            (
                {
                    "strategy_key": key,
                    **counts,
                    "win_rate": round(counts["win"] / max(counts["win"] + counts["loss"], 1), 4),
                }
                for key, counts in by_key.items()
            ),
            key=lambda item: item["win"] + item["loss"],
            reverse=True,
        )[:15]
        return {"record_count": len(rows), "top_strategies": top}


_ledger: StrategyPerformanceLedger | None = None


def get_strategy_performance_ledger(settings: Settings | None = None) -> StrategyPerformanceLedger:
    global _ledger
    if _ledger is None or settings is not None:
        _ledger = StrategyPerformanceLedger(settings)
    return _ledger
