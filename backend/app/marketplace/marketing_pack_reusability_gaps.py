"""STA-299 / MKT-PACK-AUDIT 7.4: Marketing pack reusability — general vs marketing-specific primitives."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ReusabilityState = Literal["exists", "partial", "missing"]
ReuseScope = Literal["general", "marketing_specific", "open_uncertainty"]
PackBlocker = Literal["yes", "no", "depends"]

REPO_ROOT = Path(__file__).resolve().parents[3]
APPROVAL_BATCH_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260709140000_approval_batches.sql"
PACK_TIER_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260709120000_marketplace_pack_tier.sql"
ONE_TIME_PRICING_MIGRATION = (
    REPO_ROOT / "supabase" / "migrations" / "20260709130000_department_pack_one_time_pricing.sql"
)
MODE_B_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260709150000_mode_b_feedback_infrastructure.sql"
MARKETING_PACK_SLUG = "marketing-operations-pack"


@dataclass(frozen=True)
class ReusabilityCapability:
    key: str
    display_name: str
    reuse_scope: ReuseScope
    audit_state: ReusabilityState
    complexity: Literal["low", "medium", "high"]
    blocks_future_packs: PackBlocker
    notes: str
    module_path: str | None = None
    symbol: str | None = None


GENERAL_PRIMITIVES: tuple[ReusabilityCapability, ...] = (
    ReusabilityCapability(
        key="graph_handoff_agent_chains",
        display_name="Graph + handoff agent chains (department packs)",
        reuse_scope="general",
        audit_state="exists",
        complexity="medium",
        blocks_future_packs="no",
        notes="next_agent_seed resolved at install; reusable for HR/Finance/Ops/Sales packs.",
        module_path="app.marketplace.service",
        symbol="_install_department_pack",
    ),
    ReusabilityCapability(
        key="department_pack_marketplace_type",
        display_name="department_pack marketplace asset type",
        reuse_scope="general",
        audit_state="exists",
        complexity="low",
        blocks_future_packs="no",
        notes="schemas.py + seed_catalog department_pack entries for all department packs.",
        module_path="app.marketplace.schemas",
        symbol="DepartmentPackAssetConfig",
    ),
    ReusabilityCapability(
        key="mode_ab_feedback_toggle",
        display_name="Mode A/B feedback toggle (org-scoped)",
        reuse_scope="general",
        audit_state="exists",
        complexity="medium",
        blocks_future_packs="no",
        notes="org_feedback_settings + /api/admin/feedback-mode; Marketing is first consumer.",
        module_path="app.services.mode_b_feedback_service",
        symbol="set_feedback_mode",
    ),
    ReusabilityCapability(
        key="batch_partial_approval",
        display_name="Batch + partial approval primitive",
        reuse_scope="general",
        audit_state="partial",
        complexity="high",
        blocks_future_packs="depends",
        notes="STA-290 schema + runtime shipped; analytics/reporting still missing (STA-297).",
        module_path="app.workflows.approval_batch_service",
        symbol="create_approval_batch",
    ),
    ReusabilityCapability(
        key="rejection_upstream_routing",
        display_name="Rejection -> upstream agent routing",
        reuse_scope="general",
        audit_state="partial",
        complexity="medium",
        blocks_future_packs="depends",
        notes="on_reject=route_upstream + reject_route_node_id in execution_engine_runtime.",
        module_path="app.workflows.execution_engine_runtime",
        symbol="_route_upstream_on_reject",
    ),
    ReusabilityCapability(
        key="pack_tier_pricing_framework",
        display_name="Pack tier pricing framework (one-time paid)",
        reuse_scope="general",
        audit_state="exists",
        complexity="low",
        blocks_future_packs="no",
        notes="pack_pricing.py tier bands $49/$149/$299; pack_tier migration.",
        module_path="app.marketplace.pack_pricing",
        symbol="validate_department_pack_pricing",
    ),
    ReusabilityCapability(
        key="one_time_entitlement_path",
        display_name="One-time paid entitlement + checkout",
        reuse_scope="general",
        audit_state="exists",
        complexity="medium",
        blocks_future_packs="no",
        notes="assert_install_entitlement + create_asset_checkout_session payment mode.",
        module_path="app.marketplace.entitlements",
        symbol="assert_install_entitlement",
    ),
)

MARKETING_SPECIFIC: tuple[ReusabilityCapability, ...] = (
    ReusabilityCapability(
        key="linkedin_publish_connector",
        display_name="LinkedIn organic publishing connector",
        reuse_scope="marketing_specific",
        audit_state="partial",
        complexity="high",
        blocks_future_packs="depends",
        notes="LinkedIn read/enrich only; no posts.create / w_member_social publish action.",
    ),
    ReusabilityCapability(
        key="post_publish_engagement_metrics",
        display_name="Post-publish marketing metrics -> suggestions",
        reuse_scope="marketing_specific",
        audit_state="exists",
        complexity="medium",
        blocks_future_packs="depends",
        notes="GA4/LinkedIn/Canva/HubSpot wired via post_publish_marketing_metrics_service.",
        module_path="app.services.post_publish_marketing_metrics_service",
        symbol="maybe_record_post_publish_marketing_baseline",
    ),
)

OPEN_UNCERTAINTIES: tuple[ReusabilityCapability, ...] = (
    ReusabilityCapability(
        key="tier_eligibility_checkout_gating",
        display_name="Platform tier eligibility enforced at pack checkout",
        reuse_scope="open_uncertainty",
        audit_state="missing",
        complexity="medium",
        blocks_future_packs="depends",
        notes="pack_pricing documents Control/Command requirement; checkout does not enforce platform tier.",
        module_path="app.marketplace.entitlements",
        symbol="create_asset_checkout_session",
    ),
)

ALL_REUSABILITY_CAPABILITIES = GENERAL_PRIMITIVES + MARKETING_SPECIFIC + OPEN_UNCERTAINTIES


def _module_source_path(module_path: str) -> Path | None:
    relative = module_path.replace(".", "/") + ".py"
    candidate = REPO_ROOT / "backend" / relative
    return candidate if candidate.is_file() else None


def _symbol_exists(module_path: str, symbol: str) -> bool:
    source_path = _module_source_path(module_path)
    if source_path is not None:
        text = source_path.read_text(encoding="utf-8")
        return f"def {symbol}" in text or f"class {symbol}" in text or f"async def {symbol}" in text
    if importlib.util.find_spec(module_path) is None:
        return False
    module = importlib.import_module(module_path)
    return getattr(module, symbol, None) is not None


def _department_pack_handoff_shipped() -> bool:
    service_path = _module_source_path("app.marketplace.service")
    if service_path is None:
        return False
    text = service_path.read_text(encoding="utf-8")
    return "_install_department_pack" in text and "next_agent_seed" in text


def _batch_partial_approval_shipped() -> bool:
    return APPROVAL_BATCH_MIGRATION.is_file() and _symbol_exists(
        "app.workflows.approval_batch_service",
        "create_approval_batch",
    )


def _rejection_upstream_shipped() -> bool:
    runtime_path = _module_source_path("app.workflows.execution_engine_runtime")
    if runtime_path is None:
        return False
    text = runtime_path.read_text(encoding="utf-8")
    return "route_upstream" in text and "_route_upstream_on_reject" in text


def _pack_pricing_framework_shipped() -> bool:
    return (
        _symbol_exists("app.marketplace.pack_pricing", "validate_department_pack_pricing")
        and PACK_TIER_MIGRATION.is_file()
        and ONE_TIME_PRICING_MIGRATION.is_file()
    )


def _one_time_entitlement_shipped() -> bool:
    entitlements_path = _module_source_path("app.marketplace.entitlements")
    if entitlements_path is None:
        return False
    text = entitlements_path.read_text(encoding="utf-8")
    return "assert_install_entitlement" in text and 'mode = "subscription"' in text and '"payment"' in text


def _mode_ab_toggle_shipped() -> bool:
    return MODE_B_MIGRATION.is_file() and _symbol_exists(
        "app.services.mode_b_feedback_service",
        "set_feedback_mode",
    )


def _linkedin_publish_missing() -> bool:
    from app.marketplace.marketing_pack_connector_gaps import audit_marketing_pack_connectors

    report = audit_marketing_pack_connectors()
    by_key = {row["key"]: row for row in report["connectors"]}
    linkedin = by_key.get("linkedin_publish") or {}
    return linkedin.get("liveState") in {"missing", "partial"}


def _tier_eligibility_at_checkout() -> bool:
    entitlements_path = _module_source_path("app.marketplace.entitlements")
    if entitlements_path is None:
        return False
    text = entitlements_path.read_text(encoding="utf-8")
    markers = (
        "platform_tier",
        "Control",
        "Command",
        "assert_platform_tier",
        "pack_tier_eligibility",
    )
    checkout_fn = text.split("def create_asset_checkout_session", 1)
    if len(checkout_fn) < 2:
        return False
    body = checkout_fn[1].split("\ndef ", 1)[0]
    return any(marker in body for marker in markers)


def _resolve_live_state(cap: ReusabilityCapability) -> ReusabilityState:
    if cap.key == "graph_handoff_agent_chains":
        return "exists" if _department_pack_handoff_shipped() else "missing"

    if cap.key == "batch_partial_approval":
        if not _batch_partial_approval_shipped():
            return "missing"
        return "partial"

    if cap.key == "rejection_upstream_routing":
        return "partial" if _rejection_upstream_shipped() else "missing"

    if cap.key == "pack_tier_pricing_framework":
        return "exists" if _pack_pricing_framework_shipped() else "missing"

    if cap.key == "one_time_entitlement_path":
        return "exists" if _one_time_entitlement_shipped() else "partial"

    if cap.key == "mode_ab_feedback_toggle":
        return "exists" if _mode_ab_toggle_shipped() else "partial"

    if cap.key == "linkedin_publish_connector":
        return "partial" if _linkedin_publish_missing() else "exists"

    if cap.key == "tier_eligibility_checkout_gating":
        return "exists" if _tier_eligibility_at_checkout() else "missing"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        return cap.audit_state

    return cap.audit_state


def audit_marketing_pack_reusability() -> dict[str, Any]:
    """Return STA-299 reusability checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0
    future_pack_blockers: list[str] = []

    for cap in ALL_REUSABILITY_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1

        if cap.blocks_future_packs == "yes" and live_state != "exists":
            future_pack_blockers.append(cap.key)

        rows.append(
            {
                "key": cap.key,
                "displayName": cap.display_name,
                "reuseScope": cap.reuse_scope,
                "documentedState": cap.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == cap.audit_state,
                "complexity": cap.complexity,
                "blocksFuturePacks": cap.blocks_future_packs,
                "notes": cap.notes,
            }
        )

    general_rows = [row for row in rows if row["reuseScope"] == "general"]
    marketing_rows = [row for row in rows if row["reuseScope"] == "marketing_specific"]
    uncertainty_rows = [row for row in rows if row["reuseScope"] == "open_uncertainty"]

    general_ready = all(row["liveState"] == "exists" for row in general_rows)

    return {
        "issue": "STA-299",
        "packSlug": MARKETING_PACK_SLUG,
        "relatedIssues": ["STA-290", "STA-293", "STA-292", "STA-294", "STA-297"],
        "recommendation": (
            "Reuse general primitives (department_pack type, tier pricing, entitlements, Mode A/B toggle) "
            "for next department packs; finish batch analytics + tier checkout gating before HR/Finance packs "
            "at scale; keep LinkedIn publish and post-publish metrics as marketing-first extensions"
        ),
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "generalPrimitiveCount": len(general_rows),
            "generalPrimitivesReady": general_ready,
            "futurePackBlockers": future_pack_blockers,
            "tierEligibilityCheckoutMissing": not _tier_eligibility_at_checkout(),
            "batchPartialApprovalPartial": _batch_partial_approval_shipped(),
            "modeAbToggleShipped": _mode_ab_toggle_shipped(),
            "packPricingFrameworkShipped": _pack_pricing_framework_shipped(),
            "nextPackReady": len(future_pack_blockers) == 0,
        },
        "generalPrimitives": general_rows,
        "marketingSpecific": marketing_rows,
        "openUncertainties": uncertainty_rows,
        "capabilities": rows,
    }
