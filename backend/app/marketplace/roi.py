"""Strategic hours-saved ROI reporting (MKT-AUDIT-13.2)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.marketplace.adoption import count_adoption_events


def marketplace_roi_summary(client: Any, org_id: str, *, limit: int = 15) -> dict[str, Any]:
    """
    Correlate active installs, adoption usage, and estimated_hours_saved.

    An asset contributes its full estimated_hours_saved once it has at least one
    adoption event; otherwise realized hours are zero.
    """
    limit = max(1, min(limit, 50))

    installs = (
        client.table("marketplace_installs")
        .select(
            "id, asset_id, installed_at, marketplace_assets("
            "slug, title, estimated_hours_saved, business_outcome, use_case"
            ")"
        )
        .eq("org_id", org_id)
        .eq("status", "active")
        .execute()
    )
    install_rows = installs.data or []

    usage_by_asset: dict[str, int] = defaultdict(int)
    events = (
        client.table("marketplace_asset_adoption_events")
        .select("asset_id")
        .eq("org_id", org_id)
        .execute()
    )
    for row in events.data or []:
        asset_id = str(row.get("asset_id") or "")
        if asset_id:
            usage_by_asset[asset_id] += 1

    roi_rows: list[dict[str, Any]] = []
    total_estimated = 0.0
    total_realized = 0.0
    assets_with_usage = 0

    for install in install_rows:
        asset_id = str(install.get("asset_id") or "")
        asset = install.get("marketplace_assets") or {}
        hours = float(asset.get("estimated_hours_saved") or 0)
        usage = usage_by_asset.get(asset_id, 0)
        realized = hours if usage > 0 else 0.0
        total_estimated += hours
        total_realized += realized
        if usage > 0:
            assets_with_usage += 1
        roi_rows.append(
            {
                "assetId": asset_id,
                "installId": str(install.get("id") or ""),
                "slug": asset.get("slug"),
                "title": asset.get("title"),
                "estimatedHoursSaved": hours,
                "realizedHoursSaved": realized,
                "usageEvents": usage,
                "installedAt": install.get("installed_at"),
                "businessOutcome": asset.get("business_outcome"),
                "useCase": asset.get("use_case"),
            }
        )

    roi_rows.sort(key=lambda row: (-row["realizedHoursSaved"], -row["usageEvents"], row["title"] or ""))

    return {
        "orgId": org_id,
        "activeInstalls": len(install_rows),
        "assetsWithUsage": assets_with_usage,
        "totalUsageEvents": count_adoption_events(client, org_id),
        "totalEstimatedHoursSaved": round(total_estimated, 1),
        "totalRealizedHoursSaved": round(total_realized, 1),
        "realizationRate": round((total_realized / total_estimated) * 100, 1) if total_estimated else 0.0,
        "byAsset": roi_rows[:limit],
    }
