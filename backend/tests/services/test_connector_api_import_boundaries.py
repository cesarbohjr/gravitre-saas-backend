"""Import boundary tests — raw connector API clients stay behind tool executors."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.connector_api_import_boundaries import (
    _API_IMPORT_ALLOWLIST,
    _extract_api_imports,
    _is_allowed_importer,
    verify_api_import_boundaries,
)
from app.services.connector_registry_verification import assert_registry_contract


def test_api_import_boundaries_have_no_errors():
    violations = verify_api_import_boundaries()
    assert violations == []


def test_registry_contract_includes_import_boundaries():
    assert_registry_contract()


def test_tool_executors_may_import_api_clients():
    assert _is_allowed_importer("app/services/apollo_tools.py")
    assert _is_allowed_importer("app/services/tool_service.py")


def test_governance_modules_are_allowlisted_pending_tool_migration():
    assert "app/services/connector_action_workflows.py" in _API_IMPORT_ALLOWLIST
    assert "app/services/connector_parameter_inference.py" in _API_IMPORT_ALLOWLIST


def test_non_execution_import_is_detected(tmp_path: Path):
    rogue = tmp_path / "app" / "services" / "rogue_service.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text(
        "from app.connectors.apollo_api import create_label\n",
        encoding="utf-8",
    )
    modules = _extract_api_imports(rogue)
    assert modules == ["app.connectors.apollo_api"]
    assert _is_allowed_importer("app/services/rogue_service.py") is False


def test_new_allowlist_entry_requires_review():
    """Allowlist should not grow without explicit review."""
    assert len(_API_IMPORT_ALLOWLIST) <= 6


def test_ast_extracts_import_from_statements():
    source = "import app.connectors.stripe_api as stripe_api\n"
    path = Path("sample.py")
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith("_api"):
                    modules.append(alias.name)
    assert modules == ["app.connectors.stripe_api"]
