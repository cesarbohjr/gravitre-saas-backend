"""Plan-included voice access + org ON/OFF (replaces Meson voice_interface purchase gate)."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.errors import error_detail


def load_voice_org_settings(client, *, org_id: str) -> dict[str, Any]:
    """Read voice flags from subscriptions; defaults are plan-included ON."""
    try:
        rows = (
            client.table("subscriptions")
            .select(
                "voice_enabled, voice_minutes_prepaid, voice_auto_topup_enabled, "
                "voice_auto_topup_minutes, voice_auto_topup_threshold_minutes, "
                "voice_auto_topup_max_charge_cents, meson_addons, status"
            )
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    row = rows[0] if rows else {}
    enabled = row.get("voice_enabled")
    if enabled is None:
        enabled = True
    prepaid = 0
    try:
        prepaid = max(int(row.get("voice_minutes_prepaid") or 0), 0)
    except (TypeError, ValueError):
        prepaid = 0
    return {
        "voice_enabled": bool(enabled),
        "voice_minutes_prepaid": prepaid,
        "voice_auto_topup_enabled": bool(row.get("voice_auto_topup_enabled")),
        "voice_auto_topup_minutes": max(int(row.get("voice_auto_topup_minutes") or 60), 1),
        "voice_auto_topup_threshold_minutes": max(
            int(row.get("voice_auto_topup_threshold_minutes") or 15), 0
        ),
        "voice_auto_topup_max_charge_cents": max(
            int(row.get("voice_auto_topup_max_charge_cents") or 3600), 100
        ),
        "subscription_status": str(row.get("status") or ""),
    }


def assert_voice_org_enabled(client, *, org_id: str) -> dict[str, Any]:
    """Gate /api/voice: plan-included unless org admin disabled voice."""
    settings = load_voice_org_settings(client, org_id=org_id)
    if not settings["voice_enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail(
                "Voice is turned off for this organization",
                "UNAUTHORIZED",
                {"reason": "voice_org_disabled", "action": "voice_use"},
            ),
        )
    return settings


def set_voice_org_enabled(client, *, org_id: str, enabled: bool) -> dict[str, Any]:
    client.table("subscriptions").upsert(
        {"org_id": org_id, "voice_enabled": bool(enabled)},
        on_conflict="org_id",
    ).execute()
    # Keep meson_addons free of a fake purchase signal for voice_interface.
    try:
        rows = (
            client.table("subscriptions")
            .select("meson_addons")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        addons = list((rows[0] or {}).get("meson_addons") or [])
        if isinstance(addons, list) and "voice_interface" in addons:
            cleaned = [a for a in addons if str(a) != "voice_interface"]
            client.table("subscriptions").update({"meson_addons": cleaned}).eq(
                "org_id", org_id
            ).execute()
    except Exception:
        pass
    return load_voice_org_settings(client, org_id=org_id)
