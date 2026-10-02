"""Marketplace 3.0 ROI reporting.

Estimated value, adoption, verified outcomes, and realized value are deliberately
separate concepts. Usage proves that an installed asset was used; it does not
prove that the declared business outcome occurred.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.marketplace.adoption import count_adoption_events
from app.plays.outcomes import PLAY_BUSINESS_RESULT_EVENT, BusinessResultStatus


def _install_play_keys(install: dict[str, Any]) -> set[str]:
    metadata = install.get("metadata") if isinstance(install.get("metadata"), dict) else {}
    keys: set[str] = set()
    direct = metadata.get("playKey") or metadata.get("play_key")
    if direct:
        keys.add(str(direct).strip().lower())
    for row in metadata.get("plays") or []:
        if not isinstance(row, dict):
            continue
        key = row.get("playKey") or row.get("play_key")
        if key:
            keys.add(str(key).strip().lower())
    return {key for key in keys if key}


def _verified_play_results(client: Any, org_id: str) -> list[dict[str, Any]]:
    result = (
        client.table("intelligence_outcome_events")
        .select(
            "id, entity_id, before_value, after_value, measured_at, "
            "measurement_status, metadata, created_at"
        )
        .eq("org_id", org_id)
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .execute()
    )
    verified: list[dict[str, Any]] = []
    for row in result.data or []:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        state = str(metadata.get("verification_state") or "").strip().upper()
        explicit = bool(metadata.get("verified"))
        if not explicit and state != BusinessResultStatus.VERIFIED_SUCCESS.value:
            continue
        if state and state != BusinessResultStatus.VERIFIED_SUCCESS.value:
            continue
        verified.append(dict(row))
    return verified


def _measured_hours(row: dict[str, Any]) -> float:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    unit = str(metadata.get("unit") or "").strip().lower()
    if unit not in {"hour", "hours"}:
        return 0.0
    delta = metadata.get("delta_value")
    if delta is None:
        before = row.get("before_value")
        after = row.get("after_value")
        if before is None or after is None:
            return 0.0
        delta = float(after) - float(before)
    try:
        value = float(delta)
    except (TypeError, ValueError):
        return 0.0
    # Hours saved are represented as a positive realized value. A negative
    # measured delta is not converted into "savings".
    return round(max(value, 0.0), 4)


def marketplace_roi_summary(client: Any, org_id: str, *, limit: int = 15) -> dict[str, Any]:
    """Return Marketplace ROI without promoting adoption into business proof."""
    limit = max(1, min(limit, 50))

    installs = (
        client.table("marketplace_installs")
        .select(
            "id, asset_id, installed_at, installed_entity_type, metadata, marketplace_assets("
            "slug, title, asset_type, estimated_hours_saved, business_outcome, use_case"
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

    verified_results = _verified_play_results(client, org_id)
    verified_by_play: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in verified_results:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        play_key = str(metadata.get("play_key") or "").strip().lower()
        if play_key:
            verified_by_play[play_key].append(row)

    roi_rows: list[dict[str, Any]] = []
    total_estimated = 0.0
    total_realized = 0.0
    assets_with_usage = 0
    assets_with_verified_outcomes = 0
    total_verified_outcomes = 0

    for install in install_rows:
        asset_id = str(install.get("asset_id") or "")
        asset = install.get("marketplace_assets") or {}
        hours = float(asset.get("estimated_hours_saved") or 0)
        usage = usage_by_asset.get(asset_id, 0)
        play_keys = _install_play_keys(install)

        matched: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for play_key in play_keys:
            for row in verified_by_play.get(play_key, []):
                row_id = str(row.get("id") or "")
                if row_id and row_id in seen_ids:
                    continue
                if row_id:
                    seen_ids.add(row_id)
                matched.append(row)

        realized = round(sum(_measured_hours(row) for row in matched), 1)
        verified_count = len(matched)

        total_estimated += hours
        total_realized += realized
        total_verified_outcomes += verified_count
        if usage > 0:
            assets_with_usage += 1
        if verified_count > 0:
            assets_with_verified_outcomes += 1

        roi_rows.append(
            {
                "assetId": asset_id,
                "installId": str(install.get("id") or ""),
                "slug": asset.get("slug"),
                "title": asset.get("title"),
                "assetType": asset.get("asset_type"),
                "estimatedHoursSaved": hours,
                "realizedHoursSaved": realized,
                "usageEvents": usage,
                "verifiedOutcomeEvents": verified_count,
                "outcomeVerified": verified_count > 0,
                "installedAt": install.get("installed_at"),
                "businessOutcome": asset.get("business_outcome"),
                "useCase": asset.get("use_case"),
            }
        )

    roi_rows.sort(
        key=lambda row: (
            -row["realizedHoursSaved"],
            -row["verifiedOutcomeEvents"],
            -row["usageEvents"],
            row["title"] or "",
        )
    )

    return {
        "orgId": org_id,
        "activeInstalls": len(install_rows),
        "assetsWithUsage": assets_with_usage,
        "assetsWithVerifiedOutcomes": assets_with_verified_outcomes,
        "totalUsageEvents": count_adoption_events(client, org_id),
        "totalVerifiedOutcomeEvents": total_verified_outcomes,
        "totalEstimatedHoursSaved": round(total_estimated, 1),
        "totalRealizedHoursSaved": round(total_realized, 1),
        "realizationRate": round((total_realized / total_estimated) * 100, 1) if total_estimated else 0.0,
        "byAsset": roi_rows[:limit],
    }
