"""Platform golden signals for admin ops dashboard (audit_events-backed)."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.workflows.repository import get_supabase_client

PLATFORM_ORG_ID = os.environ.get(
    "GRAVITRE_PLATFORM_SIGNALS_ORG_ID",
    "00000000-0000-4000-8000-000000000001",
)

FALLTHROUGH_ALERT_PCT = float(os.environ.get("UNIFIED_TURN_FALLTHROUGH_ALERT_PCT", "10"))
FALLTHROUGH_ALERT_BUCKET_SPIKE = int(
    os.environ.get("UNIFIED_TURN_FALLTHROUGH_DEFER_SPIKE", "15")
)
# Standing TTFT alert thresholds (ms) — match fallthrough-alert pattern.
TTFT_ALERT_P50_MS = int(os.environ.get("UNIFIED_TURN_TTFT_ALERT_P50_MS", "1500"))
TTFT_ALERT_P99_MS = int(os.environ.get("UNIFIED_TURN_TTFT_ALERT_P99_MS", "5000"))
TTFT_ALERT_MAX_MS = int(os.environ.get("UNIFIED_TURN_TTFT_ALERT_MAX_MS", "10000"))
MOUNT_TTI_ALERT_MS = int(os.environ.get("CHAT_MOUNT_TTI_ALERT_MS", "3000"))


def _percentile(sorted_vals: list[int], p: float) -> int | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = int(round((len(sorted_vals) - 1) * p))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, idx))]


def _wall_ttft_ms(meta: dict[str, Any]) -> int | None:
    bd = meta.get("latency_breakdown") or {}
    if not isinstance(bd, dict):
        bd = {}
    raw = meta.get("first_token_proxy_ms")
    if raw is None:
        raw = bd.get("wall_to_first_token_ms")
    if isinstance(raw, (int, float)):
        return int(raw)
    return None


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def _fetch_rows(client: Any, *, action: str, since_iso: str, org_id: str | None = None) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    page = 500
    while True:
        q = (
            client.table("audit_events")
            .select("action,created_at,metadata,resource_id")
            .eq("action", action)
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
        )
        if org_id:
            q = q.eq("org_id", org_id)
        batch = q.range(offset, offset + page - 1).execute()
        data = batch.data or []
        if not data:
            break
        rows.extend(data)
        if len(data) < page:
            break
        offset += page
    return rows


def _latest_platform_signal(client: Any, action_stem: str, *, hours: int = 168) -> dict[str, Any] | None:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows: list[dict] = []
    for suffix in ("completed", "failed", "alert"):
        rows.extend(
            _fetch_rows(
                client,
                action=f"{action_stem}.{suffix}",
                since_iso=since,
                org_id=PLATFORM_ORG_ID,
            )
        )
    if not rows:
        return None
    row = max(rows, key=lambda r: str(r.get("created_at") or ""))
    meta = _meta(row)
    verdict = str(meta.get("verdict") or "")
    return {
        "action": row.get("action"),
        "created_at": row.get("created_at"),
        "verdict": verdict,
        "pass": verdict.upper().startswith("PASS"),
        "git_sha": meta.get("git_sha"),
        "metadata": meta,
    }


async def load_golden_signals_dashboard(settings: Any, *, period: str = "24h") -> dict[str, Any]:
    hours = {"1h": 1, "24h": 24, "7d": 168}.get(period, 24)
    since_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    client = get_supabase_client(settings)

    completed = _fetch_rows(client, action="unified_turn.live.completed", since_iso=since_iso)
    fallthrough = _fetch_rows(client, action="unified_turn.live.fallthrough", since_iso=since_iso)
    live_total = len(completed) + len(fallthrough)
    fallthrough_pct = round(100.0 * len(fallthrough) / live_total, 2) if live_total else 0.0

    defer_counts = Counter()
    cache_ratios: list[float] = []
    cache_deltas: list[int] = []
    wall_ttfTs: list[int] = []
    for row in fallthrough:
        meta = _meta(row)
        defer_counts[str(meta.get("fallthrough_reason") or "unknown")] += 1
        wall = _wall_ttft_ms(meta)
        if wall is not None:
            wall_ttfTs.append(wall)
    for row in completed:
        meta = _meta(row)
        bd = meta.get("latency_breakdown") or {}
        ratio = bd.get("cached_prompt_ratio") if isinstance(bd, dict) else None
        if isinstance(ratio, (int, float)):
            cache_ratios.append(float(ratio))
        wall = _wall_ttft_ms(meta)
        if wall is not None:
            wall_ttfTs.append(wall)

    platform_rows = _fetch_rows(
        client,
        action="platform.ttft_cache.sample",
        since_iso=since_iso,
        org_id=PLATFORM_ORG_ID,
    )
    for row in platform_rows:
        meta = _meta(row)
        delta = meta.get("model_ttft_delta_ms")
        if isinstance(delta, (int, float)):
            cache_deltas.append(int(delta))

    walls_sorted = sorted(wall_ttfTs)
    ttft_p50 = _percentile(walls_sorted, 0.50)
    ttft_p99 = _percentile(walls_sorted, 0.99)
    ttft_max = walls_sorted[-1] if walls_sorted else None

    mount_rows = _fetch_rows(
        client,
        action="platform.chat_mount_tti.sample",
        since_iso=since_iso,
        org_id=PLATFORM_ORG_ID,
    )
    mount_nav_ms: list[int] = []
    for row in mount_rows:
        meta = _meta(row)
        nav = meta.get("ai_nav_to_interactive_ms")
        if isinstance(nav, (int, float)):
            mount_nav_ms.append(int(nav))
    mount_sorted = sorted(mount_nav_ms)
    mount_p50 = _percentile(mount_sorted, 0.50)
    mount_max = mount_sorted[-1] if mount_sorted else None
    latest_mount = None
    if mount_rows:
        latest = max(mount_rows, key=lambda r: str(r.get("created_at") or ""))
        latest_mount = {
            "created_at": latest.get("created_at"),
            **{k: v for k, v in _meta(latest).items() if k in {
                "ai_nav_to_interactive_ms",
                "chat_tti_from_script_start_ms",
                "mount_intel_before_interactive_n",
                "verdict",
                "git_sha",
            }},
        }

    deploy_smoke = _latest_platform_signal(client, "platform.deploy_smoke")
    hardening = _latest_platform_signal(client, "platform.hardening_smoke")

    alerts: list[str] = []
    if fallthrough_pct > FALLTHROUGH_ALERT_PCT:
        alerts.append(f"fallthrough_pct>{FALLTHROUGH_ALERT_PCT}%")
    defer_proposal = defer_counts.get("defer_connector_tool_proposal", 0)
    if defer_proposal >= FALLTHROUGH_ALERT_BUCKET_SPIKE:
        alerts.append(f"defer_connector_tool_proposal_spike>={FALLTHROUGH_ALERT_BUCKET_SPIKE}")

    ttft_alerts: list[str] = []
    if ttft_p50 is not None and ttft_p50 > TTFT_ALERT_P50_MS:
        ttft_alerts.append(f"ttft_p50>{TTFT_ALERT_P50_MS}ms")
    if ttft_p99 is not None and ttft_p99 > TTFT_ALERT_P99_MS:
        ttft_alerts.append(f"ttft_p99>{TTFT_ALERT_P99_MS}ms")
    if ttft_max is not None and ttft_max > TTFT_ALERT_MAX_MS:
        ttft_alerts.append(f"ttft_max>{TTFT_ALERT_MAX_MS}ms")
    alerts.extend(ttft_alerts)

    mount_alerts: list[str] = []
    if mount_p50 is not None and mount_p50 > MOUNT_TTI_ALERT_MS:
        mount_alerts.append(f"mount_ai_nav_p50>{MOUNT_TTI_ALERT_MS}ms")
    alerts.extend(mount_alerts)

    r2_ready = (
        fallthrough_pct <= 1.0
        and (deploy_smoke or {}).get("pass") is True
        and not alerts
    )

    return {
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deploy_smoke": deploy_smoke,
        "hardening_smoke": hardening,
        "fallthrough": {
            "window_hours": hours,
            "live_completed": len(completed),
            "live_fallthrough": len(fallthrough),
            "fallthrough_pct": fallthrough_pct,
            "by_reason": dict(defer_counts),
            "alert_threshold_pct": FALLTHROUGH_ALERT_PCT,
            "alerts": [a for a in alerts if a.startswith("fallthrough") or a.startswith("defer_")],
        },
        "ttft": {
            "window_hours": hours,
            "sample_count": len(walls_sorted),
            "wall_p50_ms": ttft_p50,
            "wall_p99_ms": ttft_p99,
            "wall_max_ms": ttft_max,
            "alert_thresholds_ms": {
                "p50": TTFT_ALERT_P50_MS,
                "p99": TTFT_ALERT_P99_MS,
                "max": TTFT_ALERT_MAX_MS,
            },
            "alerts": ttft_alerts,
        },
        "mount_tti": {
            "window_hours": hours,
            "sample_count": len(mount_sorted),
            "ai_nav_to_interactive_p50_ms": mount_p50,
            "ai_nav_to_interactive_max_ms": mount_max,
            "latest": latest_mount,
            "alert_threshold_ms": MOUNT_TTI_ALERT_MS,
            "alerts": mount_alerts,
        },
        "prefix_cache": {
            "avg_cached_prompt_ratio": round(sum(cache_ratios) / len(cache_ratios), 4)
            if cache_ratios
            else None,
            "sample_count": len(cache_ratios),
            "ttft_delta_samples": len(cache_deltas),
            "avg_ttft_delta_ms": round(sum(cache_deltas) / len(cache_deltas))
            if cache_deltas
            else None,
        },
        "alerts": alerts,
        "r2_removal_gates": {
            "fallthrough_pct_target": 1.0,
            "current_fallthrough_pct": fallthrough_pct,
            "deploy_smoke_green": (deploy_smoke or {}).get("pass"),
            "alerts_clear": not alerts,
            "ready": r2_ready,
        },
        "status_page_proposal": {
            "customer_facing": "deferred",
            "note": "Internal golden signals first; public uptime page is a product decision.",
        },
    }
