"""STA-297 / MKT-PACK-AUDIT 7.3: Marketing pack usage analytics audit."""
from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

UsageAnalyticsState = Literal["exists", "partial", "missing"]
PackBlocker = Literal["yes", "no", "depends"]
CapabilityCategory = Literal["partial_batch_outcomes", "hours_saved_measurement"]

REPO_ROOT = Path(__file__).resolve().parents[3]
APPROVAL_BATCH_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260709140000_approval_batches.sql"
OUTCOME_LABELS_TS = REPO_ROOT / "apps" / "web" / "lib" / "outcome-labels.ts"
GROUND_TRUTH_ROADMAP = REPO_ROOT / "docs" / "ai" / "GROUND_TRUTH_OUTCOME_ROADMAP.md"
MARKETING_PACK_SLUG = "marketing-operations-pack"


@dataclass(frozen=True)
class UsageAnalyticsCapability:
    key: str
    display_name: str
    category: CapabilityCategory
    audit_state: UsageAnalyticsState
    complexity: Literal["low", "medium", "high"]
    blocks_pack: PackBlocker
    measurement_blocker: bool
    notes: str
    module_path: str | None = None
    symbol: str | None = None


PARTIAL_BATCH_CAPABILITIES: tuple[UsageAnalyticsCapability, ...] = (
    UsageAnalyticsCapability(
        key="approval_batch_schema",
        display_name="Approval batch + per-item decision schema",
        category="partial_batch_outcomes",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        measurement_blocker=False,
        notes="approval_batches + approval_batch_items migration (STA-290).",
    ),
    UsageAnalyticsCapability(
        key="approval_batch_service",
        display_name="Batch grouping + partial approve/reject service",
        category="partial_batch_outcomes",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        measurement_blocker=False,
        notes="create_approval_batch, decide_batch_items, get_active_batch_for_run.",
        module_path="app.workflows.approval_batch_service",
        symbol="create_approval_batch",
    ),
    UsageAnalyticsCapability(
        key="batch_approval_runtime",
        display_name="In-graph batch approval pause + selective resume",
        category="partial_batch_outcomes",
        audit_state="partial",
        complexity="medium",
        blocks_pack="no",
        measurement_blocker=False,
        notes="resolve_approval_batch_and_resume resumes approved items only.",
        module_path="app.workflows.execution_engine_runtime",
        symbol="resolve_approval_batch_and_resume",
    ),
    UsageAnalyticsCapability(
        key="batch_approval_api",
        display_name="Workflow run batch approval API",
        category="partial_batch_outcomes",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        measurement_blocker=False,
        notes="GET/POST approval batch on workflow runs in workflows router.",
        module_path="app.routers.workflows",
        symbol="decide_run_approval_batch",
    ),
    UsageAnalyticsCapability(
        key="partial_batch_analytics_schema",
        display_name="Partial batch outcome analytics schema",
        category="partial_batch_outcomes",
        audit_state="missing",
        complexity="medium",
        blocks_pack="no",
        measurement_blocker=True,
        notes="No analytics table/event type for per-item approved/rejected batch outcomes.",
    ),
    UsageAnalyticsCapability(
        key="partial_batch_adoption_attribution",
        display_name="Partial batch outcomes in marketplace adoption",
        category="partial_batch_outcomes",
        audit_state="missing",
        complexity="medium",
        blocks_pack="no",
        measurement_blocker=True,
        notes="Adoption records full workflow_run completion only; partial batches not attributed.",
        module_path="app.marketplace.adoption",
        symbol="record_adoption_for_workflow_run",
    ),
    UsageAnalyticsCapability(
        key="partial_batch_outcome_reporting",
        display_name="Partial batch outcome reporting API/dashboard",
        category="partial_batch_outcomes",
        audit_state="missing",
        complexity="medium",
        blocks_pack="no",
        measurement_blocker=False,
        notes="No marketplace/workforce analytics endpoint aggregates batch item decisions.",
    ),
)

