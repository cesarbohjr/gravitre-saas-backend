"""Connector registry contract verification — catalog, handlers, router visibility."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.connectors.action_catalog.registry import all_catalog_action_specs, get_action_spec, get_vendor_catalog
from app.connectors.action_catalog.tool_aliases import (
    REGISTRY_VENDOR_PREFIX_ALIASES,
    catalog_tool_is_implemented,
    resolve_registry_action,
)
from app.services.connector_action_workflows import LIST_CAPABILITY_CHECKS
from app.services.connector_execution_matrix import PRIORITY_CONNECTORS, build_connector_execution_matrix
from app.services.tool_service import list_registered_actions

ViolationSeverity = Literal["error", "warning"]

# Legacy invoke_tool handlers registered before catalog parity. Do not add new entries.
REGISTERED_WITHOUT_CATALOG_ALLOWLIST: frozenset[str] = frozenset(
    {
        "fhir.appointments.search",
        "fhir.patients.get",
        "fhir.patients.search",
        "fhir.prior_auth.checklist",
        "jira.users.search",
        "quickbooks.accounts.list",
        "quickbooks.bills.get",
        "quickbooks.customers.get",
        "quickbooks.payments.list",
        "quickbooks.vendors.get",
        "quickbooks.vendors.list",
        "salesforce.accounts.create",
        "webhook.post",
        "zendesk.tickets.close",
    }
)

_REGISTRY_PREFIX_TO_CATALOG_VENDOR = {
    alias_prefix: catalog_vendor
    for catalog_vendor, alias_prefix in REGISTRY_VENDOR_PREFIX_ALIASES.items()
}


@dataclass(frozen=True)
class RegistryViolation:
    code: str
    severity: ViolationSeverity
    message: str
    vendor: str | None = None
    action_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "vendor": self.vendor,
            "actionKey": self.action_key,
        }


def _catalog_key_for_registered_action(action_key: str) -> str | None:
    """Resolve a registry key to its catalog action id when aliases apply."""
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


def _catalog_actions_for_vendor(vendor: str) -> list[str]:
    spec = get_vendor_catalog().get(vendor)
    if not spec:
        return []
    return [action.id for action in spec.all_actions()]


def _capability_supported(vendor: str, patterns: tuple[str, ...], *, registered: set[str]) -> bool:
    for action_key in _catalog_actions_for_vendor(vendor):
        lowered = action_key.lower()
        if not any(pattern in lowered for pattern in patterns):
            continue
        if catalog_tool_is_implemented(action_key, registered):
            return True
    return False


def verify_connector_registry() -> list[RegistryViolation]:
    """Return structural violations across catalog, invoke_tool, and chat exposure."""
    registered = set(list_registered_actions())
    matrix = {entry.action_key: entry for entry in build_connector_execution_matrix()}
    violations: list[RegistryViolation] = []

    for spec in all_catalog_action_specs():
        action_id = spec.id
        vendor = action_id.split(".", 1)[0]
        entry = matrix.get(action_id)
        if entry is None:
            violations.append(
                RegistryViolation(
                    code="catalog_missing_matrix_entry",
                    severity="error",
                    message=f"Catalog action {action_id} has no execution-matrix entry.",
                    vendor=vendor,
                    action_key=action_id,
                )
            )
            continue

        if entry.implementation_status == "not_implemented":
            continue

        registry_key = resolve_registry_action(action_id, registered)
        if registry_key not in registered:
            violations.append(
                RegistryViolation(
                    code="catalog_implemented_missing_handler",
                    severity="error",
                    message=(
                        f"Catalog action {action_id} is marked implemented but "
                        f"handler {registry_key} is not registered."
                    ),
                    vendor=vendor,
                    action_key=action_id,
                )
            )

        if vendor in PRIORITY_CONNECTORS and spec.kind == "write" and not entry.chat_executable:
            violations.append(
                RegistryViolation(
                    code="priority_write_not_chat_exposed",
                    severity="error",
                    message=(
                        f"Priority connector write action {action_id} is implemented "
                        "but not chat-executable."
                    ),
                    vendor=vendor,
                    action_key=action_id,
                )
            )

        for capability, patterns in LIST_CAPABILITY_CHECKS.items():
            lowered = action_id.lower()
            if not any(pattern in lowered for pattern in patterns):
                continue
            if vendor not in PRIORITY_CONNECTORS:
                continue
            if not catalog_tool_is_implemented(action_id, registered):
                violations.append(
                    RegistryViolation(
                        code="capability_pattern_unimplemented",
                        severity="error",
                        message=(
                            f"Priority vendor {vendor} catalogs {action_id} for "
                            f"{capability} but it is not registered in invoke_tool."
                        ),
                        vendor=vendor,
                        action_key=action_id,
                    )
                )

    for action_key in sorted(registered):
        if "." not in action_key:
            continue
        if _catalog_key_for_registered_action(action_key):
            continue
        if action_key in REGISTERED_WITHOUT_CATALOG_ALLOWLIST:
            continue
        vendor = action_key.split(".", 1)[0]
        violations.append(
            RegistryViolation(
                code="registered_missing_catalog",
                severity="warning",
                message=f"Registered action {action_key} has no catalog entry.",
                vendor=vendor,
                action_key=action_key,
            )
        )

    for vendor in sorted(PRIORITY_CONNECTORS):
        if vendor not in get_vendor_catalog():
            continue
        for capability, patterns in LIST_CAPABILITY_CHECKS.items():
            if _capability_supported(vendor, patterns, registered=registered):
                continue
            # Only require capabilities that are partially declared in catalog.
            declared = any(
                any(pattern in action_key.lower() for pattern in patterns)
                for action_key in _catalog_actions_for_vendor(vendor)
            )
            if not declared:
                continue
            violations.append(
                RegistryViolation(
                    code="declared_capability_unimplemented",
                    severity="error",
                    message=(
                        f"Priority vendor {vendor} declares catalog actions for "
                        f"{capability} but none are registered in invoke_tool."
                    ),
                    vendor=vendor,
                )
            )

    return violations


def registry_violation_summary(
    violations: list[RegistryViolation] | None = None,
) -> dict[str, Any]:
    data = violations if violations is not None else verify_connector_registry()
    errors = [v for v in data if v.severity == "error"]
    warnings = [v for v in data if v.severity == "warning"]
    by_code: dict[str, int] = {}
    for item in data:
        by_code[item.code] = by_code.get(item.code, 0) + 1
    return {
        "totalViolations": len(data),
        "errors": len(errors),
        "warnings": len(warnings),
        "byCode": by_code,
        "violations": [item.to_dict() for item in data],
    }


def assert_registry_contract(*, allow_warnings: bool = True) -> None:
    """Raise AssertionError when registry contract errors exist (for tests/CI)."""
    violations = verify_connector_registry()
    errors = [v for v in violations if v.severity == "error"]
    if errors:
        lines = "\n".join(f"- [{v.code}] {v.message}" for v in errors[:20])
        extra = f"\n... and {len(errors) - 20} more" if len(errors) > 20 else ""
        raise AssertionError(f"Connector registry contract failed ({len(errors)} errors):\n{lines}{extra}")
    if not allow_warnings:
        warnings = [v for v in violations if v.severity == "warning"]
        if warnings:
            lines = "\n".join(f"- [{v.code}] {v.message}" for v in warnings[:20])
            raise AssertionError(f"Connector registry warnings ({len(warnings)}):\n{lines}")
