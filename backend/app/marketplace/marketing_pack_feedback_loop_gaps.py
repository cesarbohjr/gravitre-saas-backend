"""STA-293 / MKT-PACK-AUDIT 6.2: Marketing pack outcome feedback loop audit (Mode A / Mode B)."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

FeedbackMode = Literal["mode_a", "mode_b", "shared"]
FeedbackGapState = Literal["exists", "partial", "missing"]
PackBlocker = Literal["yes", "no", "depends"]

REPO_ROOT = Path(__file__).resolve().parents[3]
MARKETING_OBSERVABLE_METRIC_CONNECTORS = frozenset({"google_analytics", "linkedin", "canva", "hubspot_campaign"})


@dataclass(frozen=True)
class MarketingPackFeedbackCapability:
    key: str
    display_name: str
    mode: FeedbackMode
    audit_state: FeedbackGapState
    complexity: Literal["low", "medium", "high"]
    blocks_pack: PackBlocker
    notes: str
    module_path: str | None = None
    symbol: str | None = None


MODE_A_CAPABILITIES: tuple[MarketingPackFeedbackCapability, ...] = (
    MarketingPackFeedbackCapability(
        key="company_intelligence_orchestrator",
        display_name="Company intelligence learning loop",
        mode="mode_a",
        audit_state="partial",
        complexity="medium",
        blocks_pack="no",
        notes="Per-org ML loop (intent, anomaly, forecaster, success); not marketing-metrics-aware.",
        module_path="app.services.company_intelligence_orchestrator",
        symbol="CompanyIntelligenceOrchestrator",
    ),
    MarketingPackFeedbackCapability(
        key="outcome_attribution",
        display_name="Outcome attribution (correlational)",
        mode="mode_a",
        audit_state="partial",
        complexity="medium",
        blocks_pack="depends",
        notes="HubSpot deal amount + Stripe subscription metrics only; correlational, not RL.",
        module_path="app.services.outcome_attribution_service",
        symbol="OutcomeAttributionService",
    ),
    MarketingPackFeedbackCapability(
        key="integration_suggestions",
        display_name="Integration suggestions (human apply)",
        mode="mode_a",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="Audit-usage scan → integration_suggestions table; apply requires human actor.",
        module_path="app.services.integration_suggestion_service",
        symbol="apply_integration_suggestion",
    ),
    MarketingPackFeedbackCapability(
        key="optimization_suggestions",
        display_name="Optimization suggestions (human apply)",
        mode="mode_a",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="Evidence-backed suggestions; never auto-applies — human preview/apply gate.",
        module_path="app.services.optimization_suggestion_service",
        symbol="OptimizationSuggestionService",
    ),
    MarketingPackFeedbackCapability(
        key="human_approval_gate",
        display_name="Human approval before behavior change",
        mode="mode_a",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="apply_integration_suggestion + apply_optimization_suggestion require actor_id.",
        module_path="app.services.optimization_suggestion_service",
        symbol="OptimizationSuggestionService",
    ),
    MarketingPackFeedbackCapability(
        key="post_publish_marketing_metrics",
        display_name="Post-publish marketing metrics to suggestions",
        mode="mode_a",
        audit_state="exists",
        complexity="medium",
        blocks_pack="depends",
        notes="GA4/LinkedIn/Canva/HubSpot campaign metrics wired into outcome attribution and optimization detectors.",
        module_path="app.services.post_publish_marketing_metrics_service",
        symbol="maybe_record_post_publish_marketing_baseline",
    ),
)

MODE_B_CAPABILITIES: tuple[MarketingPackFeedbackCapability, ...] = (
    MarketingPackFeedbackCapability(
        key="autonomous_replanning_loop",
        display_name="Autonomous outcome-driven replanning",
        mode="mode_b",
        audit_state="partial",
        complexity="high",
        blocks_pack="depends",
        notes="run_replanning_cycle shipped; post-publish marketing metrics wiring still partial.",
        module_path="app.services.mode_b_feedback_service",
        symbol="run_replanning_cycle",
    ),
    MarketingPackFeedbackCapability(
        key="tone_cadence_auto_shift",
        display_name="Automatic tone/cadence/content-type shifts",
        mode="mode_b",
        audit_state="exists",
        complexity="high",
        blocks_pack="depends",
        notes="apply_autonomous_mutation shifts tone/cadence/content_type in agent feedbackProfile.",
        module_path="app.services.mode_b_feedback_service",
        symbol="apply_autonomous_mutation",
    ),
    MarketingPackFeedbackCapability(
        key="per_cycle_behavior_caps",
        display_name="Per-cycle behavior shift caps",
        mode="mode_b",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="assert_cycle_cap_allows_shift enforces max_shift_percent_per_cycle on org_feedback_settings.",
        module_path="app.services.mode_b_feedback_service",
        symbol="assert_cycle_cap_allows_shift",
    ),
    MarketingPackFeedbackCapability(
        key="autonomous_rollback",
        display_name="Rollback when new behavior underperforms",
        mode="mode_b",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="rollback_mutation restores agent_config_before snapshot on outcome regression.",
        module_path="app.services.mode_b_feedback_service",
        symbol="rollback_mutation",
    ),
    MarketingPackFeedbackCapability(
        key="post_hoc_audit_without_approval",
        display_name="Post-hoc audit trail (no approval anchor)",
        mode="mode_b",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="mode_b_autonomous_events + feedback.mode_b.* audit actions without actor approval.",
        module_path="app.services.mode_b_feedback_service",
        symbol="record_autonomous_event",
    ),
)

SHARED_FEEDBACK_CAPABILITIES: tuple[MarketingPackFeedbackCapability, ...] = (
    MarketingPackFeedbackCapability(
        key="feedback_mode_toggle",
        display_name="Mode A/B feedback toggle (general primitive)",
        mode="shared",
        audit_state="exists",
        complexity="medium",
        blocks_pack="depends",
        notes="org_feedback_settings + set_feedback_mode API with Mode B risk gate.",
        module_path="app.services.mode_b_feedback_service",
        symbol="set_feedback_mode",
    ),
    MarketingPackFeedbackCapability(
        key="mode_b_pricing_constant",
        display_name="Mode B pricing placeholder",
        mode="shared",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="MODE_B_AUTONOMOUS_ADDON_CENTS in pack_pricing.py; no Stripe SKU or entitlement yet.",
        module_path="app.marketplace.pack_pricing",
        symbol="MODE_B_AUTONOMOUS_ADDON_CENTS",
    ),
)

ALL_FEEDBACK_CAPABILITIES = MODE_A_CAPABILITIES + MODE_B_CAPABILITIES + SHARED_FEEDBACK_CAPABILITIES

MODE_B_INFRA_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260709150000_mode_b_feedback_infrastructure.sql"

MODE_B_LIVE_CHECKS: dict[str, tuple[str, str]] = {
    "autonomous_replanning_loop": ("app.services.mode_b_feedback_service", "run_replanning_cycle"),
    "tone_cadence_auto_shift": ("app.services.mode_b_feedback_service", "apply_autonomous_mutation"),
    "per_cycle_behavior_caps": ("app.services.mode_b_feedback_service", "assert_cycle_cap_allows_shift"),
    "autonomous_rollback": ("app.services.mode_b_feedback_service", "rollback_mutation"),
    "post_hoc_audit_without_approval": ("app.services.mode_b_feedback_service", "record_autonomous_event"),
    "feedback_mode_toggle": ("app.services.mode_b_feedback_service", "set_feedback_mode"),
}


def _module_loaded(module_path: str) -> bool:
    return importlib.util.find_spec(module_path) is not None


def _symbol_exists(module_path: str, symbol: str) -> bool:
    if not _module_loaded(module_path):
        return False
    module = importlib.import_module(module_path)
    if getattr(module, symbol, None) is not None:
        return True
    service_cls = getattr(module, "ModeBFeedbackService", None)
    if service_cls is not None and getattr(service_cls, symbol, None) is not None:
        return True
    return False


def _outcome_attribution_marketing_metrics_wired() -> bool:
    from app.services import outcome_attribution_service as module
    from app.services.post_publish_marketing_metrics_service import (
        OBSERVABLE_MARKETING_METRICS,
        maybe_record_post_publish_marketing_baseline,
    )

    if maybe_record_post_publish_marketing_baseline is None:
        return False
    if not OBSERVABLE_MARKETING_METRICS:
        return False

    scope = str(getattr(module, "CONFIDENCE_NOTE", ""))
    if "marketing" in scope.lower():
        return True
    admin_loader = getattr(module.OutcomeAttributionService, "load_admin_outcomes_snapshot", None)
    if admin_loader is None:
        return False
    import inspect

    source = inspect.getsource(module.OutcomeAttributionService.load_admin_outcomes_snapshot)
    return any(connector in source for connector in MARKETING_OBSERVABLE_METRIC_CONNECTORS)


def _mode_b_infrastructure_migration_exists() -> bool:
    if not MODE_B_INFRA_MIGRATION.is_file():
        return False
    text = MODE_B_INFRA_MIGRATION.read_text(encoding="utf-8")
    return "org_feedback_settings" in text and "mode_b_autonomous_events" in text


def _mode_b_capability_live(key: str) -> bool:
    if not _mode_b_infrastructure_migration_exists():
        return False
    module_path, symbol = MODE_B_LIVE_CHECKS.get(key, ("", ""))
    if not module_path:
        return False
    return _symbol_exists(module_path, symbol)


def _resolve_live_state(cap: MarketingPackFeedbackCapability) -> FeedbackGapState:
    if cap.key == "post_publish_marketing_metrics":
        return "exists" if _outcome_attribution_marketing_metrics_wired() else "missing"

    if cap.key == "human_approval_gate":
        has_opt = _symbol_exists(
            "app.services.optimization_suggestion_service",
            "OptimizationSuggestionService",
        )
        has_int = _symbol_exists(
            "app.services.integration_suggestion_service",
            "apply_integration_suggestion",
        )
        if has_opt and has_int:
            return "exists"
        if has_opt or has_int:
            return "partial"
        return "missing"

    if cap.key in MODE_B_LIVE_CHECKS:
        if not _mode_b_capability_live(cap.key):
            return "missing"
        if cap.audit_state == "partial":
            return "partial"
        return "exists"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        if cap.audit_state == "partial":
            return "partial"
        return "exists"

    return cap.audit_state


def audit_marketing_pack_feedback_loop() -> dict[str, Any]:
    """Return STA-293 checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0
    mode_a_missing: list[str] = []
    mode_b_missing: list[str] = []

    for cap in ALL_FEEDBACK_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
            if cap.mode == "mode_a":
                mode_a_missing.append(cap.key)
            elif cap.mode == "mode_b":
                mode_b_missing.append(cap.key)
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1

        rows.append(
            {
                "key": cap.key,
                "displayName": cap.display_name,
                "mode": cap.mode,
                "documentedState": cap.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == cap.audit_state,
                "complexity": cap.complexity,
                "blocksPack": cap.blocks_pack,
                "notes": cap.notes,
            }
        )

    mode_a_rows = [row for row in rows if row["mode"] == "mode_a"]
    mode_b_rows = [row for row in rows if row["mode"] == "mode_b"]
    shared_rows = [row for row in rows if row["mode"] == "shared"]

    pack_blockers: list[str] = []
    if "post_publish_marketing_metrics" in mode_a_missing:
        pack_blockers.append("post_publish_marketing_metrics")
    if any(row["key"] == "feedback_mode_toggle" and row["liveState"] == "missing" for row in shared_rows):
        pass  # depends on STA-294 product sign-off; not a hard blocker for Mode A default

    return {
        "issue": "STA-293",
        "packSlug": "marketing-operations-pack",
        "productDecisionTicket": "STA-294",
        "recommendedDefault": "mode_a",
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "modeA": {
                "total": len(mode_a_rows),
                "missing": sum(1 for row in mode_a_rows if row["liveState"] == "missing"),
                "partial": sum(1 for row in mode_a_rows if row["liveState"] == "partial"),
                "exists": sum(1 for row in mode_a_rows if row["liveState"] == "exists"),
                "extendable": True,
            },
            "modeB": {
                "total": len(mode_b_rows),
                "missing": sum(1 for row in mode_b_rows if row["liveState"] == "missing"),
                "partial": sum(1 for row in mode_b_rows if row["liveState"] == "partial"),
                "exists": sum(1 for row in mode_b_rows if row["liveState"] == "exists"),
                "netNewPlatformWork": True,
            },
            "packBlockers": pack_blockers,
            "modeBMissingKeys": [row["key"] for row in mode_b_rows if row["liveState"] == "missing"],
            "awaitingProductSignOff": False,
            "modeBInfrastructureShipped": _mode_b_infrastructure_migration_exists(),
        },
        "modeA": mode_a_rows,
        "modeB": mode_b_rows,
        "shared": shared_rows,
        "capabilities": rows,
    }
