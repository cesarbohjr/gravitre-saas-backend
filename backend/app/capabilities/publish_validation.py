"""Static developer validation for portable capability publishing.

This module never executes package scripts or remote tools. It produces
deterministic publish-readiness checks from persisted package metadata and
inert resources.
"""
from __future__ import annotations

from typing import Any


def _check(
    checks: list[dict[str, Any]],
    key: str,
    *,
    passed: bool,
    severity: str,
    message: str,
) -> None:
    checks.append(
        {
            "key": key,
            "passed": bool(passed),
            "severity": severity,
            "message": message,
        }
    )


def validate_capability_for_publish(
    package: dict[str, Any],
    resources: list[dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    manifest = package.get("manifest") if isinstance(package.get("manifest"), dict) else {}
    inspection = package.get("inspection") if isinstance(package.get("inspection"), dict) else {}
    security_scan = package.get("security_scan") if isinstance(package.get("security_scan"), dict) else {}

    package_format = str(package.get("package_format") or inspection.get("format") or "unknown")
    _check(
        checks,
        "recognized_format",
        passed=package_format != "unknown",
        severity="error",
        message="Package format is recognized." if package_format != "unknown" else "Package format is unknown.",
    )

    name = str(package.get("name") or manifest.get("name") or "").strip()
    _check(
        checks,
        "package_identity",
        passed=bool(name and name != "unnamed-capability"),
        severity="error",
        message="Package has a stable name." if name and name != "unnamed-capability" else "Package needs a stable name.",
    )

    license_policy = str(package.get("license_policy") or "review")
    _check(
        checks,
        "license_policy",
        passed=license_policy != "block",
        severity="error",
        message=(
            "License does not block distribution."
            if license_policy != "block"
            else "License policy blocks distribution."
        ),
    )

    blocked = bool(security_scan.get("blocked")) or str(package.get("risk_level") or "") == "blocked"
    _check(
        checks,
        "security_policy",
        passed=not blocked,
        severity="error",
        message="Static security policy passed." if not blocked else "Static security policy blocks publishing.",
    )

    unsafe_script_rows = [
        row
        for row in resources
        if (
            bool(row.get("executable")) or str(row.get("kind") or "") == "script"
        )
        and bool(str(row.get("content") or "").strip())
    ]
    _check(
        checks,
        "inert_executable_resources",
        passed=not unsafe_script_rows,
        severity="error",
        message=(
            "Executable resources are metadata-only."
            if not unsafe_script_rows
            else "Executable resources must not embed script content."
        ),
    )

    digest = str(package.get("content_digest") or "").strip()
    _check(
        checks,
        "content_digest",
        passed=bool(digest),
        severity="error",
        message="Package has an immutable content digest." if digest else "Package needs an immutable content digest.",
    )

    git_pinned = bool(
        str(package.get("source_uri") or "").strip()
        and str(package.get("source_commit_sha") or "").strip()
        and digest
    )
    trusted_signed = bool(
        digest
        and str(package.get("signature_status") or "") == "verified"
        and (
            bool(package.get("publisher_trusted"))
            or bool(package.get("publisher_verified"))
        )
    )
    _check(
        checks,
        "publish_provenance",
        passed=git_pinned or trusted_signed,
        severity="error",
        message=(
            "Strong publishing provenance is available."
            if git_pinned or trusted_signed
            else "Marketplace publishing requires exact Git provenance or a trusted verified signature."
        ),
    )

    components = inspection.get("components") if isinstance(inspection.get("components"), list) else []
    mcp_components = [
        row for row in components
        if isinstance(row, dict) and str(row.get("kind") or "") == "mcp"
    ]
    if mcp_components:
        _check(
            checks,
            "mcp_activation_separation",
            passed=True,
            severity="info",
            message="MCP dependencies require separate Gravitre preparation, discovery, and approval.",
        )

    executable = [
        row for row in resources
        if bool(row.get("executable")) or str(row.get("kind") or "") == "script"
    ]
    if executable:
        _check(
            checks,
            "script_runtime",
            passed=True,
            severity="warning",
            message=f"{len(executable)} executable resource(s) are inert and will not run directly in Gravitre.",
        )

    errors = [row for row in checks if row["severity"] == "error" and not row["passed"]]
    warnings = [row for row in checks if row["severity"] == "warning"]
    return {
        "readyForMarketplace": not errors,
        "checks": checks,
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "executionPerformed": False,
    }
