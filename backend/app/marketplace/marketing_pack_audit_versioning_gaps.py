"""STA-296 / MKT-PACK-AUDIT 7.2: Marketing pack audit immutability + pack rollback/versioning audit."""
from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

AuditVersioningState = Literal["exists", "partial", "missing"]
PackBlocker = Literal["yes", "no", "depends"]
CapabilityCategory = Literal["audit_immutability", "pack_versioning"]

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_IMMUTABILITY_MIGRATION = (
    REPO_ROOT / "supabase" / "migrations" / "20260708130000_audit_retention_and_immutability.sql"
)
RETENTION_PURGE_SCRIPT = REPO_ROOT / "backend" / "scripts" / "retention_purge.py"
MARKETING_PACK_SLUG = "marketing-operations-pack"


@dataclass(frozen=True)
class AuditVersioningCapability:
    key: str
    display_name: str
    category: CapabilityCategory
    audit_state: AuditVersioningState
    complexity: Literal["low", "medium", "high"]
    blocks_pack: PackBlocker
    compliance_blocker: bool
    notes: str
    module_path: str | None = None
    symbol: str | None = None


AUDIT_IMMUTABILITY_CAPABILITIES: tuple[AuditVersioningCapability, ...] = (
    AuditVersioningCapability(
        key="audit_immutability_migration",
        display_name="Audit retention + member read-only RLS migration",
        category="audit_immutability",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        compliance_blocker=False,
        notes="20260708130000_audit_retention_and_immutability.sql aligns purge + SELECT-only member RLS.",
    ),
    AuditVersioningCapability(
        key="audit_logs_member_read_only",
        display_name="audit_logs member read-only (no client writes)",
        category="audit_immutability",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        compliance_blocker=False,
        notes="audit_logs_org_read policy; service role still writes via write_audit_event.",
        module_path="app.workflows.audit",
        symbol="write_audit_event",
    ),
    AuditVersioningCapability(
        key="audit_events_member_read_only",
        display_name="audit_events member read-only (no client writes)",
        category="audit_immutability",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        compliance_blocker=False,
        notes="audit_events_org_read policy in STA-274 migration.",
    ),
    AuditVersioningCapability(
        key="retention_purge_rpc",
        display_name="Retention purge RPC (explicit org-scoped runner)",
        category="audit_immutability",
        audit_state="partial",
        complexity="medium",
        blocks_pack="no",
        compliance_blocker=True,
        notes="retention_purge() deletes aged audit_events and audit_logs; not append-only forever.",
        module_path="backend.scripts.retention_purge",
        symbol="main",
    ),
    AuditVersioningCapability(
        key="approval_trail_append_only",
        display_name="Approval/audit trail append-only (no aged deletion)",
        category="audit_immutability",
        audit_state="missing",
        complexity="high",
        blocks_pack="depends",
        compliance_blocker=True,
        notes="Compliance-heavy approval trails still subject to retention_purge deletion window.",
    ),
)

PACK_VERSIONING_CAPABILITIES: tuple[AuditVersioningCapability, ...] = (
    AuditVersioningCapability(
        key="marketplace_asset_version_history",
        display_name="Per-asset marketplace version history",
        category="pack_versioning",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        compliance_blocker=False,
        notes="marketplace_asset_versions + list_asset_versions for org-owned assets.",
        module_path="app.marketplace.versions",
        symbol="list_asset_versions",
    ),
    AuditVersioningCapability(
        key="marketplace_asset_rollback",
        display_name="Per-asset marketplace rollback API",
        category="pack_versioning",
        audit_state="partial",
        complexity="medium",
        blocks_pack="no",
        compliance_blocker=False,
        notes="rollback_asset_version restores config snapshot; POST /api/marketplace/assets/{ref}/rollback.",
        module_path="app.marketplace.versions",
        symbol="rollback_asset_version",
    ),
    AuditVersioningCapability(
        key="department_pack_multi_entity_install",
        display_name="Department pack install (agents + workflow + RAG)",
        category="pack_versioning",
        audit_state="partial",
        complexity="medium",
        blocks_pack="no",
        compliance_blocker=False,
        notes="_install_department_pack creates multiple entities without coordinated snapshot.",
        module_path="app.marketplace.service",
        symbol="_install_department_pack",
    ),
    AuditVersioningCapability(
        key="pack_coordinated_rollback",
        display_name="Coordinated pack-level rollback (multi-entity)",
        category="pack_versioning",
        audit_state="missing",
        complexity="high",
        blocks_pack="depends",
        compliance_blocker=False,
        notes="No rollback_department_pack_install or install snapshot primitive for marketing pack.",
    ),
    AuditVersioningCapability(
        key="pack_install_entity_snapshot",
        display_name="Pack install entity snapshot for rollback",
        category="pack_versioning",
        audit_state="missing",
        complexity="medium",
        blocks_pack="depends",
        compliance_blocker=False,
        notes="Install records entity IDs but no versioned snapshot of all pack entities for restore.",
    ),
)

