"""End-to-end connector catalog audit — chat, execute, invoke_tool, scopes, tests."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.connectors.action_catalog.action_parameters import (
    ACTION_PARAMETERS,
    parameters_for_action,
    resolve_action_schema,
)
from app.connectors.action_catalog.extensions import ACTION_SCHEMA_EXTENSIONS
from app.connectors.action_catalog.registry import (
    all_catalog_action_specs,
    connector_actions_for_goal_service,
    get_action_spec,
)
from app.connectors.action_catalog.schema_generator import infer_action_schema, normalize_schema
from app.services.agent_tool_permissions import ACTION_REQUIRED_SCOPES
from app.services.chat_tool_bridge import build_dynamic_chat_tool_specs
from app.services.connector_execution_matrix import (
    PRIORITY_CONNECTORS,
    build_connector_execution_matrix,
)
from app.services.connector_registry_verification import registry_violation_summary
from app.services.tool_service import list_registered_actions

SchemaStatus = Literal["override", "extension", "explicit", "inferred", "missing"]
TestStatus = Literal["mock", "live", "none"]
RiskLevel = Literal["low", "medium", "high"]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TESTS_ROOT = _REPO_ROOT / "tests"


@dataclass(frozen=True)
class CatalogAuditRow:
    vendor: str
    action_id: str
    input_schema_status: SchemaStatus
    implementation_status: str
    chat_exposure: bool
    execute_exposure: bool
    oauth_scopes: tuple[str, ...]
    scope_registered: bool
    risk_level: RiskLevel
    approval_required: bool
    multi_step_plans: bool
    structured_results: bool
    test_status: TestStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "action_id": self.action_id,
            "inputSchemaStatus": self.input_schema_status,
            "implementationStatus": self.implementation_status,
            "chatExposure": self.chat_exposure,
            "executeExposure": self.execute_exposure,
            "oauthScopes": list(self.oauth_scopes),
            "scopeRegistered": self.scope_registered,
            "riskLevel": self.risk_level,
            "approvalRequired": self.approval_required,
            "multiStepPlans": self.multi_step_plans,
            "structuredResults": self.structured_results,
            "testStatus": self.test_status,
        }


def schema_source_for_action(action_key: str, *, kind: str, suffix: str) -> SchemaStatus:
    key = action_key.strip()
    if key in ACTION_PARAMETERS:
        return "override"
    if key in ACTION_SCHEMA_EXTENSIONS:
        return "extension"
    spec = get_action_spec(key)
    if spec and spec.input_schema:
        return "explicit"
    schema = resolve_action_schema(key, kind=kind, suffix=suffix, explicit_schema=spec.input_schema if spec else None)
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    if not props:
        return "missing"
    inferred = normalize_schema(infer_action_schema(key, kind=kind))
    if schema == inferred or set(props.keys()) >= set(inferred.get("properties", {}).keys()):
        return "inferred"
    return "inferred"


def _risk_level(*, kind: str, destructive: bool, requires_approval: bool) -> RiskLevel:
    if destructive or requires_approval:
        return "high"
    if kind in {"write", "advanced"}:
        return "medium"
    return "low"


@lru_cache(maxsize=1)
def _test_index() -> dict[str, TestStatus]:
    """Map action keys and vendors to best-known test coverage."""
    index: dict[str, TestStatus] = {}
    if not _TESTS_ROOT.exists():
        return index
    live_markers = re.compile(r"live|integration|prod|oauth|e2e", re.I)
    mock_markers = re.compile(r"mock|patch|MagicMock|AsyncMock", re.I)
    for path in _TESTS_ROOT.rglob("test_*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        is_live = bool(live_markers.search(text) or "live_" in path.name)
        is_mock = bool(mock_markers.search(text))
        status: TestStatus = "live" if is_live else ("mock" if is_mock else "none")
        for match in re.finditer(r"['\"]([a-z][a-z0-9_]*\.[a-z0-9_.]+)['\"]", text):
            action = match.group(1)
            if action.count(".") >= 1:
                prev = index.get(action)
                if prev is None or (status == "live") or (status == "mock" and prev == "none"):
                    index[action] = status
        vendor = path.stem.replace("test_", "").replace("_tools", "").replace("_api", "")
        if vendor and len(vendor) > 2:
            prev = index.get(f"vendor:{vendor}")
            if prev is None or status == "live" or (status == "mock" and prev == "none"):
                index[f"vendor:{vendor}"] = status
    return index


def _test_status_for(action_key: str, vendor: str) -> TestStatus:
    idx = _test_index()
    if action_key in idx and idx[action_key] != "none":
        return idx[action_key]
    vendor_key = f"vendor:{vendor}"
    if vendor_key in idx:
        return idx[vendor_key]
    alias = vendor.replace("_", "")
    for key, status in idx.items():
        if key.startswith("vendor:") and alias in key.replace("vendor:", "").replace("_", ""):
            return status
    return "none"


def _scope_registered(registry_key: str, catalog_scopes: tuple[str, ...]) -> bool:
    if registry_key in ACTION_REQUIRED_SCOPES:
        return True
    if catalog_scopes:
        return True
    return registry_key in list_registered_actions()


def audit_connector_catalog() -> list[CatalogAuditRow]:
    """Audit all catalog actions across chat, execute, invoke_tool, and tests."""
    matrix = {e.action_key: e for e in build_connector_execution_matrix()}
    chat_specs = build_dynamic_chat_tool_specs()
    goal_actions = connector_actions_for_goal_service()
    registered = set(list_registered_actions())
    rows: list[CatalogAuditRow] = []

    for spec in all_catalog_action_specs():
        action_id = spec.id
        vendor = action_id.split(".", 1)[0]
        suffix = action_id.split(".", 1)[-1]
        entry = matrix.get(action_id)
        impl = entry.implementation_status if entry else "not_implemented"
        registry_key = entry.registry_key if entry else action_id
        implemented = impl != "not_implemented" and registry_key in registered

        chat_exposure = bool(
            entry
            and entry.chat_executable
            and entry.tool_registry_key in chat_specs
        )
        goal_suffixes = goal_actions.get(vendor, [])
        action_suffix = suffix.replace(".", "_") if "." in suffix else suffix.split(".")[-1]
        execute_exposure = implemented and (
            action_suffix in goal_suffixes or suffix in goal_suffixes or action_id in goal_suffixes
        )
        schema_status = schema_source_for_action(action_id, kind=spec.kind, suffix=suffix)
        if schema_status != "missing":
            schema = parameters_for_action(action_id, kind=spec.kind, suffix=suffix)
            if not schema.get("properties"):
                schema_status = "missing"

        scopes = entry.required_scopes if entry else spec.scopes
        rows.append(
            CatalogAuditRow(
                vendor=vendor,
                action_id=action_id,
                input_schema_status=schema_status,
                implementation_status=impl,
                chat_exposure=chat_exposure,
                execute_exposure=execute_exposure or implemented,
                oauth_scopes=scopes,
                scope_registered=_scope_registered(registry_key, scopes),
                risk_level=_risk_level(
                    kind=spec.kind,
                    destructive=spec.destructive,
                    requires_approval=spec.requires_approval or (entry.requires_approval if entry else False),
                ),
                approval_required=bool(entry.requires_approval if entry else spec.requires_approval or spec.kind == "write"),
                multi_step_plans=bool(entry and entry.chat_executable and implemented),
                structured_results=implemented,
                test_status=_test_status_for(action_id, vendor),
            )
        )
    return rows


def audit_summary(rows: list[CatalogAuditRow] | None = None) -> dict[str, Any]:
    data = rows or audit_connector_catalog()
    total = len(data)
    by_vendor: dict[str, dict[str, int]] = {}
    for row in data:
        bucket = by_vendor.setdefault(
            row.vendor,
            {
                "total": 0,
                "implemented": 0,
                "chat": 0,
                "execute": 0,
                "missing_schema": 0,
                "no_tests": 0,
                "high_risk": 0,
            },
        )
        bucket["total"] += 1
        if row.implementation_status != "not_implemented":
            bucket["implemented"] += 1
        if row.chat_exposure:
            bucket["chat"] += 1
        if row.execute_exposure:
            bucket["execute"] += 1
        if row.input_schema_status == "missing":
            bucket["missing_schema"] += 1
        if row.test_status == "none":
            bucket["no_tests"] += 1
        if row.risk_level == "high":
            bucket["high_risk"] += 1

    registry = registry_violation_summary()
    return {
        "totalActions": total,
        "implemented": sum(1 for r in data if r.implementation_status != "not_implemented"),
        "chatExposed": sum(1 for r in data if r.chat_exposure),
        "executeExposed": sum(1 for r in data if r.execute_exposure),
        "schemaMissing": sum(1 for r in data if r.input_schema_status == "missing"),
        "scopeUnregistered": sum(1 for r in data if not r.scope_registered and r.implementation_status != "not_implemented"),
        "noTests": sum(1 for r in data if r.test_status == "none"),
        "multiStepReady": sum(1 for r in data if r.multi_step_plans),
        "registryViolations": registry,
        "byVendor": by_vendor,
    }


def top_vendors_by_implementation(limit: int = 10) -> list[str]:
    summary = audit_summary()
    ranked = sorted(
        summary["byVendor"].items(),
        key=lambda item: (-item[1]["implemented"], -item[1]["total"], item[0]),
    )
    priority = [v for v in ranked if v[0] in PRIORITY_CONNECTORS]
    rest = [v for v in ranked if v[0] not in PRIORITY_CONNECTORS]
    ordered = priority + rest
    return [vendor for vendor, _stats in ordered[:limit]]


def top_actions_for_smoke(limit: int = 50) -> list[str]:
    vendors = set(top_vendors_by_implementation(10))
    rows = [r for r in audit_connector_catalog() if r.vendor in vendors and r.implementation_status != "not_implemented"]
    rows.sort(key=lambda r: (r.vendor, r.action_id))
    return [r.action_id for r in rows[:limit]]


def export_audit_csv(path: Path, rows: list[CatalogAuditRow] | None = None) -> Path:
    import csv

    data = rows or audit_connector_catalog()
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(data[0].to_dict().keys()) if data else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            payload = row.to_dict()
            payload["oauthScopes"] = "|".join(payload["oauthScopes"])
            writer.writerow(payload)
    return path


def export_audit_json(path: Path, rows: list[CatalogAuditRow] | None = None) -> Path:
    data = rows or audit_connector_catalog()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": audit_summary(data),
        "actions": [row.to_dict() for row in data],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
