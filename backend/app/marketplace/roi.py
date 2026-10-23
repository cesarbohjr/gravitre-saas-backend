"""Strategic hours-saved ROI reporting (MKT-AUDIT-13.2)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any
from datetime import datetime
from math import isfinite
from app.core.safe_dict import safe_normalize_stored_dict

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
            "id, asset_id, installed_at, metadata, marketplace_assets("
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

    outcome_rows = (client.table("intelligence_outcome_events")
        .select("id,org_id,workflow_id,workflow_run_id,before_value,after_value,measurement_status,metadata,created_at")
        .eq("org_id", org_id).eq("outcome_event", "play_business_result")
        .eq("measurement_status", "recorded").limit(1000).execute().data or [])

    roi_rows: list[dict[str, Any]] = []
    total_estimated = 0.0
    total_realized = 0.0
    assets_with_usage = 0

    for install in install_rows:
        asset_id = str(install.get("asset_id") or "")
        asset = install.get("marketplace_assets") or {}
        hours = float(asset.get("estimated_hours_saved") or 0)
        usage = usage_by_asset.get(asset_id, 0)
        metadata = safe_normalize_stored_dict(install.get("metadata"))
        workflow_ids = {str(row.get("workflowId")) for row in metadata.get("plays", [])
                        if isinstance(row, dict) and row.get("workflowId")}
        verified_keys: set[tuple[str, str, str]] = set()
        for row in outcome_rows:
            proof = safe_normalize_stored_dict(row.get("metadata"))
            if (row.get("org_id") != org_id or str(row.get("workflow_id")) not in workflow_ids
                    or row.get("measurement_status") != "recorded" or proof.get("contract") != "play_business_result/v1"
                    or proof.get("verified") is not True or proof.get("verification_state") != "VERIFIED SUCCESS"
                    or not proof.get("source_records") or not proof.get("evidence_ids")
                    or not proof.get("verification_method") or not row.get("workflow_run_id")):
                continue
            try:
                created = datetime.fromisoformat(str(row.get("created_at")).replace("Z", "+00:00"))
                installed = datetime.fromisoformat(str(install.get("installed_at")).replace("Z", "+00:00"))
                if created < installed or not all(isfinite(float(row[key])) for key in ("before_value", "after_value")):
                    continue
            except (TypeError, ValueError, KeyError):
                continue
            verified_keys.add((str(row["workflow_run_id"]), str(proof.get("metric_key")), str(proof.get("outcome_type"))))
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
                "verifiedOutcomeEvents": len(verified_keys),
                "measurementBasis": "catalog_estimate_with_separate_verified_outcomes",
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
        "totalVerifiedOutcomeEvents": sum(row["verifiedOutcomeEvents"] for row in roi_rows),
        "verifiedOutcomeCountIsLowerBound": len(outcome_rows) >= 1000,
        "totalEstimatedHoursSaved": round(total_estimated, 1),
        "totalRealizedHoursSaved": round(total_realized, 1),
        "realizationRate": round((total_realized / total_estimated) * 100, 1) if total_estimated else 0.0,
        "byAsset": roi_rows[:limit],
        # Hours here are catalog estimates scaled by usage, not measured time saved.
        # Verified business results live on /api/metrics/business.
        "valueBasis": "estimate",
        "estimateNote": (
            "Hours saved are estimates from each asset's declared time savings and its usage. "
            "They are not measured. Verified business results are reported separately."
        ),
    }
