"""Bounded confidence multipliers from recent learning signals."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client

MIN_MULTIPLIER = 0.85
MAX_MULTIPLIER = 1.15
DEFAULT_MULTIPLIER = 1.0


class ConfidenceCalibrator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache: dict[str, tuple[float, datetime]] = {}

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def get_multiplier(self, org_id: str, surface: str = "default", *, ttl_seconds: int = 60) -> float:
        cache_key = f"{org_id}:{surface}"
        cached = self._cache.get(cache_key)
        now = datetime.now(timezone.utc)
        if cached and (now - cached[1]).total_seconds() < ttl_seconds:
            return cached[0]
        multiplier = self._compute_multiplier(org_id, surface)
        self._cache[cache_key] = (multiplier, now)
        return multiplier

    def _compute_multiplier(self, org_id: str, surface: str) -> float:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        try:
            query = (
                self._client()
                .table("intelligence_learning_signals")
                .select("polarity, weight")
                .eq("org_id", org_id)
                .gte("created_at", since)
            )
            if surface != "default":
                query = query.eq("surface", surface)
            rows = query.limit(3000).execute().data or []
        except Exception:  # noqa: BLE001
            return DEFAULT_MULTIPLIER
        positive = sum(float(r.get("weight") or 0) for r in rows if r.get("polarity") == "positive")
        negative = sum(float(r.get("weight") or 0) for r in rows if r.get("polarity") == "negative")
        total = positive + negative
        if total < 5:
            return DEFAULT_MULTIPLIER
        ratio = positive / total
        # Map 0.5 -> MIN, 0.75+ -> MAX linearly
        scaled = MIN_MULTIPLIER + (MAX_MULTIPLIER - MIN_MULTIPLIER) * max(0.0, min(1.0, (ratio - 0.4) / 0.4))
        return round(scaled, 4)


_calibrator: ConfidenceCalibrator | None = None


def get_confidence_calibrator(settings: Settings | None = None) -> ConfidenceCalibrator:
    global _calibrator
    if _calibrator is None or settings is not None:
        _calibrator = ConfidenceCalibrator(settings)
    return _calibrator
