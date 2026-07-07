"""Enforce that raw connector *_api clients stay behind the tool execution layer."""
from __future__ import annotations

import ast
from pathlib import Path

from app.services.connector_registry_verification import RegistryViolation

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP_ROOT = _REPO_ROOT / "app"

# Tool executors and invoke_tool registry may call vendor HTTP clients directly.
_ALLOWED_FILE_SUFFIXES: tuple[str, ...] = ("_tools.py",)
_ALLOWED_RELATIVE_FILES: frozenset[str] = frozenset(
    {
        "app/services/tool_service.py",
    }
)

# Documented exceptions — shrink over time by routing through *_tools.py instead.
_API_IMPORT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Read-only governance helpers (disambiguation / parameter inference).
        "app/services/connector_action_workflows.py",
        "app/services/connector_parameter_inference.py",
        # Connector setup and health probes.
        "app/routers/connectors.py",
        "app/connectors/connection_health.py",
        # Cross-domain legacy callers pending tool-layer migration.
        "app/services/outcome_attribution_service.py",
        "app/services/post_publish_marketing_metrics_service.py",
    }
)


def _relative_app_path(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _is_allowed_importer(relative_path: str) -> bool:
    if relative_path.startswith("tests/"):
        return True
    if relative_path.endswith(_ALLOWED_FILE_SUFFIXES):
        return True
    if relative_path in _ALLOWED_RELATIVE_FILES:
        return True
    if relative_path in _API_IMPORT_ALLOWLIST:
        return True
    if relative_path.endswith("_api.py") and relative_path.startswith("app/connectors/"):
        return True
    return False


def _extract_api_imports(path: Path) -> list[str]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if module.startswith("app.connectors.") and module.split(".")[-1].endswith("_api"):
                modules.append(module)
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith("app.connectors.") and name.split(".")[-1].endswith("_api"):
                    modules.append(name)
    return modules


def verify_api_import_boundaries(*, app_root: Path | None = None) -> list[RegistryViolation]:
    """Return violations when non-execution modules import raw connector API clients."""
    root = app_root or _APP_ROOT
    violations: list[RegistryViolation] = []

    for path in sorted(root.rglob("*.py")):
        relative_path = _relative_app_path(path)
        if _is_allowed_importer(relative_path):
            continue
        for module in _extract_api_imports(path):
            api_name = module.rsplit(".", 1)[-1]
            vendor = api_name[: -len("_api")] if api_name.endswith("_api") else None
            violations.append(
                RegistryViolation(
                    code="raw_api_import_outside_execution_layer",
                    severity="error",
                    message=(
                        f"{relative_path} imports `{module}` outside the governed execution layer. "
                        "Route through the matching *_tools.py executor or tool_service instead."
                    ),
                    vendor=vendor,
                    action_key=module,
                )
            )
    return violations


def list_api_import_violations() -> list[dict[str, str]]:
    """Flat summary for audits and debugging."""
    return [
        {
            "file": violation.message.split(" imports ", 1)[0],
            "module": violation.action_key or "",
            "code": violation.code,
        }
        for violation in verify_api_import_boundaries()
    ]