HOURS_SAVED_CAPABILITIES: tuple[UsageAnalyticsCapability, ...] = (
    UsageAnalyticsCapability(
        key="catalog_estimated_hours_saved",
        display_name="Catalog estimated_hours_saved on marketplace assets",
        category="hours_saved_measurement",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        measurement_blocker=False,
        notes="Publisher metadata column used by browse, seed, and ROI dashboard.",
        module_path="app.marketplace.roi",
        symbol="marketplace_roi_summary",
    ),
    UsageAnalyticsCapability(
        key="roi_adopted_estimate_heuristic",
        display_name="ROI realized hours (adopted estimate heuristic)",
        category="hours_saved_measurement",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        measurement_blocker=True,
        notes="realizedHoursSaved copies catalog estimate when usageEvents > 0; not measured time-on-task.",
        module_path="app.marketplace.roi",
        symbol="marketplace_roi_summary",
    ),
    UsageAnalyticsCapability(
        key="outcome_estimate_labeling_ui",
        display_name="Estimate vs operational labeling (STA-286)",
        category="hours_saved_measurement",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        measurement_blocker=False,
        notes="outcome-labels.ts + ROI methodology callouts distinguish estimates from operational counts.",
    ),
    UsageAnalyticsCapability(
        key="ground_truth_hours_measurement",
        display_name="Ground-truth measured hours saved (STA-289)",
        category="hours_saved_measurement",
        audit_state="missing",
        complexity="high",
        blocks_pack="depends",
        measurement_blocker=True,
        notes="Time-on-task / before-after measurement path deferred; agent_action_outcomes is correlational.",
    ),
    UsageAnalyticsCapability(
        key="measured_vs_estimate_roi_api",
        display_name="Measured vs estimate distinction in ROI API",
        category="hours_saved_measurement",
        audit_state="missing",
        complexity="medium",
        blocks_pack="depends",
        measurement_blocker=True,
        notes="marketplace_roi_summary lacks measuredHoursSaved / provenance fields separate from estimates.",
        module_path="app.marketplace.roi",
        symbol="marketplace_roi_summary",
    ),
    UsageAnalyticsCapability(
        key="pack_hours_saved_provenance",
        display_name="Pack-level hours-saved provenance in analytics",
        category="hours_saved_measurement",
        audit_state="partial",
        complexity="medium",
        blocks_pack="no",
        measurement_blocker=True,
        notes="UI labels estimates; pack install ROI still aggregates catalog metadata without pack scope.",
    ),
)

ALL_USAGE_ANALYTICS_CAPABILITIES = PARTIAL_BATCH_CAPABILITIES + HOURS_SAVED_CAPABILITIES


def _module_loaded(module_path: str) -> bool:
    return importlib.util.find_spec(module_path) is not None


def _module_source_path(module_path: str) -> Path | None:
    relative = module_path.replace(".", "/") + ".py"
    candidate = REPO_ROOT / "backend" / relative
    return candidate if candidate.is_file() else None


def _symbol_exists(module_path: str, symbol: str) -> bool:
    source_path = _module_source_path(module_path)
    if source_path is not None:
        text = source_path.read_text(encoding="utf-8")
        return f"def {symbol}" in text or f"class {symbol}" in text or f"async def {symbol}" in text
    if not _module_loaded(module_path):
        return False
    module = importlib.import_module(module_path)
    return getattr(module, symbol, None) is not None


def _approval_batch_migration_exists() -> bool:
    if not APPROVAL_BATCH_MIGRATION.is_file():
        return False
    text = APPROVAL_BATCH_MIGRATION.read_text(encoding="utf-8")
    return "approval_batches" in text and "approval_batch_items" in text


def _partial_batch_analytics_schema_shipped() -> bool:
    migrations_dir = REPO_ROOT / "supabase" / "migrations"
    if not migrations_dir.is_dir():
        return False
    markers = (
        "batch_outcome",
        "approval_batch_analytics",
        "partial_batch_outcome",
        "batch_item_outcome",
    )
    for path in migrations_dir.glob("*.sql"):
        text = path.read_text(encoding="utf-8").lower()
        if any(marker in text for marker in markers):
            return True
    return False


def _partial_batch_adoption_wired() -> bool:
    from app.marketplace import adoption as module

    source = inspect.getsource(module)
    markers = (
        "approval_batch",
        "batch_item",
        "partial_batch",
        "approved_items",
    )
    return any(marker in source for marker in markers)


def _partial_batch_reporting_shipped() -> bool:
    router_path = REPO_ROOT / "backend" / "app" / "routers" / "marketplace.py"
    if not router_path.is_file():
        return False
    text = router_path.read_text(encoding="utf-8")
    return "batch_outcome" in text or "approval_batch" in text and "analytics" in text


def _outcome_estimate_labeling_shipped() -> bool:
    if not OUTCOME_LABELS_TS.is_file():
        return False
    text = OUTCOME_LABELS_TS.read_text(encoding="utf-8")
    return "ESTIMATED_HOURS_SAVED_LABEL" in text and "OutcomeMeasurementKind" in text


def _ground_truth_hours_measurement_shipped() -> bool:
    if GROUND_TRUTH_ROADMAP.is_file():
        text = GROUND_TRUTH_ROADMAP.read_text(encoding="utf-8")
        if "- [x]" in text and "measured" in text.lower():
            return True
    roi_path = REPO_ROOT / "backend" / "app" / "marketplace" / "roi.py"
    if roi_path.is_file():
        text = roi_path.read_text(encoding="utf-8")
        if "measured_hours_saved" in text or "measuredHoursSaved" in text:
            return True
    return False


def _roi_has_measured_vs_estimate_fields() -> bool:
    roi_path = REPO_ROOT / "backend" / "app" / "marketplace" / "roi.py"
    if not roi_path.is_file():
        return False
    text = roi_path.read_text(encoding="utf-8")
    return "measuredHoursSaved" in text or "measurementKind" in text or "provenance" in text


