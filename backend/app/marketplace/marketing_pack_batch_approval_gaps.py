"""STA-290 / MKT-PACK-AUDIT 5.2: Marketing pack batch + partial approval audit."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BatchApprovalState = Literal["exists", "partial", "missing"]
PackBlocker = Literal["yes", "no", "depends"]
CapabilityCategory = Literal["data_model", "runtime", "ui", "routing", "analytics"]

REPO_ROOT = Path(__file__).resolve().parents[3]
APPROVAL_BATCH_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260709140000_approval_batches.sql"
BATCH_UI_COMPONENT = REPO_ROOT / "apps" / "web" / "components" / "runs" / "approval-batch-panel.tsx"
MARKETING_PACK_SLUG = "marketing-operations-pack"


@dataclass(frozen=True)
class BatchApprovalCapability:
    key: str
    display_name: str
    category: CapabilityCategory
    audit_state: BatchApprovalState
    complexity: Literal["low", "medium", "high"]
    blocks_pack: PackBlocker
    notes: str
    module_path: str | None = None
    symbol: str | None = None


BATCH_APPROVAL_CAPABILITIES: tuple[BatchApprovalCapability, ...] = (
    BatchApprovalCapability(
        key="approval_batch_schema",
        display_name="Approval batch + per-item decision schema",
        category="data_model",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="approval_batches + approval_batch_items (20260709140000).",
    ),
    BatchApprovalCapability(
        key="approval_batch_service",
        display_name="Batch grouping + partial approve/reject service",
        category="data_model",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="create_approval_batch, apply_batch_decisions, summarize_batch_items.",
        module_path="app.workflows.approval_batch_service",
        symbol="create_approval_batch",
    ),
    BatchApprovalCapability(
        key="partial_item_decisions",
        display_name="Partial approve/reject within batch",
        category="runtime",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="Per-item approved/rejected status with optional reject_comment.",
        module_path="app.workflows.approval_batch_service",
        symbol="apply_batch_decisions",
    ),
    BatchApprovalCapability(
        key="batch_runtime_selective_resume",
        display_name="Selective re-entry after batch resolution",
        category="runtime",
        audit_state="partial",
        complexity="high",
        blocks_pack="depends",
        notes="resolve_approval_batch_and_resume resumes approved items; full UI polish ongoing.",
        module_path="app.workflows.execution_engine_runtime",
        symbol="resolve_approval_batch_and_resume",
    ),
    BatchApprovalCapability(
        key="batch_approval_api",
        display_name="Workflow run batch approval API",
        category="runtime",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="GET/POST /api/workflows/runs/{id}/approval-batch.",
        module_path="app.routers.workflows",
        symbol="decide_run_approval_batch",
    ),
    BatchApprovalCapability(
        key="batch_approval_ui",
        display_name="Batch approval UI (partial-select panel)",
        category="ui",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="ApprovalBatchPanel on run detail page with per-item approve/reject.",
    ),
    BatchApprovalCapability(
        key="rejection_upstream_routing",
        display_name="Rejection routes to upstream agent (route_upstream)",
        category="routing",
        audit_state="partial",
        complexity="medium",
        blocks_pack="depends",
        notes="on_reject=route_upstream + reject_route_node_id in execution_engine_runtime.",
        module_path="app.workflows.execution_engine_runtime",
        symbol="_route_upstream_on_reject",
    ),
    BatchApprovalCapability(
        key="partial_batch_analytics",
        display_name="Partial batch outcomes in analytics",
        category="analytics",
        audit_state="missing",
        complexity="medium",
        blocks_pack="no",
        notes="No analytics schema for batch item outcomes (STA-297).",
    ),
)

ALL_BATCH_APPROVAL_CAPABILITIES = BATCH_APPROVAL_CAPABILITIES


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


def _approval_batch_migration_exists() -> bool:
    if not APPROVAL_BATCH_MIGRATION.is_file():
        return False
    text = APPROVAL_BATCH_MIGRATION.read_text(encoding="utf-8")
    return "approval_batches" in text and "approval_batch_items" in text


def _batch_ui_shipped() -> bool:
    if not BATCH_UI_COMPONENT.is_file():
        return False
    text = BATCH_UI_COMPONENT.read_text(encoding="utf-8")
    return "ApprovalBatchPanel" in text and "itemKey" in text


def _rejection_upstream_shipped() -> bool:
    runtime_path = _module_source_path("app.workflows.execution_engine_runtime")
    if runtime_path is None:
        return False
    text = runtime_path.read_text(encoding="utf-8")
    return "route_upstream" in text and "_route_upstream_on_reject" in text


def _partial_batch_analytics_shipped() -> bool:
    migrations_dir = REPO_ROOT / "supabase" / "migrations"
    if not migrations_dir.is_dir():
        return False
    for path in migrations_dir.glob("*.sql"):
        text = path.read_text(encoding="utf-8").lower()
        if "batch_outcome" in text or "approval_batch_analytics" in text:
            return True
    return False


def _resolve_live_state(cap: BatchApprovalCapability) -> BatchApprovalState:
    if cap.key == "approval_batch_schema":
        return "exists" if _approval_batch_migration_exists() else "missing"

    if cap.key == "batch_approval_ui":
        return "exists" if _batch_ui_shipped() else "missing"

    if cap.key == "rejection_upstream_routing":
        return "partial" if _rejection_upstream_shipped() else "missing"

    if cap.key == "partial_batch_analytics":
        return "exists" if _partial_batch_analytics_shipped() else "missing"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        return cap.audit_state

    return cap.audit_state


def audit_marketing_pack_batch_approval() -> dict[str, Any]:
    """Return STA-290 checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0
    pack_blockers: list[str] = []

    for cap in ALL_BATCH_APPROVAL_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1

        if cap.blocks_pack == "yes" and live_state != "exists":
            pack_blockers.append(cap.key)

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
                "notes": cap.notes,
            }
        )

    return {
        "issue": "STA-290",
        "packSlug": MARKETING_PACK_SLUG,
        "relatedIssues": ["STA-297", "STA-299"],
        "recommendation": (
            "v1: batch schema, service, API, and UI are shipped; upstream routing is partial; "
            "defer partial-batch analytics until STA-289/297 measurement path"
        ),
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "packBlockers": pack_blockers,
            "approvalBatchSchemaShipped": _approval_batch_migration_exists(),
            "batchApprovalUiShipped": _batch_ui_shipped(),
            "rejectionUpstreamPartial": _rejection_upstream_shipped(),
            "partialBatchAnalyticsMissing": not _partial_batch_analytics_shipped(),
            "v1Ready": len(pack_blockers) == 0,
            "runtimeShipped": _approval_batch_migration_exists()
            and _symbol_exists("app.workflows.approval_batch_service", "create_approval_batch"),
        },
        "dataModel": [row for row in rows if row["category"] == "data_model"],
        "runtime": [row for row in rows if row["category"] == "runtime"],
        "ui": [row for row in rows if row["category"] == "ui"],
        "routing": [row for row in rows if row["category"] == "routing"],
        "analytics": [row for row in rows if row["category"] == "analytics"],
        "capabilities": rows,
    }
