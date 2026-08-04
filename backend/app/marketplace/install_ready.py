"""Install-ready evaluation: connectors + design-time bindings + honesty labels."""
from __future__ import annotations

from typing import Any

from app.workflows.binding_validation import BindingError, validate_bindings
from app.workflows.constants import SCHEMA_VERSION

# Connectors without completed-work honesty audit (STA-337). Packs that require
# these get an explicit manualSetupRequired label — never a silent fail.
HONESTY_GATED_CONNECTORS: dict[str, str] = {
    # Live mutate proof still missing (smoke Ads account has 0 campaigns).
    "google_ads": "Google Ads completed-work honesty: mutate evidence pending (STA-337)",
    "googleads": "Google Ads completed-work honesty: mutate evidence pending (STA-337)",
    # No connected google_analytics connector in prod at audit time.
    "google_analytics": "Google Analytics completed-work honesty not yet audited (STA-337)",
    "ga4": "Google Analytics completed-work honesty not yet audited (STA-337)",
    # microsoft365 / outlook / microsoft cleared after live PASS (STA-337 2026-08-04).
}


def _extract_workflow_steps(asset: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    config = asset.get("config") if isinstance(asset.get("config"), dict) else {}
    asset_type = str(asset.get("asset_type") or "")
    if asset_type == "workflow" and isinstance(config.get("steps"), list):
        return list(config["steps"]), str(config.get("schema_version") or SCHEMA_VERSION)
    if asset_type == "department_pack" and isinstance(config.get("workflow_steps"), list):
        return list(config["workflow_steps"]), SCHEMA_VERSION
    # Intelligence packs may embed demo workflow steps under config.workflowSteps / workflow_steps.
    for key in ("workflow_steps", "workflowSteps", "steps"):
        if isinstance(config.get(key), list) and config[key]:
            return list(config[key]), str(config.get("schema_version") or SCHEMA_VERSION)
    return [], SCHEMA_VERSION


def _declared_install_keys(asset: dict[str, Any]) -> set[str]:
    raw = asset.get("install_variables")
    keys: set[str] = set()
    if isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict) and row.get("key"):
                keys.add(str(row["key"]))
            elif hasattr(row, "key"):
                keys.add(str(row.key))
    return keys


def _manual_setup_required(required_connectors: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in required_connectors or []:
        if isinstance(row, dict):
            ctype = str(row.get("connectorType") or row.get("connector_type") or "").strip().lower()
            required = bool(row.get("required", True))
        else:
            ctype = str(getattr(row, "connector_type", "") or "").strip().lower()
            required = bool(getattr(row, "required", True))
        if not required or not ctype:
            continue
        note = HONESTY_GATED_CONNECTORS.get(ctype)
        if note:
            out.append({"connector": ctype, "reason": note})
    return out


def evaluate_binding_install_ready(asset: dict[str, Any]) -> dict[str, Any]:
    """Run Part 1 binding validation for an asset's embedded workflow (if any)."""
    steps, schema_version = _extract_workflow_steps(asset)
    if not steps:
        return {
            "installReady": True,
            "installReadyErrors": [],
            "hasWorkflowBindings": False,
        }
    result = validate_bindings(
        {"schema_version": schema_version, "steps": steps},
        declared_parameters=_declared_install_keys(asset),
    )
    errors = [e.as_dict() for e in result.errors]
    return {
        "installReady": result.ok,
        "installReadyErrors": errors,
        "hasWorkflowBindings": True,
    }


def merge_install_ready(
    *,
    connector_can_install: bool,
    asset: dict[str, Any],
    entitlement_blocks: bool = False,
) -> dict[str, Any]:
    """Combine connector checklist, binding gate, and honesty labels."""
    binding = evaluate_binding_install_ready(asset)
    manual = _manual_setup_required(asset.get("required_connectors") or [])
    install_ready = bool(connector_can_install and binding["installReady"] and not entitlement_blocks)
    blockers: list[dict[str, Any]] = []
    for err in binding["installReadyErrors"]:
        blockers.append(
            {
                "connector": "workflow_bindings",
                "reason": err.get("message") or err.get("code"),
                "code": err.get("code"),
                "stepId": err.get("stepId"),
                "action_url": None,
            }
        )
    return {
        "installReady": install_ready,
        "installReadyErrors": binding["installReadyErrors"],
        "hasWorkflowBindings": binding["hasWorkflowBindings"],
        "manualSetupRequired": manual,
        "bindingBlockers": blockers,
    }
