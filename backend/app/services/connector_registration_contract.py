"""Allowlist-driven registration contract — shrink tracker for connector governance debt.

Each allowlist names known debt explicitly. Contract checks fail when:
- debt appears outside its allowlist (new unmanaged item), or
- an allowlist entry is stale (debt fixed but the name was not removed).

Removing an entry from an allowlist is a unit of progress; fix the underlying issue
in the same change so tests stay green.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.registry import all_catalog_action_specs, get_action_spec
from app.connectors.action_catalog.tool_aliases import (
    REGISTRY_VENDOR_PREFIX_ALIASES,
    resolve_registry_action,
)
from app.services.connector_allowlists import (
    API_IMPORT_EXCEPTION_ALLOWLIST,
    ORPHAN_HANDLER_ALLOWLIST,
    PENDING_WORKFLOW_SCHEMA_ALLOWLIST,
)
from app.services.connector_api_import_boundaries import _extract_api_imports
from app.services.tool_service import list_registered_actions

DebtKind = Literal["orphan_handler", "api_import_exception", "pending_workflow_schema"]

_REGISTRY_PREFIX_TO_CATALOG_VENDOR = {
    alias_prefix: catalog_vendor
    for catalog_vendor, alias_prefix in REGISTRY_VENDOR_PREFIX_ALIASES.items()
}

# Scoped pytest targets for merge-blocking connector governance CI (Step 2).
CONNECTOR_GOVERNANCE_PYTEST_TARGETS: tuple[str, ...] = (
    "tests/services/test_connector_registration_contract.py",
    "tests/services/test_connector_registry_verification.py",
    "tests/services/test_connector_api_import_boundaries.py",
    "tests/services/test_connector_action_workflows.py",
    "tests/services/test_connector_parameter_inference.py",
    "tests/services/test_action_workflow_validation.py",
    "tests/services/test_connector_capability_analysis.py",
    "tests/services/test_connector_session_state.py",
    "tests/services/test_chat_connector_execution.py",
    "tests/services/test_chat_orchestration.py",
    "tests/services/test_workflow_schemas_batch_25.py",
    "tests/services/test_workflow_schemas_batch_50.py",
    "tests/services/test_workflow_schemas_batch_75.py",
    "tests/services/test_workflow_schemas_batch_100.py",
    "tests/smoke/test_connector_action_smoke.py",
)


@dataclass(frozen=True)
class AllowlistBucket:
    kind: DebtKind
    label: str
    allowlist: frozenset[str]
    actual: frozenset[str]

    @property
    def stale_entries(self) -> frozenset[str]:
        return frozenset(self.allowlist - self.actual)

    @property
    def unmanaged_debt(self) -> frozenset[str]:
        return frozenset(self.actual - self.allowlist)

    @property
    def is_exact_match(self) -> bool:
        return not self.stale_entries and not self.unmanaged_debt

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "allowlistCount": len(self.allowlist),
            "actualCount": len(self.actual),
            "remaining": len(self.allowlist),
            "staleEntries": sorted(self.stale_entries),
            "unmanagedDebt": sorted(self.unmanaged_debt),
            "isExactMatch": self.is_exact_match,
        }


def _catalog_key_for_registered_action(action_key: str) -> str | None:
    if get_action_spec(action_key):
        return action_key
    if "." not in action_key:
        return None
    vendor, rest = action_key.split(".", 1)
    catalog_vendor = _REGISTRY_PREFIX_TO_CATALOG_VENDOR.get(vendor)
    if not catalog_vendor:
        return None
    candidate = f"{catalog_vendor}.{rest}"
    if get_action_spec(candidate):
        return candidate
    return None


def collect_orphan_handlers() -> frozenset[str]:
    """Registered invoke_tool handlers with no catalog entry (aliases excluded)."""
    registered = set(list_registered_actions())
    orphans: set[str] = set()
    for action_key in registered:
        if "." not in action_key:
            continue
        if _catalog_key_for_registered_action(action_key):
            continue
        orphans.add(action_key)
    return frozenset(orphans)


def collect_api_import_exceptions() -> frozenset[str]:
    """Non-execution modules still importing raw connector *_api clients."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    exceptions: set[str] = set()
    for relative_path in API_IMPORT_EXCEPTION_ALLOWLIST:
        path = repo_root / relative_path
        if not path.exists():
            continue
        if _extract_api_imports(path):
            exceptions.add(relative_path)
    return frozenset(exceptions)


