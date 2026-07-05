"""Per-org learning profile segments stored in org settings."""
from __future__ import annotations

from typing import Any

from datetime import datetime, timezone

from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client


class OrgLearningProfileService:
    SETTINGS_KEY = "learning_profile"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def load_profile(self, org_id: str) -> dict[str, Any]:
        try:
            row = (
                self._client()
                .table("organizations")
                .select("settings")
                .eq("id", org_id)
                .limit(1)
                .execute()
            )
            if not row.data:
                return {"segments": {}}
            settings = row.data[0].get("settings") or {}
            profile = settings.get(self.SETTINGS_KEY) if isinstance(settings, dict) else {}
            if not isinstance(profile, dict):
                return {"segments": {}}
            return profile
        except Exception:  # noqa: BLE001
            return {"segments": {}}

    async def update_segment_weight(
        self,
        org_id: str,
        segment_key: str,
        *,
        strategy_key: str,
        weight_delta: float,
    ) -> dict[str, Any]:
        profile = await self.load_profile(org_id)
        segments = profile.setdefault("segments", {})
        segment = segments.setdefault(segment_key, {"strategy_weights": {}})
        weights = segment.setdefault("strategy_weights", {})
        current = float(weights.get(strategy_key) or 1.0)
        weights[strategy_key] = round(max(0.5, min(2.0, current + weight_delta)), 4)
        try:
            org_row = (
                self._client()
                .table("organizations")
                .select("settings")
                .eq("id", org_id)
                .limit(1)
                .execute()
            )
            settings_payload = (org_row.data[0].get("settings") if org_row.data else {}) or {}
            if not isinstance(settings_payload, dict):
                settings_payload = {}
            settings_payload[self.SETTINGS_KEY] = profile
            self._client().table("organizations").update({"settings": settings_payload}).eq("id", org_id).execute()
        except Exception:  # noqa: BLE001
            pass
        return profile

    async def enable_domain_adaptive_learning(self, org_id: str, *, reason: str = "manual") -> bool:
        try:
            org_row = (
                self._client()
                .table("organizations")
                .select("settings")
                .eq("id", org_id)
                .limit(1)
                .execute()
            )
            settings_payload = (org_row.data[0].get("settings") if org_row.data else {}) or {}
            if not isinstance(settings_payload, dict):
                settings_payload = {}
            profile = settings_payload.get(self.SETTINGS_KEY) if isinstance(settings_payload.get(self.SETTINGS_KEY), dict) else {}
            profile["domain_adaptive_learning_enabled"] = True
            profile["enabled_reason"] = reason
            profile["enabled_at"] = datetime.now(timezone.utc).isoformat()
            settings_payload[self.SETTINGS_KEY] = profile
            self._client().table("organizations").update({"settings": settings_payload}).eq("id", org_id).execute()
            return True
        except Exception:  # noqa: BLE001
            return False

    async def is_adaptive_learning_enabled(self, org_id: str) -> bool:
        if bool(getattr(self.settings, "domain_adaptive_learning_enabled", False)):
            return True
        profile = await self.load_profile(org_id)
        return bool(profile.get("domain_adaptive_learning_enabled"))


_profile_service: OrgLearningProfileService | None = None


def get_org_learning_profile_service(settings: Settings | None = None) -> OrgLearningProfileService:
    global _profile_service
    if _profile_service is None or settings is not None:
        _profile_service = OrgLearningProfileService(settings)
    return _profile_service
