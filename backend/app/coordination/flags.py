"""CoordinationLayer feature flag (STA-270 / Migration 8/8). Internal test orgs only."""
from __future__ import annotations

from app.config import Settings

# Synthetic smoke org + internal demo org — never enable for customer orgs in prod UI.
DEFAULT_ALLOWED_ORG_IDS: frozenset[str] = frozenset(
    {
        "00000000-0000-0000-0000-000000000001",
    }
)


def parse_allowed_org_ids(raw: str) -> frozenset[str]:
    if not raw.strip():
        return DEFAULT_ALLOWED_ORG_IDS
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def is_coordination_layer_enabled(settings: Settings, org_id: str) -> bool:
    """True when env flag is on and org is in the allowlist."""
    if not getattr(settings, "coordination_layer_enabled", False):
        return False
    raw = getattr(settings, "coordination_layer_allowed_org_ids", "")
    allowed = parse_allowed_org_ids(raw if isinstance(raw, str) else "")
    return org_id in allowed


def coordination_layer_health(settings: Settings) -> dict[str, int | bool]:
    """Public health payload fragment for /health probes."""
    raw = getattr(settings, "coordination_layer_allowed_org_ids", "")
    return {
        "enabled": bool(getattr(settings, "coordination_layer_enabled", False)),
        "allowedOrgCount": len(parse_allowed_org_ids(raw if isinstance(raw, str) else "")),
    }