def _roi_realized_is_estimate_heuristic() -> bool:
    roi_path = REPO_ROOT / "backend" / "app" / "marketplace" / "roi.py"
    if not roi_path.is_file():
        return False
    text = roi_path.read_text(encoding="utf-8")
    return "realizedHoursSaved" in text and "estimated_hours_saved" in text


def _pack_hours_provenance_in_analytics() -> bool:
    support_path = REPO_ROOT / "backend" / "app" / "marketplace" / "support.py"
    if support_path.is_file():
        text = support_path.read_text(encoding="utf-8")
        if "measurementKind" in text or "hoursSavedProvenance" in text:
            return True
    return _outcome_estimate_labeling_shipped() and not _roi_has_measured_vs_estimate_fields()


def _resolve_live_state(cap: UsageAnalyticsCapability) -> UsageAnalyticsState:
    if cap.key == "approval_batch_schema":
        return "exists" if _approval_batch_migration_exists() else "missing"

    if cap.key == "partial_batch_analytics_schema":
        return "exists" if _partial_batch_analytics_schema_shipped() else "missing"

    if cap.key == "partial_batch_adoption_attribution":
        if _partial_batch_adoption_wired():
            return "exists"
        if _symbol_exists("app.marketplace.adoption", "record_adoption_for_workflow_run"):
            return "missing"
        return "missing"

    if cap.key == "partial_batch_outcome_reporting":
        return "exists" if _partial_batch_reporting_shipped() else "missing"

    if cap.key == "outcome_estimate_labeling_ui":
        return "exists" if _outcome_estimate_labeling_shipped() else "missing"

    if cap.key == "ground_truth_hours_measurement":
        return "exists" if _ground_truth_hours_measurement_shipped() else "missing"

    if cap.key == "measured_vs_estimate_roi_api":
        return "exists" if _roi_has_measured_vs_estimate_fields() else "missing"

    if cap.key == "roi_adopted_estimate_heuristic":
        if not _symbol_exists("app.marketplace.roi", "marketplace_roi_summary"):
            return "missing"
        if _roi_realized_is_estimate_heuristic() and not _roi_has_measured_vs_estimate_fields():
            return "partial"
        if _roi_has_measured_vs_estimate_fields():
            return "exists"
        return cap.audit_state

    if cap.key == "pack_hours_saved_provenance":
        if _roi_has_measured_vs_estimate_fields():
            return "exists"
        if _outcome_estimate_labeling_shipped():
            return "partial"
        return "missing"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        return cap.audit_state

    return cap.audit_state


def audit_marketing_pack_usage_analytics() -> dict[str, Any]:
    """Return STA-297 checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0
    pack_blockers: list[str] = []
    measurement_blockers: list[str] = []

    for cap in ALL_USAGE_ANALYTICS_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1

        if cap.blocks_pack == "yes" and live_state != "exists":
            pack_blockers.append(cap.key)

        if cap.measurement_blocker and live_state in {"missing", "partial"}:
            measurement_blockers.append(cap.key)

        rows.append(
            {
                "key": cap.key,
                "displayName": cap.display_name,
                "category": cap.category,
                "documentedState": cap.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == cap.audit_state,
                "complexity": cap.complexity,
                "blocksPack": cap.blocks_pack,
                "measurementBlocker": cap.measurement_blocker,
                "notes": cap.notes,
            }
        )

    partial_batch_rows = [row for row in rows if row["category"] == "partial_batch_outcomes"]
    hours_saved_rows = [row for row in rows if row["category"] == "hours_saved_measurement"]

    return {
        "issue": "STA-297",
        "packSlug": MARKETING_PACK_SLUG,
        "relatedIssues": ["STA-286", "STA-289", "STA-290", "STA-253"],
        "recommendation": (
            "v1: batch approval runtime is shippable; defer partial-batch analytics schema and "
            "measured hours saved until STA-289 ground-truth measurement ships — keep estimate labeling"
        ),
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "packBlockers": pack_blockers,
            "measurementBlockers": measurement_blockers,
            "approvalBatchSchemaShipped": _approval_batch_migration_exists(),
            "partialBatchAnalyticsMissing": not _partial_batch_analytics_schema_shipped(),
            "outcomeEstimateLabelingShipped": _outcome_estimate_labeling_shipped(),
            "measuredHoursSavedMissing": not _ground_truth_hours_measurement_shipped(),
            "roiEstimateOnly": _roi_realized_is_estimate_heuristic()
            and not _roi_has_measured_vs_estimate_fields(),
            "v1Ready": len(pack_blockers) == 0,
            "measuredRoiClaimsBlocked": bool(measurement_blockers),
        },
        "partialBatchOutcomes": partial_batch_rows,
        "hoursSavedMeasurement": hours_saved_rows,
        "capabilities": rows,
    }