def collect_pending_workflow_schemas() -> frozenset[str]:
    """Catalog write actions without a declarative workflow schema."""
    pending: set[str] = set()
    for spec in all_catalog_action_specs():
        if spec.kind != "write":
            continue
        if get_workflow_schema(spec.id):
            continue
        pending.add(spec.id)
    return frozenset(pending)


def collect_migrated_workflow_schema_gaps() -> frozenset[str]:
    """Write actions removed from pending allowlist but still missing workflow_schema."""
    gaps: set[str] = set()
    for spec in all_catalog_action_specs():
        if spec.kind != "write":
            continue
        if spec.id in PENDING_WORKFLOW_SCHEMA_ALLOWLIST:
            continue
        if get_workflow_schema(spec.id):
            continue
        gaps.add(spec.id)
    return frozenset(gaps)


def verify_registration_contract() -> list[AllowlistBucket]:
    return [
        AllowlistBucket(
            kind="orphan_handler",
            label="Registered handlers without catalog entries",
            allowlist=ORPHAN_HANDLER_ALLOWLIST,
            actual=collect_orphan_handlers(),
        ),
        AllowlistBucket(
            kind="api_import_exception",
            label="Modules importing raw connector API clients outside executors",
            allowlist=API_IMPORT_EXCEPTION_ALLOWLIST,
            actual=collect_api_import_exceptions(),
        ),
        AllowlistBucket(
            kind="pending_workflow_schema",
            label="Write actions pending workflow_schema migration",
            allowlist=PENDING_WORKFLOW_SCHEMA_ALLOWLIST,
            actual=collect_pending_workflow_schemas(),
        ),
    ]


def registration_contract_summary() -> dict[str, Any]:
    buckets = verify_registration_contract()
    migrated_gaps = collect_migrated_workflow_schema_gaps()
    by_kind = {bucket.kind: bucket.to_dict() for bucket in buckets}
    pending = by_kind["pending_workflow_schema"]
    return {
        "buckets": by_kind,
        "orphanHandlersRemaining": by_kind["orphan_handler"]["allowlistCount"],
        "apiImportExceptionsRemaining": by_kind["api_import_exception"]["allowlistCount"],
        "pendingWorkflowSchemaRemaining": pending["allowlistCount"],
        "pendingWorkflowSchemaTrendingDownFrom": len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST),
        "migratedWorkflowSchemaGaps": sorted(migrated_gaps),
        "allExactMatches": all(bucket.is_exact_match for bucket in buckets),
    }


def _format_bucket_mismatch(bucket: AllowlistBucket) -> str:
    lines: list[str] = []
    if bucket.stale_entries:
        lines.append(
            f"Stale allowlist entries for {bucket.label} (remove after fixing debt): "
            + ", ".join(sorted(bucket.stale_entries))
        )
    if bucket.unmanaged_debt:
        lines.append(
            f"Unmanaged debt for {bucket.label} (fix debt or add to allowlist): "
            + ", ".join(sorted(bucket.unmanaged_debt))
        )
    return "\n".join(lines)


def assert_registration_contract(
    *,
    enforce_pending_workflow_schema: bool = False,
    enforce_migrated_workflow_schemas: bool = False,
) -> None:
    """Raise AssertionError when allowlist contract is broken.

    Step 1 (default): hard-enforce orphan handlers + API import exceptions.
    Step 3: set enforce_pending_workflow_schema and enforce_migrated_workflow_schemas.
    """
    buckets = verify_registration_contract()
    hard_kinds: set[DebtKind] = {"orphan_handler", "api_import_exception"}
    if enforce_pending_workflow_schema:
        hard_kinds.add("pending_workflow_schema")

    failures: list[str] = []
    for bucket in buckets:
        if bucket.kind in hard_kinds and not bucket.is_exact_match:
            detail = _format_bucket_mismatch(bucket)
            if detail:
                failures.append(detail)

    if enforce_migrated_workflow_schemas:
        gaps = collect_migrated_workflow_schema_gaps()
        if gaps:
            failures.append(
                "Migrated write actions missing workflow_schema (removed from pending allowlist): "
                + ", ".join(sorted(gaps))
            )

    if failures:
        raise AssertionError("Connector registration contract failed:\n" + "\n".join(failures))