ALL_AUDIT_VERSIONING_CAPABILITIES = AUDIT_IMMUTABILITY_CAPABILITIES + PACK_VERSIONING_CAPABILITIES


def _module_loaded(module_path: str) -> bool:
    return importlib.util.find_spec(module_path) is not None


def _symbol_exists(module_path: str, symbol: str) -> bool:
    if not _module_loaded(module_path):
        return False
    module = importlib.import_module(module_path)
    return getattr(module, symbol, None) is not None


def _audit_immutability_migration_exists() -> bool:
    if not AUDIT_IMMUTABILITY_MIGRATION.is_file():
        return False
    text = AUDIT_IMMUTABILITY_MIGRATION.read_text(encoding="utf-8")
    return "audit_logs_org_read" in text and "audit_events_org_read" in text


def _retention_purge_deletes_audit_rows() -> bool:
    if AUDIT_IMMUTABILITY_MIGRATION.is_file():
        text = AUDIT_IMMUTABILITY_MIGRATION.read_text(encoding="utf-8")
        if "DELETE FROM public.audit_events" in text and "DELETE FROM public.audit_logs" in text:
            return True
    if RETENTION_PURGE_SCRIPT.is_file():
        text = RETENTION_PURGE_SCRIPT.read_text(encoding="utf-8")
        return "retention_purge" in text
    return False


def _department_pack_install_is_multi_entity() -> bool:
    from app.marketplace import service as module

    source = inspect.getsource(module._install_department_pack)
    return "_install_ai_agent" in source and "_install_workflow_entity" in source


def _pack_coordinated_rollback_shipped() -> bool:
    from app.marketplace import service as module

    source = inspect.getsource(module)
    markers = (
        "rollback_department_pack",
        "rollback_pack_install",
        "pack_install_snapshot",
        "coordinated_pack_rollback",
    )
    return any(marker in source for marker in markers)


def _resolve_live_state(cap: AuditVersioningCapability) -> AuditVersioningState:
    if cap.key == "audit_immutability_migration":
        return "exists" if _audit_immutability_migration_exists() else "missing"

    if cap.key == "audit_logs_member_read_only":
        if not _audit_immutability_migration_exists():
            return "missing"
        if _symbol_exists("app.workflows.audit", "write_audit_event"):
            return "partial"
        return "missing"

    if cap.key == "audit_events_member_read_only":
        return "partial" if _audit_immutability_migration_exists() else "missing"

    if cap.key == "retention_purge_rpc":
        if _retention_purge_deletes_audit_rows() and RETENTION_PURGE_SCRIPT.is_file():
            return "partial"
        return "missing"

    if cap.key == "approval_trail_append_only":
        if _retention_purge_deletes_audit_rows():
            return "missing"
        return "partial"

    if cap.key == "department_pack_multi_entity_install":
        return "partial" if _department_pack_install_is_multi_entity() else "missing"

    if cap.key in {"pack_coordinated_rollback", "pack_install_entity_snapshot"}:
        return "exists" if _pack_coordinated_rollback_shipped() else "missing"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        return cap.audit_state

    return cap.audit_state


def audit_marketing_pack_audit_versioning() -> dict[str, Any]:
    """Return STA-296 checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0
    pack_blockers: list[str] = []
    compliance_blockers: list[str] = []

    for cap in ALL_AUDIT_VERSIONING_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1

        if cap.blocks_pack == "yes" and live_state != "exists":
            pack_blockers.append(cap.key)

        if cap.compliance_blocker and live_state in {"missing", "partial"}:
            compliance_blockers.append(cap.key)

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
                "complianceBlocker": cap.compliance_blocker,
                "notes": cap.notes,
            }
        )

    immutability_rows = [row for row in rows if row["category"] == "audit_immutability"]
    versioning_rows = [row for row in rows if row["category"] == "pack_versioning"]

    return {
        "issue": "STA-296",
        "packSlug": MARKETING_PACK_SLUG,
        "relatedIssues": ["STA-274", "STA-290", "STA-293"],
        "recommendation": (
            "v1: rely on per-asset marketplace rollback + member read-only audit RLS; "
            "defer coordinated pack rollback and append-only compliance until product requires it"
        ),
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "packBlockers": pack_blockers,
            "complianceBlockers": compliance_blockers,
            "auditImmutabilityMigrationShipped": _audit_immutability_migration_exists(),
            "retentionPurgeDeletesAuditRows": _retention_purge_deletes_audit_rows(),
            "perAssetRollbackShipped": _symbol_exists(
                "app.marketplace.versions",
                "rollback_asset_version",
            ),
            "packCoordinatedRollbackMissing": not _pack_coordinated_rollback_shipped(),
            "v1Ready": len(pack_blockers) == 0,
            "complianceHeavyApprovalTrailsBlocked": bool(compliance_blockers),
        },
        "auditImmutability": immutability_rows,
        "packVersioning": versioning_rows,
        "capabilities": rows,
    }
